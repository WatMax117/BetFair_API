#!/usr/bin/env python3
"""
Time-window discovery: listMarketCatalogue for football in [now - lookback, now + horizon].
Market types: MATCH_ODDS, NEXT_GOAL only. Upserts rest_events, rest_markets, market_event_metadata.
Then runs selector sync to update tracked_markets from desired_markets_to_track view.

Config (env):
  DISCOVERY_LOOKBACK_MINUTES   default 60
  DISCOVERY_HORIZON_HOURS      default 48  (H in spec)

Run: python discovery_time_window.py
Cron (e.g. every 15 min): */15 * * * * cd /opt/netbet/betfair-rest-client && python discovery_time_window.py

See docs/REST_DISCOVERY_VS_SNAPSHOT_REFACTOR.md for architecture and tuning.
"""
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("discovery_time_window")

LOOKBACK_MINUTES = int(os.environ.get("DISCOVERY_LOOKBACK_MINUTES", "60"))
HORIZON_HOURS = float(os.environ.get("DISCOVERY_HORIZON_HOURS", "48"))
MARKET_TYPES = ["MATCH_ODDS", "NEXT_GOAL"]
MAX_RESULTS = int(os.environ.get("DISCOVERY_MAX_RESULTS", "500"))
# Cap for streaming (deterministic truncation if desired set exceeds this)
DISCOVERY_STREAM_CAP = int(os.environ.get("DISCOVERY_STREAM_CAP", "200"))
# If discovery hasn't run for longer than this, daemon logs WARNING (see main.py)
DISCOVERY_STALE_WARNING_MINUTES = int(os.environ.get("DISCOVERY_STALE_WARNING_MINUTES", "45"))


def _get_attr(obj: Any, *keys: str):
    for k in keys:
        if obj is None:
            return None
        if isinstance(obj, dict):
            if k in obj:
                return obj[k]
        else:
            v = getattr(obj, k, None)
            if v is not None:
                return v
    return None


def _normalise_market_type(bt: Optional[str]) -> Optional[str]:
    if not bt:
        return None
    u = (bt or "").strip().upper()
    if u in ("MATCH_ODDS", "MATCH_ODDS_FT"):
        return "MATCH_ODDS_FT"
    if u == "NEXT_GOAL":
        return "NEXT_GOAL"
    return None


def _fetch_catalogue_time_window(trading, lookback_minutes: int, horizon_hours: float, max_results: int) -> List[Any]:
    from betfairlightweight import filters
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(minutes=lookback_minutes)
    to_ts = now + timedelta(hours=horizon_hours)
    time_range = filters.time_range(from_=from_ts, to=to_ts)
    market_filter = filters.market_filter(
        event_type_ids=[1],
        market_type_codes=MARKET_TYPES,
        market_start_time=time_range,
    )
    result = trading.betting.list_market_catalogue(
        filter=market_filter,
        market_projection=[
            "RUNNER_DESCRIPTION",
            "MARKET_DESCRIPTION",
            "EVENT",
            "EVENT_TYPE",
            "MARKET_START_TIME",
            "COMPETITION",
        ],
        max_results=max_results,
        sort="MAXIMUM_TRADED",
    )
    lst = result if isinstance(result, list) else []
    return list(lst)


