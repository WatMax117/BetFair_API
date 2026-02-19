#!/usr/bin/env python3
"""
Diagnose and inventory collected market parameters.

Pure diagnostic analysis: market types, event coverage, selections, data density,
ladder depth, traded data, field completeness.

Usage:
  python scripts/diagnose_market_inventory.py --date 2026-02-16 --output-dir /opt/netbet/data_exports/diagnostics

Requires: psycopg2-binary, pandas.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("diagnose_market_inventory")

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


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    """Write CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        if not rows:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        else:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def market_type_inventory(conn, start_utc: datetime, end_utc: datetime) -> list[dict]:
    """A. Market Type Inventory"""
    query = """
    WITH ladder_stats AS (
        SELECT
            m.market_type,
            COUNT(DISTINCT ll.market_id) AS distinct_markets,
            COUNT(DISTINCT m.event_id) AS distinct_events,
            COUNT(*) AS ladder_rows
        FROM stream_ingest.ladder_levels ll
        JOIN public.markets m ON m.market_id = ll.market_id
        WHERE ll.publish_time >= %s AND ll.publish_time < %s
        GROUP BY m.market_type
    ),
    traded_stats AS (
        SELECT
            m.market_type,
            COUNT(*) AS traded_rows
        FROM stream_ingest.traded_volume tv
        JOIN public.markets m ON m.market_id = tv.market_id
        WHERE tv.publish_time >= %s AND tv.publish_time < %s
        GROUP BY m.market_type
    ),
    market_durations AS (
        SELECT
            m.market_type,
            ll.market_id,
            COUNT(*) AS rows_per_market,
            EXTRACT(EPOCH FROM (MAX(ll.publish_time) - MIN(ll.publish_time))) AS duration_seconds
        FROM stream_ingest.ladder_levels ll
        JOIN public.markets m ON m.market_id = ll.market_id
        WHERE ll.publish_time >= %s AND ll.publish_time < %s
        GROUP BY m.market_type, ll.market_id
    ),
    runner_counts AS (
        SELECT
            m.market_type,
            m.market_id,
            COUNT(DISTINCT r.selection_id) AS runner_count
        FROM public.markets m
        JOIN public.runners r ON r.market_id = m.market_id
        GROUP BY m.market_type, m.market_id
    ),
    in_play_stats AS (
        SELECT
            m.market_type,
            COUNT(*) FILTER (WHERE lc.in_play = true) AS in_play_count,
            COUNT(*) AS total_lifecycle_rows
        FROM stream_ingest.market_lifecycle_events lc
        JOIN public.markets m ON m.market_id = lc.market_id
        WHERE lc.publish_time >= %s AND lc.publish_time < %s
        GROUP BY m.market_type
    )
    SELECT
        COALESCE(ls.market_type, ts.market_type) AS market_type,
        COALESCE(ls.distinct_markets, 0) AS count_distinct_market_id,
        COALESCE(ls.distinct_events, 0) AS count_distinct_event_id,
        COALESCE(ls.ladder_rows, 0) + COALESCE(ts.traded_rows, 0) AS total_tick_rows,
        COALESCE(ls.ladder_rows, 0) AS total_ladder_rows,
        COALESCE(ts.traded_rows, 0) AS total_traded_rows,
        CASE WHEN COALESCE(ls.distinct_markets, 0) > 0
             THEN (COALESCE(ls.ladder_rows, 0) + COALESCE(ts.traded_rows, 0))::numeric / ls.distinct_markets
             ELSE 0 END AS average_rows_per_market,
        CASE WHEN COALESCE(ls.distinct_markets, 0) > 0 AND COALESCE(md.avg_duration, 0) > 0
             THEN (COALESCE(ls.ladder_rows, 0) + COALESCE(ts.traded_rows, 0))::numeric / ls.distinct_markets / NULLIF(md.avg_duration, 0)
             ELSE 0 END AS average_update_rate_per_market,
        COALESCE(rc.avg_runners, 0) AS average_number_of_runners,
        CASE WHEN COALESCE(ips.total_lifecycle_rows, 0) > 0
             THEN (ips.in_play_count::numeric / ips.total_lifecycle_rows * 100)
             ELSE 0 END AS in_play_ratio
    FROM ladder_stats ls
    FULL OUTER JOIN traded_stats ts ON ls.market_type = ts.market_type
    LEFT JOIN (
        SELECT market_type, AVG(duration_seconds) AS avg_duration
        FROM market_durations
        GROUP BY market_type
    ) md ON COALESCE(ls.market_type, ts.market_type) = md.market_type
    LEFT JOIN (
        SELECT market_type, AVG(runner_count) AS avg_runners
        FROM runner_counts
        GROUP BY market_type
    ) rc ON COALESCE(ls.market_type, ts.market_type) = rc.market_type
    LEFT JOIN in_play_stats ips ON COALESCE(ls.market_type, ts.market_type) = ips.market_type
    ORDER BY COALESCE(ls.market_type, ts.market_type)
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (start_utc, end_utc, start_utc, end_utc, start_utc, end_utc, start_utc, end_utc))
        return [dict(row) for row in cur.fetchall()]


def event_market_mapping(conn, start_utc: datetime, end_utc: datetime) -> list[dict]:
    """B. Event-Level Market Mapping"""
    query = """
    WITH event_markets AS (
        SELECT
            e.event_id,
            e.event_name,
            m.market_type,
            m.market_id,
            COUNT(DISTINCT ll.publish_time) AS tick_count
        FROM public.events e
        JOIN public.markets m ON m.event_id = e.event_id
        LEFT JOIN stream_ingest.ladder_levels ll ON ll.market_id = m.market_id
            AND ll.publish_time >= %s AND ll.publish_time < %s
        GROUP BY e.event_id, e.event_name, m.market_type, m.market_id
    ),
    event_summary AS (
        SELECT
            event_id,
            event_name,
            STRING_AGG(DISTINCT market_type, ', ' ORDER BY market_type) AS market_types_list,
            COUNT(DISTINCT market_id) AS total_markets,
            SUM(tick_count) AS total_rows
        FROM event_markets
        GROUP BY event_id, event_name
    ),
    time_bounds AS (
        SELECT
            e.event_id,
            MIN(ll.publish_time) AS earliest_publish_time,
            MAX(ll.publish_time) AS latest_publish_time
        FROM public.events e
        JOIN public.markets m ON m.event_id = e.event_id
        JOIN stream_ingest.ladder_levels ll ON ll.market_id = m.market_id
        WHERE ll.publish_time >= %s AND ll.publish_time < %s
        GROUP BY e.event_id
    )
    SELECT
        es.event_id,
        es.event_name,
        es.market_types_list,
        es.total_markets,
        es.total_rows,
        tb.earliest_publish_time::text AS earliest_publish_time,
        tb.latest_publish_time::text AS latest_publish_time
    FROM event_summary es
    LEFT JOIN time_bounds tb ON es.event_id = tb.event_id
    ORDER BY es.event_id
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (start_utc, end_utc, start_utc, end_utc))
        return [dict(row) for row in cur.fetchall()]


