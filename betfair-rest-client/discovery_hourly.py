#!/usr/bin/env python3
"""
REST discovery only (Soccer, Full-Time markets). Run on the hour at HH:00:17 (cron 0 * * * *; script sleeps 17s).
- Calls Betfair listMarketCatalogue for Soccer with MATCH_ODDS, OVER_UNDER_2_5, NEXT_GOAL.
- Excludes ALL Half-Time market types (HALF_TIME, HALF_TIME_SCORE, MATCH_ODDS_HT, etc.).
- Persists ALL events and ALL relevant markets + runner/selection mapping.
- Does NOT call listMarketBook; does NOT write any odds/snapshots. Metadata only.
- NEXT_GOAL follow-up: for events without NEXT_GOAL at kickoff, runs one REST check 117s after kickoff.
"""
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("discovery_hourly")

# Full-Time only: Betfair market type codes (no HT)
MARKET_TYPE_CODES_FT = ["MATCH_ODDS", "OVER_UNDER_2_5", "NEXT_GOAL"]
# Exclude any type containing these (case-insensitive)
HT_KEYWORDS = ("HALF_TIME", "HALF_TIME_SCORE", "HALF_TIME_FULL_TIME", "FIRST_HALF", "_HT", "HT_")

# Normalise to internal FT naming for DB (stream client uses MATCH_ODDS_FT, OVER_UNDER_25_FT, NEXT_GOAL)
def _normalise_market_type(bt: Optional[str]) -> Optional[str]:
    if not bt:
        return None
    u = (bt or "").strip().upper()
    if u in ("MATCH_ODDS", "MATCH_ODDS_FT"):
        return "MATCH_ODDS_FT"
    if u in ("OVER_UNDER_2_5", "OVER_UNDER_25", "OVER_UNDER_25_FT"):
        return "OVER_UNDER_25_FT"
    if u == "NEXT_GOAL":
        return "NEXT_GOAL"
    # Other OVER_UNDER_* full time (e.g. OVER_UNDER_3_5, OVER_UNDER_1_5) keep as-is for storage but allow
    if u.startswith("OVER_UNDER_") and not any(h in u for h in ("_HT", "HALF")):
        return u
    return None


def _is_ht_market_type(bt: Optional[str]) -> bool:
    if not bt:
        return True
    u = (bt or "").strip().upper()
    return any(h in u for h in HT_KEYWORDS) or "_HT" in u or u.endswith("HT")


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