def _ensure_tables_and_views(conn):
    """Ensure rest_events, rest_markets, tracked_markets, desired_markets_to_track view, active_markets_to_stream."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rest_events (
                event_id     VARCHAR(32) PRIMARY KEY,
                event_name   TEXT,
                home_team    VARCHAR(255),
                away_team    VARCHAR(255),
                open_date    TIMESTAMPTZ,
                competition_name TEXT,
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rest_markets (
                market_id         VARCHAR(32) PRIMARY KEY,
                event_id          VARCHAR(32) NOT NULL,
                market_type       VARCHAR(64) NOT NULL,
                market_name       TEXT,
                market_start_time TIMESTAMPTZ,
                last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rest_markets_event_id ON rest_markets(event_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rest_markets_market_type ON rest_markets(market_type);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_event_metadata (
                market_id TEXT PRIMARY KEY,
                market_name TEXT NULL, market_start_time TIMESTAMPTZ NULL,
                sport_id TEXT NULL, sport_name TEXT NULL,
                event_id TEXT NULL, event_name TEXT NULL, event_open_date TIMESTAMPTZ NULL,
                country_code TEXT NULL, competition_id TEXT NULL, competition_name TEXT NULL, timezone TEXT NULL,
                home_selection_id BIGINT NULL, away_selection_id BIGINT NULL, draw_selection_id BIGINT NULL,
                home_runner_name TEXT NULL, away_runner_name TEXT NULL, draw_runner_name TEXT NULL,
                metadata_version TEXT NULL DEFAULT 'v1',
                first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tracked_markets_state ON tracked_markets(state);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tracked_markets_event_start ON tracked_markets(event_start_time_utc);")
        cur.execute("""
            CREATE OR REPLACE VIEW desired_markets_to_track AS
            SELECT rm.market_id, rm.event_id, rm.market_type, rm.market_name, rm.market_start_time
            FROM rest_markets rm
            JOIN rest_events e ON rm.event_id = e.event_id
            WHERE (
                (rm.market_type = 'MATCH_ODDS_FT'
                 AND rm.market_start_time IS NOT NULL
                 AND rm.market_start_time >= (now() AT TIME ZONE 'UTC')
                 AND rm.market_start_time <= (now() AT TIME ZONE 'UTC') + interval '48 hours')
                OR
                (rm.market_type = 'NEXT_GOAL'
                 AND e.open_date IS NOT NULL
                 AND e.open_date <= (now() AT TIME ZONE 'UTC')
                 AND e.open_date >= (now() AT TIME ZONE 'UTC') - interval '3 hours')
            );
        """)
        cur.execute("""
            CREATE OR REPLACE VIEW active_markets_to_stream AS
            SELECT t.market_id, t.event_id, rm.market_type, rm.market_name, rm.market_start_time
            FROM tracked_markets t
            JOIN rest_markets rm ON t.market_id = rm.market_id
            WHERE t.state = 'TRACKING';
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS discovery_run_log (
                id BIGSERIAL PRIMARY KEY,
                run_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                duration_ms INTEGER NOT NULL,
                discovered_count INTEGER NOT NULL,
                desired_count INTEGER NOT NULL,
                tracked_count_after INTEGER NOT NULL,
                added_count INTEGER NOT NULL,
                dropped_count INTEGER NOT NULL,
                earliest_kickoff TIMESTAMPTZ,
                latest_kickoff TIMESTAMPTZ,
                truncated_count INTEGER NOT NULL DEFAULT 0,
                truncation_rule TEXT
            );
        """)
    conn.commit()


def _upsert_event(conn, event_id: str, event_name: Optional[str], open_date: Any, competition_name: Optional[str],
                  home_team: Optional[str], away_team: Optional[str]):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO rest_events (event_id, event_name, open_date, competition_name, home_team, away_team, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (event_id) DO UPDATE SET
                event_name = COALESCE(EXCLUDED.event_name, rest_events.event_name),
                open_date = COALESCE(EXCLUDED.open_date, rest_events.open_date),
                competition_name = COALESCE(EXCLUDED.competition_name, rest_events.competition_name),
                home_team = COALESCE(EXCLUDED.home_team, rest_events.home_team),
                away_team = COALESCE(EXCLUDED.away_team, rest_events.away_team),
                last_seen_at = NOW()
        """, (event_id, event_name, open_date, competition_name, home_team, away_team))
    conn.commit()


