#!/usr/bin/env python3
"""
Generate consolidated tick CSV directly from PostgreSQL (one UTC day).

Reads from stream_ingest.ladder_levels and stream_ingest.traded_volume,
joins metadata, filters by publish_time for a single UTC calendar day,
deduplicates, sorts, and writes CSV + report.

Designed to run inside Docker container on VPS.

Usage:
  python scripts/consolidate_tick_data_direct.py --date 2026-02-16 --output-dir /data_exports

Requires: psycopg2-binary, pandas (for CSV writing).
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

try:
    import pandas as pd
except ImportError:
    pd = None

DEFAULT_OUTPUT_DIR = Path("/data_exports")
CSV_COLUMNS = [
    "received_at",
    "publish_time",
    "market_id",
    "event_id",
    "selection_id",
    "side",
    "level",
    "price",
    "size",
    "traded_volume",
    "in_play",
    "change_type",
    "sequence",
    "record_type",
    "market_status",
    "market_start_time",
    "market_type",
    "runner_name",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("consolidate_tick_direct")

# DB connection from env (Docker)
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
PGOPTIONS = os.environ.get("PGOPTIONS", "-c search_path=public,stream_ingest")


def get_conn():
    if not psycopg2:
        raise RuntimeError("psycopg2 required. pip install psycopg2-binary")
    kwargs = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": POSTGRES_DB,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "connect_timeout": 30,
    }
    if PGOPTIONS:
        kwargs["options"] = PGOPTIONS
    return psycopg2.connect(**kwargs)


def parse_utc_date(date_str: str) -> tuple[datetime, datetime]:
    """Parse YYYY-MM-DD and return (start_utc, end_utc) for that calendar day in UTC."""
    start_utc = datetime.strptime(date_str + " 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc


def utc_iso(ts: Any) -> str:
    """Format timestamp as UTC ISO 8601 with Z. None -> empty string."""
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    if hasattr(ts, "strftime"):
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=timezone.utc) if hasattr(ts, "replace") else ts
        return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return str(ts)


def _csv_cell(v: Any) -> str:
    """Format one cell for CSV; null/NaN -> empty string."""
    if v is None:
        return ""
    if isinstance(v, float) and (v != v):  # NaN
        return ""
    return str(v)


def build_consolidation_query(start_utc: datetime, end_utc: datetime) -> str:
    """Build SQL query that unions ladder_levels and traded_volume, joins metadata, filters by date."""
    # Ladder rows: record_type='ladder', side BACK/LAY, level 0-7
    ladder_query = """
    SELECT
        ll.received_time AS received_at,
        ll.publish_time,
        ll.market_id,
        COALESCE(m.event_id, '') AS event_id,
        ll.selection_id,
        CASE WHEN ll.side = 'B' THEN 'BACK' WHEN ll.side = 'L' THEN 'LAY' ELSE '' END AS side,
        ll.level,
        ll.price,
        ll.size,
        NULL::numeric AS traded_volume,
        NULL::boolean AS in_play,
        'update' AS change_type,
        ll.level AS sequence,
        'ladder' AS record_type,
        COALESCE(lc.status, '') AS market_status,
        COALESCE(m.market_start_time::text, '') AS market_start_time,
        COALESCE(m.market_type, '') AS market_type,
        COALESCE(r.runner_name, '') AS runner_name
    FROM stream_ingest.ladder_levels ll
    LEFT JOIN public.markets m ON m.market_id = ll.market_id
    LEFT JOIN public.runners r ON r.market_id = ll.market_id AND r.selection_id = ll.selection_id
    LEFT JOIN LATERAL (
        SELECT status
        FROM stream_ingest.market_lifecycle_events lc
        WHERE lc.market_id = ll.market_id
        ORDER BY lc.publish_time DESC
        LIMIT 1
    ) lc ON true
    WHERE ll.publish_time >= %s AND ll.publish_time < %s
    """
    # Traded volume rows: record_type='traded_volume', no side/level
    traded_query = """
    SELECT
        tv.received_time AS received_at,
        tv.publish_time,
        tv.market_id,
        COALESCE(m.event_id, '') AS event_id,
        tv.selection_id,
        NULL::text AS side,
        NULL::integer AS level,
        tv.price,
        tv.size_traded AS size,
        tv.size_traded AS traded_volume,
        NULL::boolean AS in_play,
        'update' AS change_type,
        0 AS sequence,
        'traded_volume' AS record_type,
        COALESCE(lc.status, '') AS market_status,
        COALESCE(m.market_start_time::text, '') AS market_start_time,
        COALESCE(m.market_type, '') AS market_type,
        COALESCE(r.runner_name, '') AS runner_name
    FROM stream_ingest.traded_volume tv
    LEFT JOIN public.markets m ON m.market_id = tv.market_id
    LEFT JOIN public.runners r ON r.market_id = tv.market_id AND r.selection_id = tv.selection_id
    LEFT JOIN LATERAL (
        SELECT status
        FROM stream_ingest.market_lifecycle_events lc
        WHERE lc.market_id = tv.market_id
        ORDER BY lc.publish_time DESC
        LIMIT 1
    ) lc ON true
    WHERE tv.publish_time >= %s AND tv.publish_time < %s
    """
    # UNION ALL (we dedupe in Python) and ORDER BY
    # Note: ORDER BY must be at outer level, not inside subqueries
    # Sorting must be deterministic and done in SQL
    return f"""
    SELECT * FROM (
        {ladder_query}
        UNION ALL
        {traded_query}
    ) combined
    ORDER BY
        publish_time ASC,
        market_id ASC,
        selection_id ASC,
        CASE WHEN side = 'BACK' THEN 0
             WHEN side = 'LAY' THEN 1
             ELSE 2 END ASC,
        level ASC NULLS FIRST,
        sequence ASC NULLS FIRST
    """


def dedupe_key(row: dict) -> tuple:
    """Uniqueness key: record_type, market_id, selection_id, side, level, price, publish_time, sequence.
    NULLs preserved (not replaced with defaults).
    """
    record_type = row.get("record_type") or ""
    market_id = row.get("market_id") or ""
    selection_id = row.get("selection_id")
    side = row.get("side") or ""
    level = row.get("level")  # Keep None if None
    price = row.get("price")  # Keep None if None
    publish_time = row.get("publish_time") or ""
    sequence = row.get("sequence")  # Keep None if None
    return (
        record_type,
        market_id,
        selection_id,
        side,
        level,
        price,
        publish_time,
        sequence,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate consolidated tick CSV directly from PostgreSQL (one UTC day)."
    )
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        metavar="YYYY-MM-DD",
        help="UTC calendar day (e.g. 2026-02-16)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory (default: /data_exports)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10000,
        help="Rows per chunk when writing CSV (default: 10000)",
    )
    args = parser.parse_args()

    try:
        start_utc, end_utc = parse_utc_date(args.date)
    except ValueError as e:
        logger.error("Invalid date format: %s. Use YYYY-MM-DD", e)
        return 1

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_filename = f"consolidated_ticks_{args.date.replace('-', '_')}.csv"
    report_filename = f"consolidation_report_{args.date.replace('-', '_')}.txt"
    csv_path = output_dir / csv_filename
    report_path = output_dir / report_filename

    logger.info("Date window: [%s, %s)", start_utc.isoformat(), end_utc.isoformat())
    logger.info("Output CSV: %s", csv_path)

    start_time = time.perf_counter()
    conn = get_conn()

    try:
        query = build_consolidation_query(start_utc, end_utc)
        logger.info("Executing query (chunked)...")

        with conn.cursor(name="consolidate_cursor", cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (start_utc, end_utc, start_utc, end_utc))
            cur.itersize = args.chunk_size

            # Streaming deduplication: compare current row with previous row key
            prev_key: Optional[tuple] = None
            total_rows_read = 0
            rows_before_dedupe = 0
            total_written = 0
            duplicates_removed = 0
            distinct_markets: set[str] = set()
            earliest_pt: Optional[str] = None
            latest_pt: Optional[str] = None

            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
                writer.writeheader()

                for row in cur:
                    total_rows_read += 1
                    rows_before_dedupe += 1
                    market_id = row.get("market_id") or ""
                    if market_id:
                        distinct_markets.add(market_id)

                    pt = utc_iso(row.get("publish_time"))
                    if pt:
                        if earliest_pt is None or pt < earliest_pt:
                            earliest_pt = pt
                        if latest_pt is None or pt > latest_pt:
                            latest_pt = pt

                    # Streaming deduplication: compare with previous row
                    k = dedupe_key(row)
                    if prev_key is not None and k == prev_key:
                        duplicates_removed += 1
                        continue

                    prev_key = k
                    out_row = {col: _csv_cell(row.get(col)) for col in CSV_COLUMNS}
                    writer.writerow(out_row)
                    total_written += 1

                    if total_written % 100000 == 0:
                        logger.info("Written %s rows (read %s, dupes %s)", total_written, total_rows_read, duplicates_removed)

        duration_sec = time.perf_counter() - start_time
        file_size = csv_path.stat().st_size if csv_path.exists() else 0

        # Date validation: check first/last rows are in range
        date_validation_ok = True
        if total_written > 0:
            start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_utc.strftime("%Y-%m-%dT%H:%M:%S")
            if earliest_pt and (earliest_pt < start_str or earliest_pt >= end_str):
                date_validation_ok = False
            if latest_pt and (latest_pt < start_str or latest_pt >= end_str):
                date_validation_ok = False

        # Report
        report_lines = [
            "Tick consolidation (direct from PostgreSQL) – execution report",
            "==============================================================",
            f"Selected UTC date: {args.date}",
            f"Start (inclusive): {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"End (exclusive):   {end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"Absolute output path: {csv_path}",
            f"Total rows read from DB: {total_rows_read}",
            f"Rows written before dedupe: {rows_before_dedupe}",
            f"Duplicates removed: {duplicates_removed}",
            f"Final rows written: {total_written}",
            f"Distinct market_id count: {len(distinct_markets)}",
            f"Earliest publish_time: {earliest_pt or 'N/A'}",
            f"Latest publish_time: {latest_pt or 'N/A'}",
            f"File size (bytes): {file_size}",
            f"Runtime (seconds): {duration_sec:.2f}",
            f"Date validation (all rows in range): {'PASS' if date_validation_ok else 'FAIL'}",
        ]

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        logger.info("Consolidated CSV: %s (%s rows, %s bytes)", csv_path, total_written, file_size)
        logger.info("Report: %s", report_path)
        for line in report_lines:
            logger.info("  %s", line)

        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
