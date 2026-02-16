"""
Partition provisioning for stream_ingest.ladder_levels.
Runs on API startup and periodically (every 12h). Ensures daily partitions exist
for [today_utc, today_utc + DAYS_AHEAD] so streaming client inserts never fail
with "no partition of relation ladder_levels found for row".

Uses Postgres advisory lock so multiple API replicas do not run DDL concurrently.
Control-plane only; not triggered from request handlers.

Requires API DB user to have CREATE on schema stream_ingest and to own (or have
privileges to attach partitions to) stream_ingest.ladder_levels.
"""
import logging
import os
import threading
import time
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional, Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from app.db import get_conn_kwargs

logger = logging.getLogger(__name__)


def _get_partition_conn_kwargs():
    """Connection for DDL (create partitions). Uses partition-manager user if set, else main API user."""
    base = get_conn_kwargs()
    user = os.environ.get("POSTGRES_PARTITION_USER")
    password = os.environ.get("POSTGRES_PARTITION_PASSWORD")
    if user:
        base = {**base, "user": user, "password": password or ""}
    return base

# Stable bigint for advisory lock (unique to this maintenance task)
PARTITION_PROVISIONER_LOCK_ID = 0x504152545F50524F56  # "PART_PROV" in hex
DAYS_AHEAD = int(os.environ.get("PARTITION_DAYS_AHEAD", "30"))
PARTITION_INTERVAL_HOURS = float(os.environ.get("PARTITION_INTERVAL_HOURS", "12"))

# Minimum horizon (days) to consider healthy; alert if below this
HORIZON_ALERT_THRESHOLD_DAYS = 7
# Degrade health (do not hard-fail) if below this
HORIZON_DEGRADE_THRESHOLD_DAYS = 2

# Last observed horizon (days ahead); updated after each run; used for health/metrics
_horizon_days: Optional[float] = None
_horizon_lock = threading.Lock()


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _partition_name_for_date(d: date) -> str:
    return f"ladder_levels_{d.strftime('%Y%m%d')}"


def get_partition_horizon_days() -> Optional[float]:
    """
    Query DB for current partition coverage: max partition date - today (UTC).
    Returns None if table is missing or query fails.
    """
    try:
        conn = psycopg2.connect(**get_conn_kwargs(), cursor_factory=RealDictCursor)
        try:
            cur = conn.cursor()
            # Child tables of stream_ingest.ladder_levels; names are ladder_levels_YYYYMMDD
            cur.execute(
                """
                SELECT c.relname
                FROM pg_inherits i
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_class p ON p.oid = i.inhparent
                JOIN pg_namespace n ON n.oid = p.relnamespace
                WHERE n.nspname = 'stream_ingest' AND p.relname = 'ladder_levels'
                """
            )
            rows = cur.fetchall()
            if not rows:
                return None
            max_date: Optional[date] = None
            for r in rows:
                name = r["relname"]
                if name and name.startswith("ladder_levels_") and len(name) == len("ladder_levels_YYYYMMDD"):
                    try:
                        part_date = datetime.strptime(name.replace("ladder_levels_", ""), "%Y%m%d").date()
                        if max_date is None or part_date > max_date:
                            max_date = part_date
                    except ValueError:
                        continue
            if max_date is None:
                return None
            today = _today_utc()
            # Upper bound of a daily partition is next day 00:00; coverage is up to end of max_date
            horizon = (max_date - today).days
            return float(horizon)
        finally:
            conn.close()
    except Exception as e:
        logger.warning("partition_provisioner: get_partition_horizon_days failed: %s", e)
        return None


def run_provisioning() -> Tuple[bool, List[str], Optional[float]]:
    """
    Ensure partitions exist for stream_ingest.ladder_levels for [today_utc, today_utc + DAYS_AHEAD].
    Uses advisory lock; if lock not acquired, skips and returns (False, [], current_horizon).
    Returns (lock_acquired, list_of_created_partition_names, coverage_horizon_days).
    """
    created: List[str] = []
    conn = None
    try:
        conn = psycopg2.connect(**_get_partition_conn_kwargs(), cursor_factory=RealDictCursor)
        cur = conn.cursor()

        # Try advisory lock (session-scoped)
        cur.execute("SELECT pg_try_advisory_lock(%s)", (PARTITION_PROVISIONER_LOCK_ID,))
        if not cur.fetchone()[0]:
            logger.info("partition provisioning skipped (lock held by another instance)")
            horizon = get_partition_horizon_days()
            return False, [], horizon

        logger.info("partition provisioning acquired lock")

        try:
            today = _today_utc()
            end_date = today + timedelta(days=DAYS_AHEAD)
            parent = sql.SQL(".").join([sql.Identifier("stream_ingest"), sql.Identifier("ladder_levels")])
            current = today
            while current <= end_date:
                part_name = _partition_name_for_date(current)
                range_from = datetime(current.year, current.month, current.day, 0, 0, 0, tzinfo=timezone.utc)
                range_to = range_from + timedelta(days=1)
                part_ident = sql.SQL(".").join([sql.Identifier("stream_ingest"), sql.Identifier(part_name)])
                cur.execute(
                    sql.SQL("CREATE TABLE IF NOT EXISTS {} PARTITION OF {} FOR VALUES FROM ({}) TO ({})").format(
                        part_ident,
                        parent,
                        sql.Literal(range_from),
                        sql.Literal(range_to),
                    )
                )
                created.append(part_name)
                current += timedelta(days=1)

            conn.commit()
            # Log coverage horizon
            horizon_end = end_date
            horizon_days = (horizon_end - today).days
            logger.info(
                "partition provisioning created/ensured partitions: %s ... %s; coverage horizon: %s",
                created[0] if created else "none",
                created[-1] if len(created) > 1 else "",
                horizon_end.isoformat(),
            )

            with _horizon_lock:
                global _horizon_days
                _horizon_days = float(horizon_days)

            if horizon_days < HORIZON_ALERT_THRESHOLD_DAYS:
                logger.warning(
                    "partition provisioning: horizon %s days is below alert threshold %s",
                    horizon_days,
                    HORIZON_ALERT_THRESHOLD_DAYS,
                )

            return True, created, float(horizon_days)
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (PARTITION_PROVISIONER_LOCK_ID,))
            conn.commit()
    except Exception as e:
        logger.exception("partition provisioning failed: %s", e)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        horizon = get_partition_horizon_days()
        return False, [], horizon
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    return False, [], get_partition_horizon_days()


def get_horizon_for_health() -> Optional[float]:
    """Return last-known horizon (from last run or live query) for health/metrics."""
    with _horizon_lock:
        if _horizon_days is not None:
            return _horizon_days
    return get_partition_horizon_days()


def _run_loop() -> None:
    """Background loop: run once, then every PARTITION_INTERVAL_HOURS."""
    run_provisioning()
    interval_sec = max(3600, int(PARTITION_INTERVAL_HOURS * 3600))
    while True:
        time.sleep(interval_sec)
        try:
            run_provisioning()
        except Exception as e:
            logger.exception("partition provisioning loop error: %s", e)


def start_background_provisioner() -> None:
    """Start the partition provisioner in a daemon thread (startup + periodic)."""
    def run():
        try:
            _run_loop()
        except Exception as e:
            logger.exception("partition provisioner thread exited: %s", e)

    t = threading.Thread(target=run, name="partition-provisioner", daemon=True)
    t.start()
    logger.info(
        "partition provisioner started (DAYS_AHEAD=%s, interval_hours=%s)",
        DAYS_AHEAD,
        PARTITION_INTERVAL_HOURS,
    )