def _upsert_market(conn, market_id: str, event_id: str, market_type: str, market_name: Optional[str], market_start_time: Any):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO rest_markets (market_id, event_id, market_type, market_name, market_start_time, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (market_id) DO UPDATE SET
                event_id = EXCLUDED.event_id,
                market_type = EXCLUDED.market_type,
                market_name = COALESCE(EXCLUDED.market_name, rest_markets.market_name),
                market_start_time = COALESCE(EXCLUDED.market_start_time, rest_markets.market_start_time),
                last_seen_at = NOW()
        """, (market_id, event_id, market_type, market_name, market_start_time))
    conn.commit()


def _extract_metadata_row(catalogue_entry: Any) -> Optional[Dict]:
    market_id = _get_attr(catalogue_entry, "marketId", "market_id")
    if not market_id:
        return None
    market_id = str(market_id)
    desc = _get_attr(catalogue_entry, "description", "market_description")
    market_name = _get_attr(desc, "marketName", "market_name") if desc else None
    market_start_time = _get_attr(catalogue_entry, "marketStartTime", "market_start_time")
    event = _get_attr(catalogue_entry, "event", "event")
    event_id = _get_attr(event, "id") if event else None
    event_name = _get_attr(event, "name") if event else None
    event_open_date = _get_attr(event, "openDate", "open_date") if event else None
    comp = _get_attr(catalogue_entry, "competition", "competition")
    competition_id = _get_attr(comp, "id") if comp else None
    competition_name = _get_attr(comp, "name") if comp else None
    sport = _get_attr(catalogue_entry, "eventType", "eventType")
    sport_id = _get_attr(sport, "id") if sport else None
    sport_name = _get_attr(sport, "name") if sport else None
    if event_id is not None:
        event_id = str(event_id)
    runners_cat = _get_attr(catalogue_entry, "runners")
    if not runners_cat or len(runners_cat) < 3:
        return None
    priority_to_role = {1: "HOME", 2: "AWAY", 3: "DRAW"}
    home_sid = away_sid = draw_sid = None
    home_name = away_name = draw_name = None
    for r in runners_cat:
        sp = _get_attr(r, "sortPriority", "sortPriority")
        if sp is None:
            continue
        sp = int(sp)
        if sp not in priority_to_role:
            continue
        role = priority_to_role[sp]
        sid = _get_attr(r, "selectionId", "selectionId")
        rname = _get_attr(r, "runnerName", "runnerName")
        if sid is not None:
            sid = int(sid) if isinstance(sid, (int, float)) else sid
        if role == "HOME":
            home_sid, home_name = sid, rname
        elif role == "AWAY":
            away_sid, away_name = sid, rname
        else:
            draw_sid, draw_name = sid, rname
    if home_sid is None or away_sid is None or draw_sid is None:
        return None
    return {
        "market_id": market_id, "market_name": market_name, "market_start_time": market_start_time,
        "sport_id": str(sport_id) if sport_id else None, "sport_name": sport_name,
        "event_id": event_id, "event_name": event_name, "event_open_date": event_open_date,
        "country_code": None, "competition_id": str(competition_id) if competition_id else None,
        "competition_name": competition_name, "timezone": None,
        "home_selection_id": home_sid, "away_selection_id": away_sid, "draw_selection_id": draw_sid,
        "home_runner_name": home_name, "away_runner_name": away_name, "draw_runner_name": draw_name,
        "metadata_version": "v1",
    }


def _upsert_metadata(conn, row: Dict):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO market_event_metadata (
                market_id, market_name, market_start_time, sport_id, sport_name,
                event_id, event_name, event_open_date, country_code, competition_id, competition_name, timezone,
                home_selection_id, away_selection_id, draw_selection_id,
                home_runner_name, away_runner_name, draw_runner_name,
                metadata_version, first_seen_at, last_seen_at
            )
            VALUES (
                %(market_id)s, %(market_name)s, %(market_start_time)s, %(sport_id)s, %(sport_name)s,
                %(event_id)s, %(event_name)s, %(event_open_date)s, %(country_code)s, %(competition_id)s, %(competition_name)s, %(timezone)s,
                %(home_selection_id)s, %(away_selection_id)s, %(draw_selection_id)s,
                %(home_runner_name)s, %(away_runner_name)s, %(draw_runner_name)s,
                %(metadata_version)s, NOW(), NOW()
            )
            ON CONFLICT (market_id) DO UPDATE SET
                last_seen_at = NOW(),
                market_name = COALESCE(EXCLUDED.market_name, market_event_metadata.market_name),
                market_start_time = COALESCE(EXCLUDED.market_start_time, market_event_metadata.market_start_time),
                event_id = COALESCE(EXCLUDED.event_id, market_event_metadata.event_id),
                event_name = COALESCE(EXCLUDED.event_name, market_event_metadata.event_name),
                event_open_date = COALESCE(EXCLUDED.event_open_date, market_event_metadata.event_open_date),
                competition_id = COALESCE(EXCLUDED.competition_id, market_event_metadata.competition_id),
                competition_name = COALESCE(EXCLUDED.competition_name, market_event_metadata.competition_name),
                home_selection_id = COALESCE(EXCLUDED.home_selection_id, market_event_metadata.home_selection_id),
                away_selection_id = COALESCE(EXCLUDED.away_selection_id, market_event_metadata.away_selection_id),
                draw_selection_id = COALESCE(EXCLUDED.draw_selection_id, market_event_metadata.draw_selection_id),
                home_runner_name = COALESCE(EXCLUDED.home_runner_name, market_event_metadata.home_runner_name),
                away_runner_name = COALESCE(EXCLUDED.away_runner_name, market_event_metadata.away_runner_name),
                draw_runner_name = COALESCE(EXCLUDED.draw_runner_name, market_event_metadata.draw_runner_name)
            """, {
                **row,
                "metadata_version": row.get("metadata_version", "v1"),
            })
    conn.commit()


