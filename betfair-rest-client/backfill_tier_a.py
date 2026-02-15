#!/usr/bin/env python3
"""
Tier A Backfill: Recompute Book Risk L3 and L1 sizes from raw_payload.

Imbalance and Impedance indices removed (MVP). Only backfills book_risk_l3 and L1 size columns.

Usage:
    python3 backfill_tier_a.py [--batch-size N] [--limit M] [--dry-run]
"""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.extras import Json as PsycopgJson
except ImportError:
    print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

# Import production logic (assumes script runs from betfair-rest-client directory)
try:
    from risk import compute_book_risk_l3
    from main import _runner_best_prices, _safe_float, DEPTH_LIMIT
except ImportError:
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from risk import compute_book_risk_l3
    from main import _runner_best_prices, _safe_float, DEPTH_LIMIT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# DB connection: env vars (VPS/docker) or defaults (local)
def _get_db_config():
    import os
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ.get("POSTGRES_DB", "netbet"),
        "user": os.environ.get("POSTGRES_USER", os.environ.get("POSTGRES_REST_WRITER_USER", "netbet")),
        "password": os.environ.get("POSTGRES_PASSWORD", os.environ.get("POSTGRES_REST_WRITER_PASSWORD", "netbet")),
    }


def get_conn():
    """Open DB connection."""
    return psycopg2.connect(**_get_db_config())