def ladder_depth_diagnostics(conn, start_utc: datetime, end_utc: datetime) -> list[dict]:
    """C. Ladder Depth Diagnostics"""
    query = """
    WITH level_distribution AS (
        SELECT
            m.market_type,
            ll.level,
            COUNT(*) AS row_count
        FROM stream_ingest.ladder_levels ll
        JOIN public.markets m ON m.market_id = ll.market_id
        WHERE ll.publish_time >= %s AND ll.publish_time < %s
        GROUP BY m.market_type, ll.level
    ),
    market_type_totals AS (
        SELECT
            market_type,
            SUM(row_count) AS total_rows,
            MAX(level) AS max_level,
            MIN(level) AS min_level,
            SUM(CASE WHEN level = 0 THEN row_count ELSE 0 END) AS level_0_rows,
            SUM(CASE WHEN level >= 3 THEN row_count ELSE 0 END) AS level_ge_3_rows,
            SUM(CASE WHEN level >= 7 THEN row_count ELSE 0 END) AS level_ge_7_rows
        FROM level_distribution
        GROUP BY market_type
    )
    SELECT
        market_type,
        max_level,
        min_level,
        total_rows,
        CASE WHEN total_rows > 0 THEN (level_0_rows::numeric / total_rows * 100) ELSE 0 END AS pct_level_0_only,
        CASE WHEN total_rows > 0 THEN (level_ge_3_rows::numeric / total_rows * 100) ELSE 0 END AS pct_level_ge_3,
        CASE WHEN total_rows > 0 THEN (level_ge_7_rows::numeric / total_rows * 100) ELSE 0 END AS pct_level_ge_7
    FROM market_type_totals
    ORDER BY market_type
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (start_utc, end_utc,))
        return [dict(row) for row in cur.fetchall()]


def traded_volume_diagnostics(conn, start_utc: datetime, end_utc: datetime) -> list[dict]:
    """D. Traded Volume Diagnostics"""
    query = """
    WITH all_rows AS (
        SELECT
            m.market_type,
            ll.market_id,
            ll.publish_time,
            NULL::numeric AS traded_volume
        FROM stream_ingest.ladder_levels ll
        JOIN public.markets m ON m.market_id = ll.market_id
        WHERE ll.publish_time >= %s AND ll.publish_time < %s
        UNION ALL
        SELECT
            m.market_type,
            tv.market_id,
            tv.publish_time,
            tv.size_traded AS traded_volume
        FROM stream_ingest.traded_volume tv
        JOIN public.markets m ON m.market_id = tv.market_id
        WHERE tv.publish_time >= %s AND tv.publish_time < %s
    ),
    market_type_stats AS (
        SELECT
            market_type,
            COUNT(*) AS total_rows,
            COUNT(*) FILTER (WHERE traded_volume IS NOT NULL) AS rows_with_traded_volume
        FROM all_rows
        GROUP BY market_type
    ),
    traded_deltas AS (
        SELECT
            m.market_type,
            tv.market_id,
            tv.publish_time,
            tv.size_traded,
            LAG(tv.size_traded) OVER (PARTITION BY tv.market_id ORDER BY tv.publish_time) AS prev_traded,
            EXTRACT(EPOCH FROM (tv.publish_time - LAG(tv.publish_time) OVER (PARTITION BY tv.market_id ORDER BY tv.publish_time))) AS delta_seconds
        FROM stream_ingest.traded_volume tv
        JOIN public.markets m ON m.market_id = tv.market_id
        WHERE tv.publish_time >= %s AND tv.publish_time < %s
    ),
    delta_stats AS (
        SELECT
            market_type,
            AVG(CASE WHEN delta_seconds > 0 AND delta_seconds IS NOT NULL THEN ABS(size_traded - prev_traded) / delta_seconds ELSE NULL END) AS avg_delta_per_second,
            MAX(ABS(size_traded - COALESCE(prev_traded, 0))) AS max_delta_observed
        FROM traded_deltas
        WHERE prev_traded IS NOT NULL AND delta_seconds > 0
        GROUP BY market_type
    )
    SELECT
        mts.market_type,
        CASE WHEN mts.total_rows > 0 THEN (mts.rows_with_traded_volume::numeric / mts.total_rows * 100) ELSE 0 END AS pct_rows_with_traded_volume,
        COALESCE(ds.avg_delta_per_second, 0) AS avg_traded_volume_delta_per_second,
        COALESCE(ds.max_delta_observed, 0) AS max_traded_volume_delta_observed
    FROM market_type_stats mts
    LEFT JOIN delta_stats ds ON mts.market_type = ds.market_type
    ORDER BY mts.market_type
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (start_utc, end_utc, start_utc, end_utc, start_utc, end_utc))
        return [dict(row) for row in cur.fetchall()]


