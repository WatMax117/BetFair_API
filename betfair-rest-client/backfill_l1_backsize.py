#!/usr/bin/env python3
"""
One-time backfill: populate *_best_back_size_l1 from raw_payload in market_book_snapshots.

Per runner: extract availableToBack[0].size (best back level size) and update market_derived_metrics.
Only updates rows where current value is NULL. Does not overwrite non-NULL values.
Leaves NULL where raw ladder has no L1 back level for that runner.

Usage (same env as rest client; use search_path=public for VPS):
  python backfill_l1_backsize.py [--limit 10000] [--batch-size 100] [--dry-run]
"""
import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

POSTGRES_HOST = os.environ.get("POSTGRES_HOST") or os.environ.get("BF_POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT") or os.environ.get("BF_POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
PGOPTIONS = os.environ.get("PGOPTIONS", "-c search_path=public")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("backfill_l1_backsize")


def _safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _l1_back_size(runner: Any) -> Optional[float]:
    """Extract availableToBack[0].size from runner. Returns None if missing or invalid."""
    ex = runner.get("ex") if isinstance(runner, dict) else getattr(runner, "ex", None)
    if not ex:
        return None
    atb = ex.get("availableToBack") if isinstance(ex, dict) else getattr(ex, "availableToBack", None) or getattr(ex, "available_to_back", None)
    if not atb or len(atb) < 1:
        return None
    lev = atb[0]
    if isinstance(lev, (list, tuple)) and len(lev) >= 2:
        price = _safe_float(lev[0])
        size = _safe_float(lev[1])
    elif isinstance(lev, dict):
        price = _safe_float(lev.get("price") or lev.get("Price"))
        size = _safe_float(lev.get("size") or lev.get("Size") or 0)
    else:
        return None
    if price <= 1 or size <= 0:
        return None
    return size


def _runner_l1_back_sizes(runners: list, runner_metadata: Dict) -> Optional[Dict[str, Optional[float]]]:
    """Build home/away/draw_best_back_size_l1 per role. Returns None if metadata incomplete."""
    if not runner_metadata or len(runner_metadata) < 3:
        return None
    by_sid = {}
    for r in runners:
        sid = r.get("selectionId") if isinstance(r, dict) else getattr(r, "selectionId", None) or getattr(r, "selection_id", None)
        if sid is not None:
            by_sid[int(sid) if isinstance(sid, (int, float)) else sid] = r
    out = {}
    for sid_key, role in runner_metadata.items():
        sid_key = int(sid_key) if isinstance(sid_key, (int, float)) else sid_key
        role_lower = (role or "").lower()
        if role_lower not in ("home", "away", "draw"):
            continue
        r = by_sid.get(sid_key)
        if not r:
            out[f"{role_lower}_best_back_size_l1"] = None
            continue
        out[f"{role_lower}_best_back_size_l1"] = _l1_back_size(r)
    if len(out) < 3:
        return None
    return out


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


def get_runner_metadata(conn, market_id: str) -> Optional[Dict]:
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


def run_backfill(limit: int = 10000, batch_size: int = 100, dry_run: bool = False) -> tuple[int, int, int]:
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
                WHERE d.home_best_back_size_l1 IS NULL
                   OR d.away_best_back_size_l1 IS NULL
                   OR d.draw_best_back_size_l1 IS NULL
                ORDER BY m.snapshot_at ASC
                LIMIT %s
                """,
                (max(1, limit),),
            )
            rows = cur.fetchall()

        logger.info("Found %s snapshots needing L1 backsize backfill", len(rows))

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
            if not runners or not isinstance(runners, list) or len(runners) < 3:
                skipped += 1
                continue
            meta = get_runner_metadata(conn, market_id)
            if not meta:
                skipped += 1
                continue
            ladder = _runner_l1_back_sizes(runners, meta)
            if not ladder:
                skipped += 1
                continue

            h = ladder.get("home_best_back_size_l1")
            a = ladder.get("away_best_back_size_l1")
            d = ladder.get("draw_best_back_size_l1")
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
                    SET home_best_back_size_l1 = COALESCE(home_best_back_size_l1, %s),
                        away_best_back_size_l1 = COALESCE(away_best_back_size_l1, %s),
                        draw_best_back_size_l1 = COALESCE(draw_best_back_size_l1, %s)
                    WHERE snapshot_id = %s
                      AND (home_best_back_size_l1 IS NULL OR away_best_back_size_l1 IS NULL OR draw_best_back_size_l1 IS NULL)
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
    ap = argparse.ArgumentParser(description="Backfill *_best_back_size_l1 into market_derived_metrics from raw_payload")
    ap.add_argument("--limit", type=int, default=10000, help="Max snapshots to process (default 10000)")
    ap.add_argument("--batch-size", type=int, default=100, help="Commit every N rows (default 100)")
    ap.add_argument("--dry-run", action="store_true", help="Only log what would be updated")
    args = ap.parse_args()
    if not POSTGRES_PASSWORD:
        logger.error("POSTGRES_PASSWORD not set")
        sys.exit(1)
    updated, skipped, errors = run_backfill(limit=args.limit, batch_size=args.batch_size, dry_run=args.dry_run)
    logger.info("Backfill complete: updated=%s skipped=%s errors=%s", updated, skipped, errors)


if __name__ == "__main__":
    main()