def sync_desired_to_tracked(conn) -> Dict[str, Any]:
    """
    Sync desired_markets_to_track view to tracked_markets.
    Applies DISCOVERY_STREAM_CAP with prioritization: MATCH_ODDS_FT first (by market_start_time), then NEXT_GOAL.
    Returns added, dropped, desired_count (before cap), tracked_count_after, earliest_kickoff, latest_kickoff,
    truncated_count, truncation_rule.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT market_id, event_id, market_start_time, market_type
            FROM desired_markets_to_track
            ORDER BY (CASE WHEN market_type = 'MATCH_ODDS_FT' THEN 0 ELSE 1 END), market_start_time ASC NULLS LAST
        """)
        desired_full = [(r[0], r[1], r[2]) for r in cur.fetchall()]
        cur.execute("SELECT market_id FROM tracked_markets WHERE state = 'TRACKING'")
        current = {r[0] for r in cur.fetchall()}
    desired_count_full = len(desired_full)
    desired = desired_full[:DISCOVERY_STREAM_CAP] if desired_count_full > DISCOVERY_STREAM_CAP else desired_full
    truncated_count = desired_count_full - len(desired) if desired_count_full > DISCOVERY_STREAM_CAP else 0
    truncation_rule = "stream_cap" if truncated_count > 0 else None
    desired_ids = {r[0] for r in desired}
    to_add = desired_ids - current
    to_drop = current - desired_ids
    now_utc = datetime.now(timezone.utc)
    added = 0
    with conn.cursor() as cur:
        for row in desired:
            if row[0] not in to_add:
                continue
            cur.execute("""
                INSERT INTO tracked_markets (market_id, event_id, event_start_time_utc, admitted_at_utc, state)
                VALUES (%s, %s, %s, %s, 'TRACKING')
                ON CONFLICT (market_id) DO UPDATE SET
                    event_id = EXCLUDED.event_id,
                    event_start_time_utc = EXCLUDED.event_start_time_utc,
                    state = 'TRACKING',
                    updated_at_utc = %s
            """, (row[0], row[1], row[2], now_utc, now_utc))
            if cur.rowcount:
                added += 1
        if to_drop:
            cur.execute(
                "UPDATE tracked_markets SET state = 'DROPPED', updated_at_utc = %s WHERE market_id = ANY(%s) AND state = 'TRACKING'",
                (now_utc, list(to_drop)),
            )
            dropped = cur.rowcount
        else:
            dropped = 0
        cur.execute("SELECT COUNT(*) FROM tracked_markets WHERE state = 'TRACKING'")
        tracked_count_after = cur.fetchone()[0]
    conn.commit()
    kickoffs = [r[2] for r in desired if r[2] is not None]
    earliest_kickoff = min(kickoffs) if kickoffs else None
    latest_kickoff = max(kickoffs) if kickoffs else None
    return {
        "added": added,
        "dropped": dropped,
        "desired_count": desired_count_full,
        "tracked_count_after": tracked_count_after,
        "earliest_kickoff": earliest_kickoff,
        "latest_kickoff": latest_kickoff,
        "truncated_count": truncated_count,
        "truncation_rule": truncation_rule,
    }


def run_discovery(conn, trading) -> Dict[str, Any]:
    run_start = datetime.now(timezone.utc)
    logger.info("Time-window discovery: lookback=%sm horizon=%sh types=%s", LOOKBACK_MINUTES, HORIZON_HOURS, MARKET_TYPES)
    try:
        catalogues = _fetch_catalogue_time_window(trading, LOOKBACK_MINUTES, HORIZON_HOURS, MAX_RESULTS)
    except Exception as e:
        logger.exception("listMarketCatalogue failed: %s", e)
        return {"error": str(e), "markets_stored": 0}
    if not catalogues:
        logger.warning("Catalogue returned no markets")
        sync_result = sync_desired_to_tracked(conn)
        _log_discovery_run(conn, run_start, 0, sync_result)
        return {"markets_stored": 0, "sync": sync_result}
    seen_events = set()
    markets_stored = 0
    for c in catalogues:
        raw_type = _get_attr(_get_attr(c, "description", "market_description"), "marketType", "marketType") or ""
        raw_type = (raw_type or "").strip()
        norm = _normalise_market_type(raw_type)
        if norm not in ("MATCH_ODDS_FT", "NEXT_GOAL"):
            continue
        market_id = str(_get_attr(c, "marketId", "market_id") or "")
        if not market_id:
            continue
        event = _get_attr(c, "event", "event")
        event_id = _get_attr(event, "id") if event else None
        event_name = _get_attr(event, "name") if event else None
        event_open_date = _get_attr(event, "openDate", "open_date") if event else None
        comp = _get_attr(c, "competition", "competition")
        competition_name = _get_attr(comp, "name") if comp else None
        if event_id not in seen_events:
            seen_events.add(event_id)
            home_team = away_team = None
            if event_name and " v " in str(event_name):
                parts = str(event_name).split(" v ", 1)
                home_team = parts[0].strip() if parts else None
                away_team = parts[1].strip() if len(parts) > 1 else None
            _upsert_event(conn, str(event_id), event_name, event_open_date, competition_name, home_team, away_team)
        market_name = _get_attr(_get_attr(c, "description", "market_description"), "marketName", "market_name")
        market_start_time = _get_attr(c, "marketStartTime", "market_start_time")
        _upsert_market(conn, market_id, str(event_id), norm, market_name, market_start_time)
        meta_row = _extract_metadata_row(c)
        if meta_row:
            try:
                _upsert_metadata(conn, meta_row)
            except Exception as e:
                logger.debug("Metadata upsert skip %s: %s", market_id, e)
        markets_stored += 1
    sync_result = sync_desired_to_tracked(conn)
    _log_discovery_run(conn, run_start, markets_stored, sync_result)
    if sync_result.get("truncated_count", 0) > 0:
        logger.warning(
            "Selector output exceeded stream cap: desired_count=%s cap=%s truncated_count=%s rule=%s",
            sync_result["desired_count"], DISCOVERY_STREAM_CAP,
            sync_result["truncated_count"], sync_result.get("truncation_rule"),
        )
    return {"markets_stored": markets_stored, "sync": sync_result}