def market_update_frequency(conn, start_utc: datetime, end_utc: datetime) -> list[dict]:
    """E. Update Frequency Analysis"""
    query = """
    WITH market_times AS (
        SELECT
            m.market_id,
            m.market_type,
            ll.publish_time,
            LAG(ll.publish_time) OVER (PARTITION BY ll.market_id ORDER BY ll.publish_time) AS prev_publish_time,
            EXTRACT(EPOCH FROM (ll.publish_time - LAG(ll.publish_time) OVER (PARTITION BY ll.market_id ORDER BY ll.publish_time))) AS inter_update_seconds
        FROM stream_ingest.ladder_levels ll
        JOIN public.markets m ON m.market_id = ll.market_id
        WHERE ll.publish_time >= %s AND ll.publish_time < %s
    ),
    market_stats AS (
        SELECT
            market_id,
            market_type,
            COUNT(*) AS total_rows,
            EXTRACT(EPOCH FROM (MAX(publish_time) - MIN(publish_time))) AS duration_seconds,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY inter_update_seconds) AS median_inter_update,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY inter_update_seconds) AS p95_inter_update
        FROM market_times
        GROUP BY market_id, market_type
    )
    SELECT
        market_id,
        market_type,
        CASE WHEN duration_seconds > 0 THEN total_rows / duration_seconds ELSE 0 END AS rows_per_second,
        median_inter_update,
        p95_inter_update
    FROM market_stats
    ORDER BY rows_per_second DESC
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (start_utc, end_utc,))
        return [dict(row) for row in cur.fetchall()]


def distinct_values_check(conn, start_utc: datetime, end_utc: datetime) -> dict[str, list]:
    """Check distinct values for various fields"""
    results = {}
    
    queries = {
        "market_type": """
            SELECT DISTINCT market_type FROM public.markets ORDER BY market_type
        """,
        "market_status": """
            SELECT DISTINCT status AS market_status 
            FROM stream_ingest.market_lifecycle_events
            WHERE publish_time >= %s AND publish_time < %s
            ORDER BY status
        """,
        "change_type": """
            SELECT DISTINCT 'update' AS change_type
            -- change_type is hardcoded in our export, but check if any variation exists
        """,
        "record_type": """
            SELECT DISTINCT 'ladder' AS record_type
            UNION
            SELECT DISTINCT 'traded_volume' AS record_type
            ORDER BY record_type
        """,
    }
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for key, query in queries.items():
            if '%s' in query:
                cur.execute(query, (start_utc, end_utc))
            else:
                cur.execute(query)
            results[key] = [row[list(row.keys())[0]] for row in cur.fetchall()]
    
    # Check for NEXT_GOAL variations
    next_goal_query = """
        SELECT DISTINCT market_type
        FROM public.markets
        WHERE UPPER(market_type) LIKE '%NEXT%' OR UPPER(market_type) LIKE '%GOAL%'
        ORDER BY market_type
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(next_goal_query)
        results["next_goal_variations"] = [row["market_type"] for row in cur.fetchall()]
    
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose and inventory collected market parameters."
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
        default=Path("/opt/netbet/data_exports/diagnostics"),
        help="Output directory",
    )
    args = parser.parse_args()

    try:
        start_utc, end_utc = parse_utc_date(args.date)
    except ValueError as e:
        logger.error("Invalid date format: %s. Use YYYY-MM-DD", e)
        return 1

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Date window: [%s, %s)", start_utc.isoformat(), end_utc.isoformat())
    logger.info("Output directory: %s", output_dir)

    start_time = time.perf_counter()
    conn = get_conn()

    try:
        # A. Market Type Inventory
        logger.info("Generating market type inventory...")
        market_type_rows = market_type_inventory(conn, start_utc, end_utc)
        write_csv(
            output_dir / f"market_type_inventory_{args.date.replace('-', '_')}.csv",
            market_type_rows,
            list(market_type_rows[0].keys()) if market_type_rows else [],
        )

        # B. Event Market Mapping
        logger.info("Generating event market mapping...")
        event_rows = event_market_mapping(conn, start_utc, end_utc)
        write_csv(
            output_dir / f"event_market_mapping_{args.date.replace('-', '_')}.csv",
            event_rows,
            list(event_rows[0].keys()) if event_rows else [],
        )

        # C. Ladder Depth Diagnostics
        logger.info("Generating ladder depth diagnostics...")
        ladder_rows = ladder_depth_diagnostics(conn, start_utc, end_utc)
        write_csv(
            output_dir / f"ladder_depth_diagnostics_{args.date.replace('-', '_')}.csv",
            ladder_rows,
            list(ladder_rows[0].keys()) if ladder_rows else [],
        )

        # D. Traded Volume Diagnostics
        logger.info("Generating traded volume diagnostics...")
        traded_rows = traded_volume_diagnostics(conn, start_utc, end_utc)
        write_csv(
            output_dir / f"traded_volume_diagnostics_{args.date.replace('-', '_')}.csv",
            traded_rows,
            list(traded_rows[0].keys()) if traded_rows else [],
        )

        # E. Update Frequency Analysis
        logger.info("Generating update frequency analysis...")
        freq_rows = market_update_frequency(conn, start_utc, end_utc)
        write_csv(
            output_dir / f"market_update_frequency_{args.date.replace('-', '_')}.csv",
            freq_rows,
            list(freq_rows[0].keys()) if freq_rows else [],
        )

        # Distinct Values Check
        logger.info("Checking distinct values...")
        distinct_vals = distinct_values_check(conn, start_utc, end_utc)

        # Summary Report
        total_rows = sum(r.get("total_tick_rows", 0) or 0 for r in market_type_rows)
        total_markets = sum(r.get("count_distinct_market_id", 0) or 0 for r in market_type_rows)
        total_events = len(event_rows)

        duration_sec = time.perf_counter() - start_time

        report_lines = [
            "Market Inventory Diagnostics Report",
            "====================================",
            f"Date: {args.date} (UTC)",
            f"Start: {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"End: {end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "",
            "Summary:",
            f"  Total rows scanned: {total_rows:,}",
            f"  Total markets: {total_markets:,}",
            f"  Total events: {total_events:,}",
            f"  Runtime: {duration_sec:.2f} seconds",
            "",
            "Market Types Found:",
        ]
        for row in market_type_rows:
            report_lines.append(f"  - {row.get('market_type', 'N/A')}: {row.get('count_distinct_market_id', 0)} markets, {row.get('total_tick_rows', 0):,} rows")

        report_lines.extend([
            "",
            "Distinct Values:",
            f"  market_type: {', '.join(distinct_vals.get('market_type', []))}",
            f"  market_status: {', '.join(distinct_vals.get('market_status', []))}",
            f"  record_type: {', '.join(distinct_vals.get('record_type', []))}",
            "",
            "NEXT_GOAL Variations:",
        ])
        if distinct_vals.get("next_goal_variations"):
            for mt in distinct_vals["next_goal_variations"]:
                report_lines.append(f"  - {mt}")
        else:
            report_lines.append("  None found")

        report_lines.extend([
            "",
            "Output Files:",
            f"  market_type_inventory_{args.date.replace('-', '_')}.csv",
            f"  event_market_mapping_{args.date.replace('-', '_')}.csv",
            f"  ladder_depth_diagnostics_{args.date.replace('-', '_')}.csv",
            f"  traded_volume_diagnostics_{args.date.replace('-', '_')}.csv",
            f"  market_update_frequency_{args.date.replace('-', '_')}.csv",
            f"  distinct_values_{args.date.replace('-', '_')}.txt",
        ])

        report_path = output_dir / f"diagnostics_report_{args.date.replace('-', '_')}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        # Write distinct values to separate file
        distinct_path = output_dir / f"distinct_values_{args.date.replace('-', '_')}.txt"
        with open(distinct_path, "w", encoding="utf-8") as f:
            f.write("Distinct Values Inventory\n")
            f.write("========================\n\n")
            for key, values in distinct_vals.items():
                f.write(f"{key}:\n")
                for v in values:
                    f.write(f"  - {v}\n")
                f.write("\n")

        logger.info("Diagnostics complete. Report: %s", report_path)
        for line in report_lines:
            logger.info("  %s", line)

        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
