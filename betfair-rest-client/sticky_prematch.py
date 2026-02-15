"""
Sticky pre-match tracking: persistent TrackedSet with admission/retention policy.

Once a market is admitted (up to cap K), it stays tracked until kickoff + buffer or invalid.
Catalogue is used only for discovery and fill; no eviction by rank.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("betfair_rest_client.sticky_prematch")

# Defaults (overridden by main from env)
K_DEFAULT = 50
KICKOFF_BUFFER_SECONDS_DEFAULT = 90
V_MIN_DEFAULT = 0.0  # min totalMatched to admit (optional)
T_MIN_HOURS_DEFAULT = 0.0  # admit only if kickoff >= now + T_min (hours)
T_MAX_HOURS_DEFAULT = 24.0  # admit only if kickoff <= now + T_max (hours)
REQUIRE_CONSECUTIVE_TICKS_DEFAULT = 2  # must appear this many consecutive ticks
CATALOGUE_MAX_RESULTS_DEFAULT = 200
MARKET_BOOK_BATCH_SIZE_DEFAULT = 50  # Betfair weight limit ~200; ~50 markets safe


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_tables(conn) -> None:
    """Create tracked_markets and seen_markets if not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seen_markets (
                market_id TEXT NOT NULL PRIMARY KEY,
                tick_id_first BIGINT NOT NULL,
                tick_id_last BIGINT NOT NULL,
                last_seen_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_seen_markets_tick_last ON seen_markets (tick_id_last);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tracked_markets (
                market_id TEXT NOT NULL PRIMARY KEY,
                event_id TEXT NULL,
                event_start_time_utc TIMESTAMPTZ NOT NULL,
                admitted_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                admission_score DOUBLE PRECISION NULL,
                state TEXT NOT NULL DEFAULT 'TRACKING' CHECK (state IN ('TRACKING', 'DROPPED')),
                last_polled_at_utc TIMESTAMPTZ NULL,
                last_snapshot_at_utc TIMESTAMPTZ NULL,
                created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tracked_markets_state ON tracked_markets (state);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tracked_markets_event_start ON tracked_markets (event_start_time_utc);")
    conn.commit()


def get_tracked_active(conn, tick_id: int) -> List[Dict[str, Any]]:
    """Return list of tracked rows with state=TRACKING (for polling)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT market_id, event_id, event_start_time_utc, admitted_at_utc, admission_score,
                   last_polled_at_utc, last_snapshot_at_utc
            FROM tracked_markets
            WHERE state = 'TRACKING'
            ORDER BY event_start_time_utc ASC
            """,
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def expire_at_kickoff(
    conn,
    now_utc: datetime,
    kickoff_buffer_seconds: int,
    tick_id: int,
) -> int:
    """
    Mark as DROPPED any TRACKING market where now_utc >= event_start_time_utc + buffer.
    Returns count expired.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tracked_markets
            SET state = 'DROPPED', updated_at_utc = %s
            WHERE state = 'TRACKING'
              AND %s >= event_start_time_utc + (%s || ' seconds')::interval
            """,
            (now_utc, now_utc, kickoff_buffer_seconds),
        )
        n = cur.rowcount
    conn.commit()
    return n


def record_seen(conn, market_id: str, tick_id: int, now_utc: datetime) -> None:
    """Upsert seen_markets: set tick_id_last = tick_id, or insert with tick_id_first = tick_id_last = tick_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO seen_markets (market_id, tick_id_first, tick_id_last, last_seen_at_utc)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (market_id) DO UPDATE SET
                tick_id_last = %s,
                last_seen_at_utc = %s
            """,
            (market_id, tick_id, tick_id, now_utc, tick_id, now_utc),
        )
    conn.commit()


def is_mature(
    conn,
    market_id: str,
    event_start_utc: Optional[datetime],
    total_matched: float,
    tick_id: int,
    now_utc: datetime,
    *,
    v_min: float = 0,
    t_min_hours: float = 0,
    t_max_hours: float = 24,
    require_consecutive_ticks: int = 2,
) -> bool:
    """
    True if market is mature enough to admit.
    - Kickoff in [now + T_min, now + T_max] (hours).
    - Either totalMatched >= v_min OR seen in require_consecutive_ticks consecutive ticks.
    """
    if event_start_utc is None:
        return False
    delta = (event_start_utc - now_utc).total_seconds() / 3600.0
    if delta < t_min_hours or delta > t_max_hours:
        return False
    if total_matched >= v_min:
        return True
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tick_id_first, tick_id_last FROM seen_markets WHERE market_id = %s",
            (market_id,),
        )
        row = cur.fetchone()
    if not row:
        return False
    tick_first, tick_last = row
    # "Seen in N consecutive ticks": must have been seen in the previous (N-1) ticks.
    # So at tick_id, we require tick_id_last >= tick_id - (N-1) and tick_id_last < tick_id
    # (so we don't admit on first sight; record_seen is called after building candidates).
    if tick_last >= tick_id:
        return False  # not yet updated for this tick
    return (tick_id - tick_last) <= (require_consecutive_ticks - 1)


def get_tracked_market_ids_set(conn) -> set:
    """Set of market_ids currently TRACKING."""
    with conn.cursor() as cur:
        cur.execute("SELECT market_id FROM tracked_markets WHERE state = 'TRACKING'")
        return {r[0] for r in cur.fetchall()}


def admit_markets(
    conn,
    entries: List[Tuple[str, Optional[str], datetime, float]],
    now_utc: datetime,
    k: int,
) -> int:
    """
    entries: list of (market_id, event_id, event_start_time_utc, score).
    Admit in order until len(tracked TRACKING) reaches K. Returns number admitted.
    """
    current = len(get_tracked_market_ids_set(conn))
    to_admit = k - current
    if to_admit <= 0:
        return 0
    admitted = 0
    with conn.cursor() as cur:
        for market_id, event_id, event_start_utc, score in entries:
            if admitted >= to_admit:
                break
            cur.execute(
                """
                INSERT INTO tracked_markets (market_id, event_id, event_start_time_utc, admitted_at_utc, admission_score, state)
                VALUES (%s, %s, %s, %s, %s, 'TRACKING')
                ON CONFLICT (market_id) DO NOTHING
                """,
                (market_id, event_id, event_start_utc, now_utc, score),
            )
            if cur.rowcount:
                admitted += 1
    conn.commit()
    return admitted


def update_tracked_after_poll(
    conn,
    market_ids: List[str],
    now_utc: datetime,
) -> None:
    """Set last_polled_at_utc and last_snapshot_at_utc for given market_ids."""
    if not market_ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tracked_markets
            SET last_polled_at_utc = %s, last_snapshot_at_utc = %s, updated_at_utc = %s
            WHERE market_id = ANY(%s) AND state = 'TRACKING'
            """,
            (now_utc, now_utc, now_utc, market_ids),
        )
    conn.commit()


def drop_tracked_not_found(
    conn,
    requested_ids: List[str],
    returned_ids: List[str],
    now_utc: datetime,
) -> int:
    """Mark as DROPPED any TRACKING market that was requested but not in API response (e.g. NOT_FOUND)."""
    missing = set(requested_ids) - set(returned_ids)
    if not missing:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tracked_markets
            SET state = 'DROPPED', updated_at_utc = %s
            WHERE state = 'TRACKING' AND market_id = ANY(%s)
            """,
            (now_utc, list(missing)),
        )
        n = cur.rowcount
    conn.commit()
    return n
