#!/usr/bin/env python3
"""
One-time backfill: compute L2/L3 ladder fields from raw_payload in market_book_snapshots
and update public.market_derived_metrics for rows where L2/L3 are NULL.

Extracts availableToBack[1] (L2) and availableToBack[2] (L3) per runner; maps to HOME/AWAY/DRAW
via market_event_metadata. Same logic as main.py _back_level_at / _runner_best_prices.

Usage (same env as rest client; use search_path=public for VPS):
  python backfill_ladder_levels.py [--limit 10000] [--batch-size 100] [--dry-run]
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
logger = logging.getLogger("backfill_ladder_levels")


def _safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _back_level_at(runner: Any, level: int) -> tuple:
    """Extract (price, size) from availableToBack level index (0=L1, 1=L2, 2=L3). Returns (0.0, 0.0) if missing."""
    ex = runner.get("ex") if isinstance(runner, dict) else getattr(runner, "ex", None)
    if not ex:
        return 0.0, 0.0
    atb = ex.get("availableToBack") if isinstance(ex, dict) else getattr(ex, "availableToBack", None) or getattr(ex, "available_to_back", None)
    if not atb or level >= len(atb):
        return 0.0, 0.0
    lev = atb[level]
    if isinstance(lev, (list, tuple)) and len(lev) >= 2:
        price = _safe_float(lev[0])
        size = _safe_float(lev[1])
    elif isinstance(lev, dict):
        price = _safe_float(lev.get("price") or lev.get("Price"))
        size = _safe_float(lev.get("size") or lev.get("Size") or 0)
    else:
        return 0.0, 0.0
    if price <= 1 or size <= 0:
        return 0.0, 0.0
    return price, size


def _runner_l2_l3(runners: list, runner_metadata: Dict) -> Optional[Dict[str, Any]]:
    """Build L2/L3 ladder fields per role. Returns dict with home/away/draw _back_odds_l2, _back_size_l2, etc."""
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
            continue
        odds_l2, size_l2 = _back_level_at(r, 1)
        odds_l3, size_l3 = _back_level_at(r, 2)
        out[f"{role_lower}_back_odds_l2"] = odds_l2 if odds_l2 > 0 else None
        out[f"{role_lower}_back_size_l2"] = size_l2 if size_l2 > 0 else None
        out[f"{role_lower}_back_odds_l3"] = odds_l3 if odds_l3 > 0 else None
        out[f"{role_lower}_back_size_l3"] = size_l3 if size_l3 > 0 else None
    if len(out) < 12:  # need all 3 roles x 4 fields
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
                WHERE d.home_back_odds_l2 IS NULL
                   OR d.home_back_odds_l3 IS NULL
                ORDER BY m.snapshot_at ASC
                LIMIT %s
                """,
                (max(1, limit),),
            )
            rows = cur.fetchall()

        logger.info("Found %s snapshots needing L2/L3 backfill", len(rows))

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
            ladder = _runner_l2_l3(runners, meta)
            if not ladder:
                skipped += 1
                continue

            if dry_run:
                logger.info(
                    "dry-run: snapshot_id=%s market_id=%s -> home_l2=%s/%s home_l3=%s/%s",
                    snapshot_id, market_id,
                    ladder.get("home_back_odds_l2"), ladder.get("home_back_size_l2"),
                    ladder.get("home_back_odds_l3"), ladder.get("home_back_size_l3"),
                )
                updated += 1
                continue

            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.market_derived_metrics
                    SET home_back_odds_l2 = %s, home_back_size_l2 = %s, home_back_odds_l3 = %s, home_back_size_l3 = %s,
                        away_back_odds_l2 = %s, away_back_size_l2 = %s, away_back_odds_l3 = %s, away_back_size_l3 = %s,
                        draw_back_odds_l2 = %s, draw_back_size_l2 = %s, draw_back_odds_l3 = %s, draw_back_size_l3 = %s
                    WHERE snapshot_id = %s
                    """,
                    (
                        ladder.get("home_back_odds_l2"), ladder.get("home_back_size_l2"),
                        ladder.get("home_back_odds_l3"), ladder.get("home_back_size_l3"),
                        ladder.get("away_back_odds_l2"), ladder.get("away_back_size_l2"),
                        ladder.get("away_back_odds_l3"), ladder.get("away_back_size_l3"),
                        ladder.get("draw_back_odds_l2"), ladder.get("draw_back_size_l2"),
                        ladder.get("draw_back_odds_l3"), ladder.get("draw_back_size_l3"),
                        snapshot_id,
                    ),
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
    ap = argparse.ArgumentParser(description="Backfill L2/L3 ladder levels into market_derived_metrics from raw_payload")
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