def _log_discovery_run(conn, run_start: datetime, discovered_count: int, sync_result: Dict[str, Any]):
    """Append one row to discovery_run_log and log INFO with run summary."""
    duration_ms = int((datetime.now(timezone.utc) - run_start).total_seconds() * 1000)
    earliest = sync_result.get("earliest_kickoff")
    latest = sync_result.get("latest_kickoff")
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO discovery_run_log (
                run_at_utc, duration_ms, discovered_count, desired_count, tracked_count_after,
                added_count, dropped_count, earliest_kickoff, latest_kickoff,
                truncated_count, truncation_rule
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            run_start, duration_ms, discovered_count,
            sync_result.get("desired_count", 0), sync_result.get("tracked_count_after", 0),
            sync_result.get("added", 0), sync_result.get("dropped", 0),
            earliest, latest,
            sync_result.get("truncated_count", 0) or 0, sync_result.get("truncation_rule"),
        ))
    conn.commit()
    logger.info(
        "discovery_run run_ts_utc=%s discovered_count=%s desired_count=%s tracked_count_after=%s added=%s dropped=%s earliest_kickoff=%s latest_kickoff=%s duration_ms=%s truncated=%s",
        run_start.isoformat(), discovered_count,
        sync_result.get("desired_count"), sync_result.get("tracked_count_after"),
        sync_result.get("added"), sync_result.get("dropped"),
        earliest.isoformat() if earliest else None, latest.isoformat() if latest else None,
        duration_ms, sync_result.get("truncated_count") or 0,
    )


def main() -> int:
    import psycopg2
    username = os.environ.get("BF_USERNAME") or os.environ.get("BETFAIR_USERNAME")
    password = os.environ.get("BF_PASSWORD") or os.environ.get("BETFAIR_PASSWORD")
    app_key = os.environ.get("BF_APP_KEY") or os.environ.get("BETFAIR_APP_KEY")
    cert_path = os.environ.get("BF_CERT_PATH", "/app/certs/client-2048.crt")
    key_path = os.environ.get("BF_KEY_PATH", "/app/certs/client-2048.key")
    if not all([username, password, app_key]):
        logger.error("Missing BF_USERNAME, BF_PASSWORD, BF_APP_KEY")
        return 1
    if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
        logger.error("Certificate missing: %s / %s", cert_path, key_path)
        return 1
    host = os.environ.get("POSTGRES_HOST") or os.environ.get("BF_POSTGRES_HOST", "postgres")
    port = int(os.environ.get("POSTGRES_PORT") or os.environ.get("BF_POSTGRES_PORT", "5432"))
    dbname = os.environ.get("POSTGRES_DB", "netbet")
    user = os.environ.get("POSTGRES_USER", "netbet")
    password_db = os.environ.get("POSTGRES_PASSWORD", "")
    if not password_db:
        logger.error("POSTGRES_PASSWORD required")
        return 1
    import betfairlightweight
    trading = betfairlightweight.APIClient(username=username, password=password, app_key=app_key, cert_files=(cert_path, key_path), lightweight=True)
    try:
        trading.login()
    except Exception as e:
        logger.exception("Login failed: %s", e)
        return 1
    conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password_db, connect_timeout=10)
    try:
        _ensure_tables_and_views(conn)
        run_discovery(conn, trading)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
