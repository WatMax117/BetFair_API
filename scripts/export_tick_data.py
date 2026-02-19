#!/usr/bin/env python3
"""
Full export of all tick-level price and liquidity data from Betfair Streaming API.

Extracts ladder_levels and traded_volume from stream_ingest, with metadata from
public.markets, public.events, public.runners. Outputs Parquet (preferred) or JSONL
per market, plus index.csv and execution report.

Usage:
  python scripts/export_tick_data.py --output-dir data_exports/tick_export [--format parquet|jsonl] [--resume]
  python scripts/export_tick_data.py --output-dir data_exports/tick_export --format jsonl --resume

Requires: psycopg2-binary, pandas, pyarrow (for Parquet).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import pandas as pd
except ImportError:
    pd = None
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data_exports" / "tick_export"
CHECKPOINT_FILENAME = ".export_tick_checkpoint"
INDEX_FILENAME = "index.csv"
REPORT_FILENAME = "execution_report.txt"

# DB connection: set POSTGRES_* env; search_path must include stream_ingest and public
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
# Include stream_ingest so we can query stream_ingest.ladder_levels etc.
PGOPTIONS = os.environ.get("PGOPTIONS", "-c search_path=public,stream_ingest")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("export_tick_data")


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


def utc_ts(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as ISO UTC string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def list_markets_with_ticks(conn) -> list[str]:
    """All market_ids that have at least one row in stream_ingest.ladder_levels, ordered for stable resume."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT market_id
            FROM stream_ingest.ladder_levels
            ORDER BY market_id
            """
        )
        return [r[0] for r in cur.fetchall()]


def list_all_stored_markets(conn) -> list[str]:
    """All market_ids from public.markets (for index completeness: every stored market in index)."""
    with conn.cursor() as cur:
        cur.execute("SELECT market_id FROM public.markets ORDER BY market_id")
        return [r[0] for r in cur.fetchall()]


def fetch_market_metadata(conn, market_id: str) -> Optional[dict[str, Any]]:
    """Market metadata for index: event_id, market_name, market_type, market_start_time, market_status, in_play, numberOfRunners."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                m.market_id,
                m.event_id,
                m.market_name,
                m.market_type,
                m.market_start_time
            FROM public.markets m
            WHERE m.market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        meta = dict(row)
        meta["event_type_id"] = None  # Not stored in current schema
        meta["market_status"] = None
        meta["in_play"] = None
        meta["number_of_runners"] = None

        # Latest lifecycle for this market
        cur.execute(
            """
            SELECT status, in_play
            FROM stream_ingest.market_lifecycle_events
            WHERE market_id = %s
            ORDER BY publish_time DESC
            LIMIT 1
            """,
            (market_id,),
        )
        lc = cur.fetchone()
        if lc:
            meta["market_status"] = lc.get("status")
            meta["in_play"] = lc.get("in_play")

        # Runner count
        cur.execute(
            "SELECT COUNT(*) AS n FROM public.runners WHERE market_id = %s",
            (market_id,),
        )
        rn = cur.fetchone()
        if rn and rn.get("n") is not None:
            meta["number_of_runners"] = int(rn["n"])

        return meta


def fetch_runner_metadata(conn, market_id: str) -> list[dict[str, Any]]:
    """Runner metadata: selection_id, runner_name, handicap (if applicable)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT selection_id, runner_name
            FROM public.runners
            WHERE market_id = %s
            ORDER BY selection_id
            """,
            (market_id,),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "selection_id": int(r["selection_id"]),
            "runner_name": r.get("runner_name"),
            "handicap": None,  # Not in current schema
        })
    return out