def _fetch_catalogue_ft(trading, from_ts, to_ts, market_type_codes: List[str], max_results: int = 1000):
    from betfairlightweight import filters
    time_range = filters.time_range(from_=from_ts, to=to_ts)
    market_filter = filters.market_filter(
        event_type_ids=[1],
        market_type_codes=market_type_codes,
        market_start_time=time_range,
    )
    return trading.betting.list_market_catalogue(
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


def _fetch_catalogue_for_event(trading, event_id: str, market_type_codes: List[str], max_results: int = 50):
    """Fetch catalogue for a specific event and market types (e.g. NEXT_GOAL only)."""
    from betfairlightweight import filters
    market_filter = filters.market_filter(
        event_ids=[event_id],
        market_type_codes=market_type_codes,
    )
    return trading.betting.list_market_catalogue(
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


def _ensure_tables(conn):
    """Ensure rest_events, rest_markets, runners, market_event_metadata and view active_markets_to_stream exist."""
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
            CREATE TABLE IF NOT EXISTS runners (
                market_id    VARCHAR(32) NOT NULL,
                selection_id BIGINT     NOT NULL,
                runner_name  TEXT,
                PRIMARY KEY (market_id, selection_id)
            );
        """)
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_event_open_date ON market_event_metadata (event_open_date);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_competition_name ON market_event_metadata (competition_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_market_start_time ON market_event_metadata (market_start_time);")
        # View: market_ids to stream (FT only; no HT). Source: rest_markets from REST discovery.
        cur.execute("""
            CREATE OR REPLACE VIEW active_markets_to_stream AS
            SELECT market_id, event_id, market_type, market_name, market_start_time
            FROM rest_markets
            WHERE market_type IN ('MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'NEXT_GOAL')
               OR (market_type LIKE 'OVER_UNDER_%%' AND market_type NOT LIKE '%%HT%%');
        """)
        # Track NEXT_GOAL follow-up attempts to avoid duplicates and support rescheduling on kickoff change.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS next_goal_followup (
                event_id       VARCHAR(32) PRIMARY KEY,
                kickoff_at     TIMESTAMPTZ,
                followup_at    TIMESTAMPTZ NOT NULL,
                attempted_at   TIMESTAMPTZ NOT NULL,
                found          BOOLEAN NOT NULL,
                market_ids     TEXT[]
            );
        """)
    conn.commit()


def _upsert_event(conn, event_id: str, event_name: Optional[str], open_date: Any, competition_name: Optional[str], home_team: Optional[str], away_team: Optional[str]):
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


def _upsert_runners(conn, market_id: str, runners: List[Dict]):
    with conn.cursor() as cur:
        for r in runners:
            sel_id = _get_attr(r, "selectionId", "selection_id")
            name = _get_attr(r, "runnerName", "runner_name")
            if sel_id is None:
                continue
            cur.execute("""
                INSERT INTO runners (market_id, selection_id, runner_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (market_id, selection_id) DO UPDATE SET runner_name = COALESCE(EXCLUDED.runner_name, runners.runner_name)
            """, (market_id, int(sel_id), name))
    conn.commit()


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
                "market_id": row["market_id"], "market_name": row.get("market_name"), "market_start_time": row.get("market_start_time"),
                "sport_id": row.get("sport_id"), "sport_name": row.get("sport_name"),
                "event_id": row.get("event_id"), "event_name": row.get("event_name"), "event_open_date": row.get("event_open_date"),
                "country_code": row.get("country_code"), "competition_id": row.get("competition_id"), "competition_name": row.get("competition_name"), "timezone": row.get("timezone"),
                "home_selection_id": row.get("home_selection_id"), "away_selection_id": row.get("away_selection_id"), "draw_selection_id": row.get("draw_selection_id"),
                "home_runner_name": row.get("home_runner_name"), "away_runner_name": row.get("away_runner_name"), "draw_runner_name": row.get("draw_runner_name"),
                "metadata_version": row.get("metadata_version", "v1"),
            })
    conn.commit()


def _extract_metadata_row(catalogue_entry: Any) -> Optional[Dict]:
    """Build one row for market_event_metadata from listMarketCatalogue. Requires 3-way (HOME/AWAY/DRAW)."""
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
    country_code = _get_attr(event, "countryCode", "country_code") if event else None
    comp = _get_attr(catalogue_entry, "competition", "competition")
    competition_id = _get_attr(comp, "id") if comp else None
    competition_name = _get_attr(comp, "name") if comp else None
    sport = _get_attr(catalogue_entry, "eventType", "eventType")
    sport_id = _get_attr(sport, "id") if sport else None
    sport_name = _get_attr(sport, "name") if sport else None
    timezone_val = _get_attr(event, "timezone") if event else None
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
        "country_code": country_code, "competition_id": str(competition_id) if competition_id else None, "competition_name": competition_name,
        "timezone": timezone_val,
        "home_selection_id": home_sid, "away_selection_id": away_sid, "draw_selection_id": draw_sid,
        "home_runner_name": home_name, "away_runner_name": away_name, "draw_runner_name": draw_name,
        "metadata_version": "v1",
    }


