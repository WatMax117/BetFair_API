#!/usr/bin/env python3
"""
Export snapshots for Book Risk L3 (H/A/D).

Outputs long (Parquet) and wide (CSV) formats under:
  <PROJECT_ROOT>/data_exports/book_risk_l3/

Usage:
  python scripts/export_book_risk_l3.py --date-from 2026-02-01 --date-to 2026-02-16 [--market-ids 1.253489253] [--env vps]

Data source: PostgreSQL (market_derived_metrics + market_event_metadata + market_book_snapshots).
Requires: psycopg2-binary, pandas, pyarrow (pip install pandas pyarrow).
"""
from __future__ import annotations

import argparse
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

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data_exports" / "book_risk_l3"

# DB connection (same as backfill scripts)
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
PGOPTIONS = os.environ.get("PGOPTIONS", "-c search_path=public")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("export_book_risk_l3")


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


def fetch_snapshots(
    date_from: str,
    date_to: str,
    market_ids: Optional[list[str]] = None,
    event_ids: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Fetch snapshots from DB. Returns list of dicts (one per market_id, snapshot_at, side)."""
    conn = get_conn()
    try:
        sql = """
        SELECT
            d.market_id,
            d.snapshot_at,
            e.event_id,
            e.event_open_date AS event_start_time_utc,
            e.home_runner_name AS home_team_name,
            e.away_runner_name AS away_team_name,
            e.draw_runner_name AS draw_team_name,
            e.market_name AS market_type,
            e.home_selection_id,
            e.away_selection_id,
            e.draw_selection_id,
            d.total_volume,
            m.inplay AS in_play,
            m.status AS market_status,
            -- Home
            d.home_best_back AS home_back_odds_l1,
            d.home_best_back_size_l1 AS home_back_size_l1,
            d.home_back_odds_l2 AS home_back_odds_l2,
            d.home_back_size_l2 AS home_back_size_l2,
            d.home_back_odds_l3 AS home_back_odds_l3,
            d.home_back_size_l3 AS home_back_size_l3,
            -- Away
            d.away_best_back AS away_back_odds_l1,
            d.away_best_back_size_l1 AS away_back_size_l1,
            d.away_back_odds_l2 AS away_back_odds_l2,
            d.away_back_size_l2 AS away_back_size_l2,
            d.away_back_odds_l3 AS away_back_odds_l3,
            d.away_back_size_l3 AS away_back_size_l3,
            -- Draw
            d.draw_best_back AS draw_back_odds_l1,
            d.draw_best_back_size_l1 AS draw_back_size_l1,
            d.draw_back_odds_l2 AS draw_back_odds_l2,
            d.draw_back_size_l2 AS draw_back_size_l2,
            d.draw_back_odds_l3 AS draw_back_odds_l3,
            d.draw_back_size_l3 AS draw_back_size_l3
        FROM market_derived_metrics d
        JOIN market_event_metadata e ON e.market_id = d.market_id
        LEFT JOIN market_book_snapshots m ON m.snapshot_id = d.snapshot_id
        WHERE d.snapshot_at >= %s
          AND d.snapshot_at < %s
          AND e.home_selection_id IS NOT NULL
          AND e.away_selection_id IS NOT NULL
          AND e.draw_selection_id IS NOT NULL
        """
        params: list[Any] = [date_from, date_to]
        if market_ids:
            sql += " AND d.market_id = ANY(%s)"
            params.append(market_ids)
        if event_ids:
            sql += " AND e.event_id = ANY(%s)"
            params.append(event_ids)
        sql += " ORDER BY d.market_id, d.snapshot_at ASC"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _to_iso(ts) -> Optional[str]:
    if ts is None:
        return None
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def rows_to_long(rows: list[dict]) -> pd.DataFrame:
    """Convert raw rows to long/tidy format: one row per (market_id, snapshot_at_utc, side)."""
    records = []
    for r in rows:
        base = {
            "market_id": r["market_id"],
            "snapshot_at_utc": _to_iso(r["snapshot_at"]),
            "event_id": r.get("event_id"),
            "event_start_time_utc": _to_iso(r.get("event_start_time_utc")),
            "home_team_name": r.get("home_team_name"),
            "away_team_name": r.get("away_team_name"),
            "market_type": r.get("market_type") or "MATCH_ODDS",
            "total_volume": r.get("total_volume"),
            "market_status": r.get("market_status"),
            "in_play": r.get("in_play"),
        }
        for side, sid_key in [
            ("H", "home_selection_id"),
            ("A", "away_selection_id"),
            ("D", "draw_selection_id"),
        ]:
            sid = r.get(sid_key)
            if side == "H":
                sel_name = r.get("home_team_name") or ""
            elif side == "A":
                sel_name = r.get("away_team_name") or ""
            else:
                sel_name = r.get("draw_team_name") or "The Draw"
            prefix = "home" if side == "H" else "away" if side == "A" else "draw"
            rec = {
                **base,
                "selection_id": sid,
                "selection_name": sel_name,
                "side": side,
                "back_odds_l1": r.get(f"{prefix}_back_odds_l1"),
                "back_size_l1": r.get(f"{prefix}_back_size_l1"),
                "back_odds_l2": r.get(f"{prefix}_back_odds_l2"),
                "back_size_l2": r.get(f"{prefix}_back_size_l2"),
                "back_odds_l3": r.get(f"{prefix}_back_odds_l3"),
                "back_size_l3": r.get(f"{prefix}_back_size_l3"),
            }
            records.append(rec)
    return pd.DataFrame(records)


def rows_to_wide(rows: list[dict]) -> pd.DataFrame:
    """Convert raw rows to wide format: one row per (market_id, snapshot_at_utc) with H_*, A_*, D_* columns."""
    records = []
    for r in rows:
        rec = {
            "market_id": r["market_id"],
            "snapshot_at_utc": _to_iso(r["snapshot_at"]),
            "event_id": r.get("event_id"),
            "event_start_time_utc": _to_iso(r.get("event_start_time_utc")),
            "home_team_name": r.get("home_team_name"),
            "away_team_name": r.get("away_team_name"),
            "market_type": r.get("market_type") or "MATCH_ODDS",
            "total_volume": r.get("total_volume"),
            "market_status": r.get("market_status"),
            "in_play": r.get("in_play"),
            "H_selection_id": r.get("home_selection_id"),
            "A_selection_id": r.get("away_selection_id"),
            "D_selection_id": r.get("draw_selection_id"),
            "H_back_odds_l1": r.get("home_back_odds_l1"),
            "H_back_size_l1": r.get("home_back_size_l1"),
            "H_back_odds_l2": r.get("home_back_odds_l2"),
            "H_back_size_l2": r.get("home_back_size_l2"),
            "H_back_odds_l3": r.get("home_back_odds_l3"),
            "H_back_size_l3": r.get("home_back_size_l3"),
            "A_back_odds_l1": r.get("away_back_odds_l1"),
            "A_back_size_l1": r.get("away_back_size_l1"),
            "A_back_odds_l2": r.get("away_back_odds_l2"),
            "A_back_size_l2": r.get("away_back_size_l2"),
            "A_back_odds_l3": r.get("away_back_odds_l3"),
            "A_back_size_l3": r.get("away_back_size_l3"),
            "D_back_odds_l1": r.get("draw_back_odds_l1"),
            "D_back_size_l1": r.get("draw_back_size_l1"),
            "D_back_odds_l2": r.get("draw_back_odds_l2"),
            "D_back_size_l2": r.get("draw_back_size_l2"),
            "D_back_odds_l3": r.get("draw_back_odds_l3"),
            "D_back_size_l3": r.get("draw_back_size_l3"),
        }
        records.append(rec)
    return pd.DataFrame(records)


def compute_metadata(rows: list[dict], date_from: str, date_to: str, filters: dict) -> dict:
    """Build metadata JSON for the export run."""
    if not rows:
        return {
            "date_from_utc": date_from,
            "date_to_utc": date_to,
            "filters": filters,
            "record_count": 0,
            "snapshot_count": 0,
            "market_count": 0,
            "min_snapshot_at": None,
            "max_snapshot_at": None,
            "source": "PostgreSQL: market_derived_metrics + market_event_metadata + market_book_snapshots",
            "total_volume_field": "total_volume (market total matched at snapshot time)",
        }
    snaps = [r["snapshot_at"] for r in rows]
    markets = {r["market_id"] for r in rows}
    min_ts = min(snaps)
    max_ts = max(snaps)
    missing = {}
    for k in ["event_id", "event_start_time_utc", "home_team_name", "away_team_name", "total_volume"]:
        missing[k] = sum(1 for r in rows if r.get(k) is None)
    return {
        "date_from_utc": date_from,
        "date_to_utc": date_to,
        "filters": filters,
        "record_count": len(rows),
        "snapshot_count": len({(r["market_id"], r["snapshot_at"]) for r in rows}),
        "market_count": len(markets),
        "min_snapshot_at": _to_iso(min_ts),
        "max_snapshot_at": _to_iso(max_ts),
        "source": "PostgreSQL: market_derived_metrics + market_event_metadata + market_book_snapshots",
        "total_volume_field": "total_volume (market total matched at snapshot time)",
        "missing_counts": missing,
    }


def run_export(
    date_from: str,
    date_to: str,
    market_ids: Optional[list[str]] = None,
    event_ids: Optional[list[str]] = None,
    env: str = "local",
    max_rows_per_file: int = 500_000,
) -> None:
    if pd is None:
        raise RuntimeError("pandas required. pip install pandas pyarrow")
    start = datetime.now(timezone.utc)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = start.strftime("%Y-%m-%d%H%M%S")
    base_name = f"book_risk_l3__{env}{ts_str}"

    log_file = OUTPUT_DIR / f"{base_name}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    try:
        logger.info("Export Book Risk L3: date_from=%s date_to=%s market_ids=%s event_ids=%s", date_from, date_to, market_ids, event_ids)
        rows = fetch_snapshots(date_from, date_to, market_ids, event_ids)
        logger.info("Fetched %d snapshots", len(rows))

        if not rows:
            logger.warning("No snapshots in range")
            meta = compute_metadata(rows, date_from, date_to, {"market_ids": market_ids, "event_ids": event_ids})
            with open(OUTPUT_DIR / f"{base_name}__metadata.json", "w") as f:
                json.dump(meta, f, indent=2)
            return

        # Deduplicate (market_id, snapshot_at) - keep first (chronological order)
        seen = {}
        for r in rows:
            key = (r["market_id"], r["snapshot_at"])
            if key not in seen:
                seen[key] = r
        orig_len = len(rows)
        rows = list(seen.values())
        if len(rows) < orig_len:
            logger.warning("Deduplicated %d -> %d rows", orig_len, len(rows))

        meta = compute_metadata(rows, date_from, date_to, {"market_ids": market_ids, "event_ids": event_ids})
        with open(OUTPUT_DIR / f"{base_name}__metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

        # Long format (Parquet)
        df_long = rows_to_long(rows)
        for i in range(0, len(df_long), max_rows_per_file):
            part = df_long.iloc[i : i + max_rows_per_file]
            part_num = i // max_rows_per_file + 1
            out_path = OUTPUT_DIR / f"{base_name}__part{part_num}.parquet"
            part.to_parquet(out_path, index=False)
            logger.info("Wrote long %s (%d rows)", out_path.name, len(part))

        # Wide format (CSV)
        df_wide = rows_to_wide(rows)
        for i in range(0, len(df_wide), max_rows_per_file):
            part = df_wide.iloc[i : i + max_rows_per_file]
            part_num = i // max_rows_per_file + 1
            out_path = OUTPUT_DIR / f"{base_name}__part{part_num}.csv"
            part.to_csv(out_path, index=False, float_format="%.6g")
            logger.info("Wrote wide %s (%d rows)", out_path.name, len(part))

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info("Export complete in %.1fs; %d snapshots", elapsed, len(rows))
    finally:
        logger.removeHandler(file_handler)


def main():
    ap = argparse.ArgumentParser(description="Export Book Risk L3 snapshots to Parquet and CSV")
    ap.add_argument("--date-from", required=True, help="Start date (UTC, inclusive) YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    ap.add_argument("--date-to", required=True, help="End date (UTC, exclusive) YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    ap.add_argument("--market-ids", nargs="*", help="Optional market IDs to filter")
    ap.add_argument("--event-ids", nargs="*", help="Optional event IDs to filter")
    ap.add_argument("--env", default="local", help="Environment tag for filename (default: local)")
    ap.add_argument("--max-rows-per-file", type=int, default=500_000, help="Split output every N rows (default 500000)")
    args = ap.parse_args()

    # Normalize dates to ISO
    for attr in ("date_from", "date_to"):
        v = getattr(args, attr)
        if len(v) == 10:
            v = v + "T00:00:00Z"
        elif "Z" not in v and "+" not in v:
            v = v + "Z"
        setattr(args, attr, v)

    if not POSTGRES_PASSWORD and os.environ.get("POSTGRES_REST_WRITER_PASSWORD"):
        os.environ["POSTGRES_PASSWORD"] = os.environ["POSTGRES_REST_WRITER_PASSWORD"]

    if not POSTGRES_PASSWORD:
        logger.error("POSTGRES_PASSWORD not set")
        sys.exit(1)

    run_export(
        date_from=args.date_from,
        date_to=args.date_to,
        market_ids=args.market_ids or None,
        event_ids=args.event_ids or None,
        env=args.env,
        max_rows_per_file=args.max_rows_per_file,
    )


if __name__ == "__main__":
    main()