def get_runner_metadata(conn, market_id: str) -> Optional[Dict]:
    """Get runner metadata (selectionId -> HOME/AWAY/DRAW) for a market."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT home_selection_id, away_selection_id, draw_selection_id
            FROM market_event_metadata
            WHERE market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
        if not row or row["home_selection_id"] is None or row["away_selection_id"] is None or row["draw_selection_id"] is None:
            return None
        return {
            row["home_selection_id"]: "HOME",
            row["away_selection_id"]: "AWAY",
            row["draw_selection_id"]: "DRAW",
        }


def load_raw_payload(conn, snapshot_id: int) -> Optional[Dict]:
    """Load raw_payload JSONB for a snapshot."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT raw_payload
            FROM market_book_snapshots
            WHERE snapshot_id = %s
            """,
            (snapshot_id,),
        )
        row = cur.fetchone()
        if not row or not row["raw_payload"]:
            return None
        payload = row["raw_payload"]
        if isinstance(payload, str):
            return json.loads(payload)
        return payload


def recompute_metrics(raw_payload: Dict, runner_metadata: Dict, snapshot_at: Any) -> Optional[Dict]:
    """
    Recompute all metrics using production logic.
    Returns dict with all computed fields or None if reconstruction fails.
    """
    runners = raw_payload.get("runners", [])
    if not runners or len(runners) < 3:
        logger.warning("Skipping: insufficient runners in raw_payload")
        return None

    # L1 sizes (best back/lay at level 1)
    best_prices = _runner_best_prices(runners, runner_metadata)
    if not best_prices:
        logger.warning("Skipping: could not extract best prices")
        return None

    # Book Risk L3
    book_risk_l3 = compute_book_risk_l3(runners, runner_metadata, depth_limit=DEPTH_LIMIT)
    if not book_risk_l3:
        logger.warning("Skipping: could not compute book_risk_l3")
        return None

    total_matched = raw_payload.get("totalMatched") or raw_payload.get("total_matched")
    total_volume = _safe_float(total_matched) if total_matched is not None else sum(
        _safe_float(r.get("totalMatched") if isinstance(r, dict) else getattr(r, "totalMatched", None) or getattr(r, "total_matched", None))
        for r in runners
    )

    metrics = {
        "home_best_back_size_l1": best_prices.get("home_best_back_size_l1"),
        "away_best_back_size_l1": best_prices.get("away_best_back_size_l1"),
        "draw_best_back_size_l1": best_prices.get("draw_best_back_size_l1"),
        "home_best_lay_size_l1": best_prices.get("home_best_lay_size_l1"),
        "away_best_lay_size_l1": best_prices.get("away_best_lay_size_l1"),
        "draw_best_lay_size_l1": best_prices.get("draw_best_lay_size_l1"),
        "home_book_risk_l3": book_risk_l3.get("home_book_risk_l3"),
        "away_book_risk_l3": book_risk_l3.get("away_book_risk_l3"),
        "draw_book_risk_l3": book_risk_l3.get("draw_book_risk_l3"),
        "total_volume": total_volume,
    }
    return metrics


def update_metrics(conn, snapshot_id: int, metrics: Dict, dry_run: bool = False):
    """Update market_derived_metrics with recomputed values (only NULL fields). COALESCE preserves existing non-NULL values."""
    if dry_run:
        logger.info(f"[DRY RUN] Would update snapshot_id={snapshot_id} with metrics: {json.dumps({k: v for k, v in metrics.items() if v != 0}, indent=2)}")
        return

    with conn.cursor() as cur:
        # Build UPDATE SET clause: COALESCE(col, val) only updates if col is NULL
        updates = []
        values = []
        for col, val in metrics.items():
            updates.append(f"{col} = COALESCE({col}, %s)")
            values.append(val)

        if not updates:
            return

        values.append(snapshot_id)
        cur.execute(
            f"""
            UPDATE market_derived_metrics
            SET {', '.join(updates)}
            WHERE snapshot_id = %s
            """,
            values,
        )
    conn.commit()


def backfill_batch(conn, batch_size: int = 500, limit: Optional[int] = None, dry_run: bool = False):
    """
    Process backfill in batches.
    Selects rows where any new column is NULL and recomputes from raw_payload.
    """
    processed = 0
    updated = 0
    skipped = 0
    errors = 0

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Find rows needing backfill (book_risk_l3 or L1 sizes NULL)
        query = """
            SELECT d.snapshot_id, d.market_id, d.snapshot_at
            FROM market_derived_metrics d
            WHERE (
                d.home_book_risk_l3 IS NULL OR
                d.home_best_back_size_l1 IS NULL
            )
            ORDER BY d.snapshot_at ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query)
        rows = cur.fetchall()

        total_rows = len(rows)
        logger.info(f"Found {total_rows} rows needing backfill")

        for i, row in enumerate(rows, 1):
            snapshot_id = row["snapshot_id"]
            market_id = row["market_id"]
            snapshot_at = row["snapshot_at"]

            try:
                # Load runner metadata
                runner_metadata = get_runner_metadata(conn, market_id)
                if not runner_metadata:
                    logger.warning(f"Snapshot {snapshot_id}: No runner metadata, skipping")
                    skipped += 1
                    continue

                # Load raw_payload
                raw_payload = load_raw_payload(conn, snapshot_id)
                if not raw_payload:
                    logger.warning(f"Snapshot {snapshot_id}: No raw_payload, skipping")
                    skipped += 1
                    continue

                # Recompute metrics
                metrics = recompute_metrics(raw_payload, runner_metadata, snapshot_at)
                if not metrics:
                    logger.warning(f"Snapshot {snapshot_id}: Could not recompute metrics, skipping")
                    skipped += 1
                    continue

                # Update database
                update_metrics(conn, snapshot_id, metrics, dry_run=dry_run)
                updated += 1
                processed += 1

                if i % batch_size == 0:
                    logger.info(f"Progress: {i}/{total_rows} processed, {updated} updated, {skipped} skipped, {errors} errors")
                    conn.commit()

            except Exception as e:
                logger.error(f"Snapshot {snapshot_id}: Error: {e}", exc_info=True)
                errors += 1
                processed += 1

        conn.commit()

    logger.info(f"Backfill complete: {processed} processed, {updated} updated, {skipped} skipped, {errors} errors")
    return processed, updated, skipped, errors


def main():
    parser = argparse.ArgumentParser(description="Tier A backfill: Full deterministic reconstruction from raw_payload")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing (default: 500)")
    parser.add_argument("--limit", type=int, help="Limit number of rows to process (for testing)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no database updates)")
    args = parser.parse_args()

    logger.info("Starting Tier A backfill")
    logger.info(f"Batch size: {args.batch_size}, Limit: {args.limit}, Dry run: {args.dry_run}")

    try:
        conn = get_conn()
        processed, updated, skipped, errors = backfill_batch(
            conn,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        conn.close()

        logger.info("Backfill completed successfully")
        sys.exit(0 if errors == 0 else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
