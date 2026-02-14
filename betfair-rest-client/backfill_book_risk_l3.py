#!/usr/bin/env python3
"""
One-time backfill: compute Book Risk L3 from raw_payload in market_book_snapshots
and write home/away/draw into public.market_derived_metrics for rows where book_risk_l3 is null.

Book Risk L3 requires ex.availableToBack ladders (top 3 levels) per runner. raw_payload contains
runners with ex.availableToBack - same structure used by impedance backfill.

Usage (same env as rest client; use search_path=public for VPS):
  python backfill_book_risk_l3.py [--limit 1000] [--batch-size 100] [--dry-run]
  Or: docker compose run --rm -e PGOPTIONS=-c search_path=public -e POSTGRES_HOST=netbet-postgres \
        betfair-rest-client python backfill_book_risk_l3.py --limit 5000
"""
import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# Use same env as main.py
POSTGRES_HOST = os.environ.get("POSTGRES_HOST") or os.environ.get("BF_POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT") or os.environ.get("BF_POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
PGOPTIONS = os.environ.get("PGOPTIONS", "-c search_path=public")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("backfill_book_risk_l3")

from risk import compute_book_risk_l3  # noqa: E402


def get_conn():
    kwargs = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": POSTGRES_DB,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "connect_timeout": 10,
    }
    if PGOPTIONS:
        kwargs["options"] = PGOPTIONS
    return psycopg2.connect(**kwargs)


def get_runner_metadata(conn, market_id: str) -> Optional[Dict[Any, str]]:
    """selection_id -> HOME | AWAY | DRAW from public.market_event_metadata."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT home_selection_id, away_selection_id, draw_selection_id
            FROM public.market_event_metadata WHERE market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
    if not row or row.get("home_selection_id") is None or row.get("away_selection_id") is None or row.get("draw_selection_id") is None:
        return None
    return {
        row["home_selection_id"]: "HOME",
        row["away_selection_id"]: "AWAY",
        row["draw_selection_id"]: "DRAW",
    }


def run_backfill(limit: int = 1000, batch_size: int = 100, dry_run: bool = False) -> tuple[int, int, int]:
    """
    Backfill Book Risk L3 for snapshots where any of home/away/draw_book_risk_l3 is null.
    Returns (updated, skipped, errors).
    """
    conn = get_conn()
    updated = 0
    skipped = 0
    errors = 0
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT m.snapshot_id, m.market_id, m.snapshot_at, m.raw_payload
                FROM public.market_book_snapshots m
                INNER JOIN public.market_derived_metrics d ON d.snapshot_id = m.snapshot_id
                WHERE d.home_book_risk_l3 IS NULL
                   OR d.away_book_risk_l3 IS NULL
                   OR d.draw_book_risk_l3 IS NULL
                ORDER BY m.snapshot_at ASC
                LIMIT %s
                """,
                (max(1, limit),),
            )
            rows = cur.fetchall()

        logger.info("Found %s snapshots needing backfill", len(rows))
        depth_limit = int(os.environ.get("BF_DEPTH_LIMIT", "3"))

        for i, r in enumerate(rows):
            snapshot_id = r["snapshot_id"]
            market_id = r["market_id"]
            raw = r["raw_payload"]
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    logger.warning("snapshot_id=%s: invalid JSON raw_payload", snapshot_id)
                    errors += 1
                    continue
            runners = (raw.get("runners") or raw.get("Runners")) if isinstance(raw, dict) else []
            if not runners or not isinstance(runners, list):
                skipped += 1
                continue
            if len(runners) < 3:
                skipped += 1
                continue
            meta = get_runner_metadata(conn, market_id)
            if not meta:
                skipped += 1
                continue
            out = compute_book_risk_l3(runners, meta, depth_limit=depth_limit)
            if not out:
                skipped += 1
                continue
            h = out.get("home_book_risk_l3")
            a = out.get("away_book_risk_l3")
            d = out.get("draw_book_risk_l3")
            if h is None and a is None and d is None:
                skipped += 1
                continue

            if dry_run:
                logger.info(
                    "dry-run: snapshot_id=%s market_id=%s -> H=%s A=%s D=%s",
                    snapshot_id, market_id, h, a, d,
                )
                updated += 1
                continue

            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.market_derived_metrics
                    SET home_book_risk_l3 = %s, away_book_risk_l3 = %s, draw_book_risk_l3 = %s
                    WHERE snapshot_id = %s
                    """,
                    (h, a, d, snapshot_id),
                )
                if cur.rowcount:
                    updated += 1

            if (i + 1) % batch_size == 0:
                conn.commit()
                logger.info("Progress: %s processed, %s updated", i + 1, updated)

        conn.commit()
    except Exception as e:
        logger.exception("Backfill failed: %s", e)
        errors += 1
    finally:
        conn.close()
    return updated, skipped, errors


def main():
    ap = argparse.ArgumentParser(description="Backfill Book Risk L3 into market_derived_metrics from raw_payload")
    ap.add_argument("--limit", type=int, default=10000, help="Max snapshots to process (default 10000)")
    ap.add_argument("--batch-size", type=int, default=100, help="Commit every N rows (default 100)")
    ap.add_argument("--dry-run", action="store_true", help="Only log what would be updated")
    args = ap.parse_args()
    if not POSTGRES_PASSWORD:
        logger.error("POSTGRES_PASSWORD not set")
        sys.exit(1)
    updated, skipped, errors = run_backfill(limit=args.limit, batch_size=args.batch_size, dry_run=args.dry_run)
    logger.info("Backfill complete: updated=%s skipped=%s errors=%s", updated, skipped, errors)
    if not args.dry_run and updated == 0 and errors == 0:
        logger.warning(
            "No rows updated. Check that snapshots have raw_payload.runners with ex.availableToBack "
            "and market_event_metadata has HOME/AWAY/DRAW mapping."
        )


if __name__ == "__main__":
    main()
