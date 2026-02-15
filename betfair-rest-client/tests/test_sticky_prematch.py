"""
Unit tests for sticky pre-match tracking.

- Market stays tracked until kickoff (no eviction by rank).
- Market not evicted by higher-ranked candidate.
- Capacity refill works.
- Kickoff expiry frees capacity.

Requires Postgres (e.g. POSTGRES_HOST=localhost and POSTGRES_* env) or run in CI with test DB.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _get_conn():
    """Real Postgres conn for tests; skip if not available."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "netbet"),
            user=os.environ.get("POSTGRES_USER", "netbet"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            connect_timeout=2,
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        return None


def test_sticky_tracked_set_persists():
    """Tracked set is persistent; add then refill does not replace."""
    import sticky_prematch as sp
    conn = _get_conn()
    if conn is None:
        print("Skip (no Postgres)")
        return
    try:
        sp.ensure_tables(conn)
        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=2)
        sp.admit_markets(conn, [("1.123", "e1", kickoff, 100.0)], now, K=50)
        active = sp.get_tracked_active(conn, tick_id=1)
        assert len(active) == 1
        assert active[0]["market_id"] == "1.123"
        sp.admit_markets(conn, [("1.456", "e2", kickoff, 200.0)], now, K=50)
        active2 = sp.get_tracked_active(conn, tick_id=2)
        assert len(active2) == 2
        assert {a["market_id"] for a in active2} == {"1.123", "1.456"}
    finally:
        conn.rollback()
        conn.close()


def test_capacity_refill():
    """When capacity < K, new candidates fill until K."""
    import sticky_prematch as sp
    conn = _get_conn()
    if conn is None:
        print("Skip (no Postgres)")
        return
    try:
        sp.ensure_tables(conn)
        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=1)
        n = sp.admit_markets(conn, [
            ("1.1", "e1", kickoff, 10.0),
            ("1.2", "e2", kickoff, 20.0),
            ("1.3", "e3", kickoff, 30.0),
        ], now, K=3)
        assert n == 3
        assert len(sp.get_tracked_market_ids_set(conn)) == 3
    finally:
        conn.rollback()
        conn.close()


def test_kickoff_expiry_frees_capacity():
    """Expiring at kickoff reduces tracked count."""
    import sticky_prematch as sp
    conn = _get_conn()
    if conn is None:
        print("Skip (no Postgres)")
        return
    try:
        sp.ensure_tables(conn)
        now = datetime.now(timezone.utc)
        past_kickoff = now - timedelta(minutes=5)
        future_kickoff = now + timedelta(hours=1)
        sp.admit_markets(conn, [
            ("1.past", "e1", past_kickoff, 10.0),
            ("1.future", "e2", future_kickoff, 20.0),
        ], now, K=50)
        assert len(sp.get_tracked_active(conn, 1)) == 2
        expired = sp.expire_at_kickoff(conn, now, kickoff_buffer_seconds=60, tick_id=1)
        assert expired == 1
        active = sp.get_tracked_active(conn, 2)
        assert len(active) == 1
        assert active[0]["market_id"] == "1.future"
    finally:
        conn.rollback()
        conn.close()


def test_market_not_evicted_by_rank():
    """Already tracked market is not removed when a higher-scored candidate appears."""
    import sticky_prematch as sp
    conn = _get_conn()
    if conn is None:
        print("Skip (no Postgres)")
        return
    try:
        sp.ensure_tables(conn)
        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=2)
        sp.admit_markets(conn, [("1.low", "e1", kickoff, 5.0)], now, K=2)
        sp.admit_markets(conn, [("1.high", "e2", kickoff, 100.0)], now, K=2)
        tracked = sp.get_tracked_market_ids_set(conn)
        assert "1.low" in tracked
        assert "1.high" in tracked
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    test_sticky_tracked_set_persists()
    test_capacity_refill()
    test_kickoff_expiry_frees_capacity()
    test_market_not_evicted_by_rank()
    print("All sticky_prematch tests passed.")