def fetch_ladder_ticks(conn, market_id: str) -> list[dict[str, Any]]:
    """All ladder_levels rows for market, ordered by publish_time ASC, level ASC (chronological)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Select core columns; ingest_source/client_version if present (optional)
        cur.execute(
            """
            SELECT
                market_id,
                selection_id,
                side,
                level,
                price,
                size,
                publish_time,
                received_time
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s
            ORDER BY publish_time ASC, selection_id, side, level ASC
            """,
            (market_id,),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        pt = r["publish_time"]
        if pt and pt.tzinfo is None:
            pt = pt.replace(tzinfo=timezone.utc)
        rt = r["received_time"]
        if rt and rt.tzinfo is None:
            rt = rt.replace(tzinfo=timezone.utc)
        out.append({
            "received_at": rt,
            "publish_time": pt,
            "market_id": r["market_id"],
            "selection_id": int(r["selection_id"]),
            "side": "BACK" if str(r["side"]).upper() == "B" else "LAY",
            "price": float(r["price"]),
            "size": float(r["size"]),
            "traded_volume": None,
            "change_type": "update",
            "level": int(r["level"]),
            "record_type": "ladder",
        })
    return out


def fetch_traded_ticks(conn, market_id: str) -> list[dict[str, Any]]:
    """All traded_volume rows for market, ordered by publish_time ASC."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                market_id,
                selection_id,
                price,
                size_traded,
                publish_time,
                received_time
            FROM stream_ingest.traded_volume
            WHERE market_id = %s
            ORDER BY publish_time ASC, selection_id, price
            """,
            (market_id,),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        pt = r["publish_time"]
        if pt and pt.tzinfo is None:
            pt = pt.replace(tzinfo=timezone.utc)
        rt = r["received_time"]
        if rt and rt.tzinfo is None:
            rt = rt.replace(tzinfo=timezone.utc)
        out.append({
            "received_at": rt,
            "publish_time": pt,
            "market_id": r["market_id"],
            "selection_id": int(r["selection_id"]),
            "side": None,
            "price": float(r["price"]),
            "size": float(r["size_traded"]),
            "traded_volume": float(r["size_traded"]),
            "change_type": "update",
            "level": None,
            "record_type": "traded",
        })
    return out


def merge_ticks_chronological(ladder: list[dict], traded: list[dict]) -> list[dict]:
    """Merge ladder and traded into one list ordered by publish_time ASC, then record_type (ladder first), then level/sequence."""
    def key(t):
        pt = t["publish_time"]
        if pt is None:
            return (datetime.min.replace(tzinfo=timezone.utc), 0, t.get("level") or 0)
        return (pt, 0 if t.get("record_type") == "ladder" else 1, t.get("level") or 0)
    combined = ladder + traded
    combined.sort(key=key)
    return combined


def tick_rows_to_parquet_format(rows: list[dict]) -> dict[str, list]:
    """Convert tick dicts to columnar format for Parquet (with serializable timestamps)."""
    if not rows:
        return {
            "received_at": [],
            "publish_time": [],
            "market_id": [],
            "selection_id": [],
            "side": [],
            "price": [],
            "size": [],
            "traded_volume": [],
            "change_type": [],
            "level": [],
            "record_type": [],
        }
    return {
        "received_at": [utc_ts(r["received_at"]) for r in rows],
        "publish_time": [utc_ts(r["publish_time"]) for r in rows],
        "market_id": [r["market_id"] for r in rows],
        "selection_id": [r["selection_id"] for r in rows],
        "side": [r["side"] for r in rows],
        "price": [r["price"] for r in rows],
        "size": [r["size"] for r in rows],
        "traded_volume": [r["traded_volume"] for r in rows],
        "change_type": [r["change_type"] for r in rows],
        "level": [r["level"] for r in rows],
        "record_type": [r["record_type"] for r in rows],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write one JSON object per line (normalized tick record)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            rec = {
                "received_at": utc_ts(r["received_at"]),
                "publish_time": utc_ts(r["publish_time"]),
                "marketId": r["market_id"],
                "selectionId": r["selection_id"],
                "side": r["side"],
                "price": r["price"],
                "size": r["size"],
                "tradedVolume": r["traded_volume"],
                "changeType": r["change_type"],
                "level": r["level"],
                "record_type": r["record_type"],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_parquet(path: Path, rows: list[dict]) -> None:
    """Write Parquet with columns: received_at, publish_time, market_id, selection_id, side, price, size, traded_volume, in_play, change_type, level, record_type, sequence."""
    if not pd:
        raise RuntimeError("pandas and pyarrow required for Parquet. pip install pandas pyarrow")
    path.parent.mkdir(parents=True, exist_ok=True)
    col = tick_rows_to_parquet_format(rows)
    df = pd.DataFrame(col)
    # in_play: not per-tick in DB; add as null for schema compatibility
    df["in_play"] = None
    # sequence: level for ladder, row order for traded
    df["sequence"] = df.get("level", pd.Series(dtype="Int64")).fillna(0).astype("int64")
    df.to_parquet(path, index=False, engine="pyarrow")


def file_checksum(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export all tick-level streaming data (ladder + traded) per market."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory (index.csv, markets/, execution report)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "jsonl"],
        default="parquet",
        help="Output format per market (default: parquet)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last processed market_id (checkpoint file)",
    )
    parser.add_argument(
        "--include-markets-without-ticks",
        action="store_true",
        help="Include in index markets that have no ladder data (zero ticks)",
    )
    parser.add_argument(
        "--export-metadata",
        action="store_true",
        default=True,
        help="Write market and runner metadata files (default: True)",
    )
    parser.add_argument(
        "--no-export-metadata",
        action="store_false",
        dest="export_metadata",
        help="Skip writing metadata JSON files",
    )
    args = parser.parse_args()
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    markets_dir = out_dir / "markets"
    markets_dir.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    try:
        # Markets to process: those with ticks; optionally add stored markets with 0 ticks
        markets_with_ticks = list_markets_with_ticks(conn)
        if args.include_markets_without_ticks:
            all_stored = set(list_all_stored_markets(conn))
            for m in all_stored:
                if m not in markets_with_ticks:
                    markets_with_ticks.append(m)
            markets_with_ticks.sort()
        logger.info("Total markets to process: %s (with tick data: %s)", len(markets_with_ticks), len(list_markets_with_ticks(conn)))

        checkpoint_path = out_dir / CHECKPOINT_FILENAME
        start_index = 0
        if args.resume and checkpoint_path.exists():
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                last_done = f.read().strip()
            if last_done:
                try:
                    start_index = markets_with_ticks.index(last_done) + 1
                except ValueError:
                    start_index = 0
                logger.info("Resume from market index %s (after market_id=%s)", start_index, last_done)

        index_rows = []
        total_ticks = 0
        total_messages = 0
        period_start: Optional[datetime] = None
        period_end: Optional[datetime] = None

        for i, market_id in enumerate(markets_with_ticks):
            if i < start_index:
                continue
            safe_id = market_id.replace(".", "_")
            if args.format == "parquet":
                data_path = markets_dir / f"marketId={market_id}.parquet"
            else:
                data_path = markets_dir / f"marketId={market_id}.jsonl"

            ladder = fetch_ladder_ticks(conn, market_id)
            traded = fetch_traded_ticks(conn, market_id)
            ticks = merge_ticks_chronological(ladder, traded)
            n_ticks = len(ticks)

            if n_ticks == 0 and not args.include_markets_without_ticks:
                continue
            if n_ticks == 0:
                first_ts = last_ts = None
                total_messages_val = 0
                # Still write empty file so index file_path and checksum are valid
                if args.format == "parquet":
                    write_parquet(data_path, [])
                else:
                    write_jsonl(data_path, [])
            else:
                first_ts = ticks[0]["publish_time"]
                last_ts = ticks[-1]["publish_time"]
                if period_start is None or (first_ts and first_ts < period_start):
                    period_start = first_ts
                if period_end is None or (last_ts and last_ts > period_end):
                    period_end = last_ts
                total_messages_val = len(set(t["publish_time"] for t in ticks if t["publish_time"]))
                if args.format == "parquet":
                    write_parquet(data_path, ticks)
                else:
                    write_jsonl(data_path, ticks)

            file_size = data_path.stat().st_size if data_path.exists() else 0
            checksum = file_checksum(data_path) if data_path.exists() and file_size else ""
            meta = fetch_market_metadata(conn, market_id)
            event_id = (meta.get("event_id") or "") if meta else ""
            index_rows.append({
                "market_id": market_id,
                "event_id": event_id,
                "first_tick_timestamp": utc_ts(first_ts) if n_ticks else "",
                "last_tick_timestamp": utc_ts(last_ts) if n_ticks else "",
                "total_tick_records": n_ticks,
                "total_messages": total_messages_val if n_ticks else 0,
                "file_path": str(data_path.relative_to(out_dir)),
                "file_size_bytes": file_size,
                "checksum": checksum,
            })
            total_ticks += n_ticks
            total_messages += total_messages_val

            if meta and args.export_metadata and n_ticks > 0:
                meta_path = markets_dir / f"marketId={market_id}_metadata.json"
                meta_export = {
                    "marketId": market_id,
                    "eventId": meta.get("event_id"),
                    "eventTypeId": meta.get("event_type_id"),
                    "marketName": meta.get("market_name"),
                    "marketType": meta.get("market_type"),
                    "marketStartTime": utc_ts(meta.get("market_start_time")),
                    "marketStatus": meta.get("market_status"),
                    "inPlay": meta.get("in_play"),
                    "numberOfRunners": meta.get("number_of_runners"),
                }
                runners = fetch_runner_metadata(conn, market_id)
                meta_export["runners"] = [
                    {"selectionId": r["selection_id"], "runnerName": r["runner_name"], "handicap": r["handicap"]}
                    for r in runners
                ]
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_export, f, indent=2, ensure_ascii=False)

            # Checkpoint
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                f.write(market_id)
            if (i + 1) % 10 == 0 or n_ticks > 0:
                logger.info("Processed %s/%s markets | last: %s | ticks: %s", i + 1, len(markets_with_ticks), market_id, n_ticks)

        # Write index.csv
        index_path = out_dir / INDEX_FILENAME
        if index_rows:
            idx_df = pd.DataFrame(index_rows) if pd else None
            if idx_df is not None:
                idx_df.to_csv(index_path, index=False)
            else:
                keys = list(index_rows[0].keys())
                with open(index_path, "w", encoding="utf-8", newline="") as f:
                    f.write(",".join(keys) + "\n")
                    for r in index_rows:
                        f.write(",".join(str(r[k]) for k in keys) + "\n")

        # Execution report
        report_path = out_dir / REPORT_FILENAME
        total_size = sum(r["file_size_bytes"] for r in index_rows)
        report_lines = [
            "Tick data export – execution report",
            "======================================",
            f"Markets count: {len(index_rows)}",
            f"Total tick records: {total_ticks}",
            f"Total messages (distinct publish_time): {total_messages}",
            f"Period covered: {utc_ts(period_start)} to {utc_ts(period_end)}",
            f"Total size (data files): {total_size} bytes",
            f"Output format: {args.format}",
            f"Output directory: {out_dir}",
        ]
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        logger.info("Index written to %s", index_path)
        logger.info("Report written to %s", report_path)
        for line in report_lines:
            logger.info("  %s", line)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