def run_discovery(trading, conn) -> Dict[str, int]:
    """Fetch catalogue for FT types only, exclude HT, persist events + markets + runners + metadata. Returns counts."""
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(hours=2)
    to_ts = now + timedelta(hours=48)
    events_seen = set()
    markets_stored = 0
    events_stored = 0
    skipped_ht = 0
    all_catalogues = []
    for mkt_type in MARKET_TYPE_CODES_FT:
        try:
            result = _fetch_catalogue_ft(trading, from_ts, to_ts, [mkt_type], max_results=1000)
            lst = result if isinstance(result, list) else []
            for c in lst:
                desc = _get_attr(c, "description", "market_description")
                raw_type = _get_attr(desc, "marketType", "marketType") if desc else None
                raw_type = (raw_type or "").strip()
                if _is_ht_market_type(raw_type):
                    skipped_ht += 1
                    continue
                norm = _normalise_market_type(raw_type)
                if norm is None and not (raw_type.startswith("OVER_UNDER_") and "HT" not in raw_type.upper()):
                    continue
                all_catalogues.append((c, norm or raw_type))
        except Exception as e:
            logger.warning("Catalogue fetch for %s failed: %s", mkt_type, e)
    for cat, stored_type in all_catalogues:
        market_id = str(_get_attr(cat, "marketId", "market_id") or "")
        if not market_id:
            continue
        event = _get_attr(cat, "event", "event")
        event_id = _get_attr(event, "id") if event else None
        event_name = _get_attr(event, "name") if event else None
        event_open_date = _get_attr(event, "openDate", "open_date") if event else None
        comp = _get_attr(cat, "competition", "competition")
        competition_name = _get_attr(comp, "name") if comp else None
        runners_cat = _get_attr(cat, "runners") or []
        if event_id not in events_seen:
            events_seen.add(event_id)
            try:
                home_team = away_team = None
                if event_name and " v " in str(event_name):
                    parts = str(event_name).split(" v ", 1)
                    home_team = parts[0].strip() if len(parts) > 0 else None
                    away_team = parts[1].strip() if len(parts) > 1 else None
                _upsert_event(conn, str(event_id), event_name, event_open_date, competition_name, home_team, away_team)
                events_stored += 1
            except Exception as e:
                logger.debug("Event upsert skip %s: %s", event_id, e)
        market_name = None
        desc = _get_attr(cat, "description", "market_description")
        if desc:
            market_name = _get_attr(desc, "marketName", "market_name")
        market_start_time = _get_attr(cat, "marketStartTime", "market_start_time")
        try:
            _upsert_market(conn, market_id, str(event_id), stored_type, market_name, market_start_time)
            _upsert_runners(conn, market_id, [r if isinstance(r, dict) else {"selectionId": getattr(r, "selectionId", None), "runnerName": getattr(r, "runnerName", None)} for r in runners_cat])
            markets_stored += 1
        except Exception as e:
            logger.debug("Market upsert skip %s: %s", market_id, e)
        meta_row = _extract_metadata_row(cat)
        if meta_row:
            try:
                _upsert_metadata(conn, meta_row)
            except Exception as e:
                logger.debug("Metadata upsert skip %s: %s", market_id, e)
    return {
        "events_discovered": len(events_seen),
        "events_stored": events_stored,
        "markets_stored": markets_stored,
        "skipped_ht": skipped_ht,
    }


def run_next_goal_followups(trading, conn, events_needing_followup: List[Dict]) -> Dict[str, int]:
    """
    For each event in events_needing_followup (has markets but no NEXT_GOAL, kickoff+117s passed),
    query NEXT_GOAL only for that eventId. Upsert if found. Idempotent. Logs all attempts.
    events_needing_followup: list of {event_id, open_date (kickoff)} from DB.
    """
    now = datetime.now(timezone.utc)
    attempted = 0
    found_count = 0
    for row in events_needing_followup:
        event_id = row["event_id"]
        kickoff = row["open_date"]
        if not kickoff:
            continue
        followup_at = kickoff + timedelta(seconds=117)
        if followup_at > now:
            continue
        try:
            result = _fetch_catalogue_for_event(trading, event_id, ["NEXT_GOAL"], max_results=20)
            lst = result if isinstance(result, list) else []
            attempted += 1
            markets_found = []
            for c in lst:
                desc = _get_attr(c, "description", "market_description")
                raw_type = (desc and _get_attr(desc, "marketType", "marketType")) or ""
                raw_type = (raw_type or "").strip()
                if _is_ht_market_type(raw_type):
                    continue
                norm = _normalise_market_type(raw_type)
                if norm != "NEXT_GOAL":
                    continue
                market_id = str(_get_attr(c, "marketId", "market_id") or "")
                if not market_id:
                    continue
                event_obj = _get_attr(c, "event", "event")
                market_name = None
                if desc:
                    market_name = _get_attr(desc, "marketName", "market_name")
                market_start_time = _get_attr(c, "marketStartTime", "market_start_time")
                runners_cat = _get_attr(c, "runners") or []
                try:
                    _upsert_market(conn, market_id, event_id, norm, market_name, market_start_time)
                    _upsert_runners(conn, market_id, [
                        r if isinstance(r, dict) else {"selectionId": getattr(r, "selectionId", None), "runnerName": getattr(r, "runnerName", None)}
                        for r in runners_cat
                    ])
                    meta_row = _extract_metadata_row(c)
                    if meta_row:
                        _upsert_metadata(conn, meta_row)
                    markets_found.append(market_id)
                except Exception as e:
                    logger.debug("NEXT_GOAL follow-up upsert skip market %s: %s", market_id, e)
            found = len(markets_found) > 0
            if found:
                found_count += 1
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO next_goal_followup (event_id, kickoff_at, followup_at, attempted_at, found, market_ids)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO UPDATE SET
                        kickoff_at = EXCLUDED.kickoff_at,
                        followup_at = EXCLUDED.followup_at,
                        attempted_at = EXCLUDED.attempted_at,
                        found = EXCLUDED.found,
                        market_ids = EXCLUDED.market_ids
                """, (event_id, kickoff, followup_at, now, found, markets_found))
            conn.commit()
            logger.info(
                "NEXT_GOAL follow-up: eventId=%s kickoff=%s followup_at=%s found=%s marketIds=%s",
                event_id, kickoff, followup_at, found, markets_found,
            )
        except Exception as e:
            logger.warning("NEXT_GOAL follow-up failed for eventId=%s: %s", event_id, e)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO next_goal_followup (event_id, kickoff_at, followup_at, attempted_at, found, market_ids)
                    VALUES (%s, %s, %s, %s, FALSE, %s)
                    ON CONFLICT (event_id) DO UPDATE SET
                        kickoff_at = EXCLUDED.kickoff_at,
                        followup_at = EXCLUDED.followup_at,
                        attempted_at = EXCLUDED.attempted_at,
                        found = EXCLUDED.found,
                        market_ids = EXCLUDED.market_ids
                """, (event_id, kickoff, followup_at, now, []))
            conn.commit()
    return {"attempted": attempted, "found": found_count}


def _get_events_needing_next_goal_followup(conn) -> List[Dict]:
    """
    Events that have markets in rest_markets but no NEXT_GOAL, kickoff + 117s has passed.
    Excludes events already attempted for same kickoff (allows reschedule when kickoff postponed).
    Skips if event cancelled/closed (API returns empty when we run).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.event_id, e.open_date
            FROM rest_events e
            WHERE EXISTS (SELECT 1 FROM rest_markets m WHERE m.event_id = e.event_id)
            AND NOT EXISTS (SELECT 1 FROM rest_markets m WHERE m.event_id = e.event_id AND m.market_type = 'NEXT_GOAL')
            AND e.open_date IS NOT NULL
            AND e.open_date + interval '117 seconds' <= NOW()
            AND e.open_date > NOW() - interval '6 hours'
            AND NOT EXISTS (
                SELECT 1 FROM next_goal_followup n
                WHERE n.event_id = e.event_id
                AND n.kickoff_at IS NOT NULL
                AND ABS(EXTRACT(EPOCH FROM (n.kickoff_at - e.open_date))) < 60
            )
        """)
        rows = cur.fetchall()
    return [{"event_id": r[0], "open_date": r[1]} for r in rows]


def main() -> int:
    # HH:00:17 timing (cron 0 * * * *): align when early, never skip when late.
    # - sec < 17: sleep (17 - sec) then run. Max sleep 17s.
    # - sec >= 17: run immediately. Never wait for next hour (no 59+ second sleep).
    # Always perform one discovery per cron trigger, even if started late.
    sec = datetime.now(timezone.utc).second
    if sec < 17:
        sleep_s = 17 - sec
        logger.info("Sleeping %s seconds to align to HH:00:17", sleep_s)
        time.sleep(sleep_s)
    # else: sec >= 17 — execute discovery immediately, do not wait for next hour

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
        logger.error("POSTGRES_PASSWORD required for discovery persistence")
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
        _ensure_tables(conn)
        counts = run_discovery(trading, conn)
        logger.info("Discovery complete: events_discovered=%s events_stored=%s markets_stored=%s skipped_ht=%s",
                    counts["events_discovered"], counts["events_stored"], counts["markets_stored"], counts["skipped_ht"])

        events_needing = _get_events_needing_next_goal_followup(conn)
        if events_needing:
            fu = run_next_goal_followups(trading, conn, events_needing)
            logger.info("NEXT_GOAL follow-up: attempted=%s found=%s", fu["attempted"], fu["found"])
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
