#!/usr/bin/env python3
"""
REST discovery only (Soccer, Full-Time markets). Run hourly at HH:00.
- Competition-driven (Variant B): iterates per competition (league) via listCompetitions.
- Market types: MATCH_ODDS, OVER_UNDER_2_5, NEXT_GOAL.
- No time-window; no inPlayOnly splitting. Single catalogue call per competition.
- If one competition fails, continues with others (no abort).
- Persists events + markets to rest_events / rest_markets. Metadata only; no listMarketBook.
- NEXT_GOAL follow-up: for events without NEXT_GOAL at kickoff, runs one REST check 117s after kickoff.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


# Competition cache: file path and TTL (hours). Env: DISCOVERY_COMPETITIONS_CACHE_PATH, DISCOVERY_COMPETITIONS_CACHE_TTL_HOURS
def _competitions_cache_path() -> Path:
    p = os.environ.get("DISCOVERY_COMPETITIONS_CACHE_PATH")
    if p:
        return Path(p)
    return Path(__file__).resolve().parent / "discovery_competitions_cache.json"


def _competitions_cache_ttl_hours() -> float:
    try:
        return float(os.environ.get("DISCOVERY_COMPETITIONS_CACHE_TTL_HOURS", "12"))
    except ValueError:
        return 12.0


def _get_competition_ids(trading) -> List[str]:
    """
    Get Soccer competition IDs. Uses file cache with TTL (default 12h).
    On cache miss/expiry, calls listCompetitions and updates cache.
    """
    cache_path = _competitions_cache_path()
    ttl_hours = _competitions_cache_ttl_hours()
    now = datetime.now(timezone.utc)

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at_s = data.get("cached_at")
            if cached_at_s:
                cached_at = datetime.fromisoformat(cached_at_s.replace("Z", "+00:00"))
                age_hours = (now - cached_at).total_seconds() / 3600
                if age_hours < ttl_hours:
                    ids = data.get("competition_ids") or []
                    logger.info("Using cached competition list: %d competitions (cached %.1fh ago)", len(ids), age_hours)
                    return ids
        except Exception as e:
            logger.warning("Competition cache read failed: %s, will refresh", e)

    from betfairlightweight import filters
    market_filter = filters.market_filter(event_type_ids=[1])
    result = trading.betting.list_competitions(filter=market_filter)
    rows = result if isinstance(result, list) else []
    ids = []
    for r in rows:
        comp = _get_attr(r, "competition") or r
        cid = _get_attr(comp, "id") or (comp.get("id") if isinstance(comp, dict) else None)
        if cid:
            ids.append(str(cid))
    logger.info("Fetched %d competitions from listCompetitions", len(ids))

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"competition_ids": ids, "cached_at": now.isoformat()}, f, indent=0)
    except Exception as e:
        logger.warning("Competition cache write failed: %s", e)
    return ids


def _fetch_catalogue_for_competition(
    trading, competition_id: str, market_type_codes: List[str], max_results: int = 200
) -> List[Any]:
    """
    Call Betfair listMarketCatalogue for one competition with MATCH_ODDS, OVER_UNDER_2_5, NEXT_GOAL.
    No time-window, no inPlayOnly. Returns list of catalogue items.
    """
    from betfairlightweight import filters
    market_filter = filters.market_filter(
        event_type_ids=[1],
        competition_ids=[competition_id],
        market_type_codes=market_type_codes,
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
    if hasattr(result, "more_available") and result.more_available:
        logger.warning("Betfair returned truncated results (more_available=True) for competition_id=%s", competition_id)
    return list(lst)


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
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rest_markets_event_id ON rest_markets(event_id);")
        except Exception as e:
            conn.rollback()
            logger.debug("Index idx_rest_markets_event_id may already exist or permission denied: %s", e)
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rest_markets_market_type ON rest_markets(market_type);")
        except Exception as e:
            conn.rollback()
            logger.debug("Index idx_rest_markets_market_type may already exist or permission denied: %s", e)
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
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_event_open_date ON market_event_metadata (event_open_date);")
        except Exception as e:
            conn.rollback()
            logger.debug("Index idx_mem_event_open_date may already exist or permission denied: %s", e)
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_competition_name ON market_event_metadata (competition_name);")
        except Exception as e:
            conn.rollback()
            logger.debug("Index idx_mem_competition_name may already exist or permission denied: %s", e)
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_market_start_time ON market_event_metadata (market_start_time);")
        except Exception as e:
            conn.rollback()
            logger.debug("Index idx_mem_market_start_time may already exist or permission denied: %s", e)
        # View: market_ids to stream (FT only; no HT). Source: rest_markets from REST discovery.
        try:
            cur.execute("""
                CREATE OR REPLACE VIEW active_markets_to_stream AS
                SELECT market_id, event_id, market_type, market_name, market_start_time
                FROM rest_markets
                WHERE market_type IN ('MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'NEXT_GOAL')
                   OR (market_type LIKE 'OVER_UNDER_%%' AND market_type NOT LIKE '%%HT%%');
            """)
        except Exception as e:
            conn.rollback()
            logger.debug("View active_markets_to_stream may already exist or permission denied: %s", e)
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


def _get_db_counts(conn) -> Tuple[int, int]:
    """Return (rest_events count, rest_markets count)."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM rest_events")
        events_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM rest_markets")
        markets_count = cur.fetchone()[0]
    return events_count, markets_count


def _run_db_coverage_checks(conn, today_str: str) -> None:
    """
    Step 3 & 4: Log DB coverage after discovery (distinct competitions today, markets today,
    top competitions by market count, distinct market_ids for stream subscription).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT mem.competition_id)
            FROM rest_events e
            JOIN rest_markets m ON e.event_id = m.event_id
            JOIN market_event_metadata mem ON m.market_id = mem.market_id
            WHERE e.open_date::date = %s
        """, (today_str,))
        distinct_comps = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(*)
            FROM rest_markets m
            JOIN rest_events e ON m.event_id = e.event_id
            WHERE e.open_date::date = %s
        """, (today_str,))
        markets_today = cur.fetchone()[0]
        cur.execute("""
            SELECT mem.competition_id, mem.competition_name, COUNT(*) AS cnt
            FROM rest_markets m
            JOIN rest_events e ON m.event_id = e.event_id
            JOIN market_event_metadata mem ON m.market_id = mem.market_id
            WHERE e.open_date::date = %s
            GROUP BY mem.competition_id, mem.competition_name
            ORDER BY cnt DESC
            LIMIT 20
        """, (today_str,))
        top_comps = cur.fetchall()
        cur.execute("SELECT COUNT(DISTINCT market_id) FROM rest_markets")
        distinct_market_ids = cur.fetchone()[0]
    logger.info("[DIAG] db_coverage today=%s distinct_competitions=%d markets_today=%d distinct_market_ids_total=%d",
                today_str, distinct_comps, markets_today, distinct_market_ids)
    logger.info("[DIAG] top_20_competitions_by_markets_today: %s",
                [(cid, cname, cnt) for cid, cname, cnt in top_comps])


def run_discovery(trading, conn) -> Dict[str, Any]:
    """
    Competition-driven discovery: for each Soccer competition, fetch catalogue
    (MATCH_ODDS, OVER_UNDER_2_5, NEXT_GOAL). Deduplicate by market_id. Persist events + markets.
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logger.info("=== DISCOVERY DIAGNOSTICS START run_id=%s ===", run_id)
    logger.info("Discovery mode: competition-driven (Variant B)")
    logger.info("MarketTypeCodes: %s", MARKET_TYPE_CODES_FT)
    logger.info("eventTypeIds: [1] (Soccer), maxResults: 200 per competition")

    # Step 2: DB baseline before discovery
    rest_events_before, rest_markets_before = _get_db_counts(conn)
    logger.info("[DIAG] db_before rest_events=%d rest_markets=%d", rest_events_before, rest_markets_before)

    competition_ids = _get_competition_ids(trading)
    competitions_total = len(competition_ids)
    competitions_succeeded = 0
    competitions_failed = 0
    competitions_returning_0 = 0
    competitions_returning_gt0 = 0
    catalogue_items_total = 0
    competition_market_counts: List[Tuple[str, int]] = []  # (comp_id, count)
    seen_market_id: Dict[str, Any] = {}  # market_id -> (catalogue_entry, stored_type)
    skipped_ht = 0
    skipped_normalize = 0
    dropped_samples: List[Dict] = []
    max_results_per_comp = 200

    logger.info("[DIAG] competitions_total=%d", competitions_total)
    logger.info("[DIAG] first_20_competitionIds=%s", competition_ids[:20])

    for comp_index, comp_id in enumerate(competition_ids, start=1):
        call_started_at = datetime.now(timezone.utc)
        logger.info("[DIAG] run_id=%s comp=%d/%d comp_id=%s catalogue_call=START",
                    run_id, comp_index, competitions_total, comp_id)
        try:
            lst = _fetch_catalogue_for_competition(trading, comp_id, MARKET_TYPE_CODES_FT, max_results=max_results_per_comp)
            call_finished_at = datetime.now(timezone.utc)
            returned_count = len(lst)
            duration_ms = (call_finished_at - call_started_at).total_seconds() * 1000
            logger.info("[DIAG] run_id=%s comp=%d/%d comp_id=%s catalogue_call=END returned_count=%d duration_ms=%.0f",
                        run_id, comp_index, competitions_total, comp_id, returned_count, duration_ms)

            # Per-competition market coverage
            type_counts: Dict[str, int] = {}
            for c in lst:
                desc = _get_attr(c, "description", "market_description")
                raw_type = _get_attr(desc, "marketType", "marketType") if desc else None
                rt = (raw_type or "").strip()
                type_counts[rt] = type_counts.get(rt, 0) + 1
            logger.info("[DIAG] comp_id=%s returned_count=%d by_type=%s", comp_id, returned_count, type_counts)
            if returned_count >= max_results_per_comp:
                logger.warning("[DIAG] POTENTIAL_TRUNCATION for competitionId=%s (returned %d >= maxResults %d)", comp_id, returned_count, max_results_per_comp)

            if returned_count == 0:
                competitions_returning_0 += 1
            else:
                competitions_returning_gt0 += 1

            comp_count = 0
            for c in lst:
                desc = _get_attr(c, "description", "market_description")
                raw_type = _get_attr(desc, "marketType", "marketType") if desc else None
                raw_type = (raw_type or "").strip()
                market_id = str(_get_attr(c, "marketId", "market_id") or "")
                event = _get_attr(c, "event", "event")
                event_id = _get_attr(event, "id") if event else None

                if _is_ht_market_type(raw_type):
                    skipped_ht += 1
                    if len(dropped_samples) < 10:
                        dropped_samples.append({"market_id": market_id, "market_type": raw_type, "event_id": str(event_id) if event_id else None, "reason": "HT excluded"})
                    continue
                norm = _normalise_market_type(raw_type)
                if norm is None and not (raw_type.startswith("OVER_UNDER_") and "HT" not in raw_type.upper()):
                    skipped_normalize += 1
                    if len(dropped_samples) < 10:
                        dropped_samples.append({"market_id": market_id, "market_type": raw_type, "event_id": str(event_id) if event_id else None, "reason": "normalize None"})
                    continue
                if market_id and market_id not in seen_market_id:
                    seen_market_id[market_id] = (c, norm or raw_type)
                    comp_count += 1
            catalogue_items_total += returned_count
            competitions_succeeded += 1
            if comp_count > 0:
                competition_market_counts.append((comp_id, comp_count))
        except Exception as e:
            competitions_failed += 1
            logger.error("[DIAG] run_id=%s comp=%d/%d comp_id=%s catalogue_call=ERROR err=%s",
                        run_id, comp_index, competitions_total, comp_id, str(e))

    logger.info("[DIAG] catalogue_call END count=%d (succeeded=%d failed=%d)",
                competitions_succeeded + competitions_failed, competitions_succeeded, competitions_failed)
    logger.info("[DIAG] competitions_returning_0=%d competitions_returning_gt0=%d", competitions_returning_0, competitions_returning_gt0)

    all_catalogues = list(seen_market_id.values())
    events_seen: set = set()
    markets_stored = 0
    events_stored = 0
    skipped_other = 0
    markets_by_type: Dict[str, int] = {}
    metadata_to_upsert = 0

    logger.info("competitions_total=%d competitions_succeeded=%d competitions_failed=%d",
                competitions_total, competitions_succeeded, competitions_failed)
    logger.info("catalogue_items_total=%d unique_markets=%d", catalogue_items_total, len(all_catalogues))

    # Step 3: Compare catalogue vs stored (coverage loss detection)
    if catalogue_items_total > 0 and len(events_seen) > 0:
        catalogue_to_events_ratio = catalogue_items_total / len(events_seen) if len(events_seen) else 0
        if catalogue_items_total > 10 * len(events_seen):
            logger.warning("[DIAG] NORMALIZATION_SUSPECT: catalogue_items_total=%d >> events_discovered=%d (ratio %.1f) -- check dropped reasons",
                           catalogue_items_total, len(events_seen), catalogue_to_events_ratio)
    
    for cat, stored_type in all_catalogues:
        market_id = str(_get_attr(cat, "marketId", "market_id") or "")
        if not market_id:
            skipped_other += 1
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
                conn.rollback()
                logger.warning("Event upsert skip event_id=%s: %s", event_id, e)
                skipped_other += 1
        market_name = None
        desc = _get_attr(cat, "description", "market_description")
        if desc:
            market_name = _get_attr(desc, "marketName", "market_name")
        market_start_time = _get_attr(cat, "marketStartTime", "market_start_time")
        try:
            _upsert_market(conn, market_id, str(event_id), stored_type, market_name, market_start_time)
            try:
                _upsert_runners(conn, market_id, [r if isinstance(r, dict) else {"selectionId": getattr(r, "selectionId", None), "runnerName": getattr(r, "runnerName", None)} for r in runners_cat])
            except Exception as re:
                conn.rollback()
                logger.debug("Runners upsert skip market_id=%s (e.g. FK to public.markets): %s", market_id, re)
            markets_stored += 1
            markets_by_type[stored_type] = markets_by_type.get(stored_type, 0) + 1
        except Exception as e:
            conn.rollback()
            logger.warning("Market upsert skip market_id=%s: %s", market_id, e)
            skipped_other += 1
        meta_row = _extract_metadata_row(cat)
        if meta_row:
            metadata_to_upsert += 1
            try:
                _upsert_metadata(conn, meta_row)
            except Exception as e:
                conn.rollback()
                logger.warning("Metadata upsert skip market_id=%s: %s", market_id, e)
                skipped_other += 1

    # Top 10 competitions by market count
    competition_market_counts.sort(key=lambda x: x[1], reverse=True)
    top10 = competition_market_counts[:10]

    # Step 2: DB after discovery + deltas
    rest_events_after, rest_markets_after = _get_db_counts(conn)
    delta_events = rest_events_after - rest_events_before
    delta_markets = rest_markets_after - rest_markets_before
    logger.info("[DIAG] db_after rest_events=%d rest_markets=%d delta_events=%d delta_markets=%d",
                rest_events_after, rest_markets_after, delta_events, delta_markets)

    # Step 3 & 4: DB coverage checks (today UTC)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _run_db_coverage_checks(conn, today_str)

    logger.info("=== DISCOVERY SUMMARY ===")
    logger.info("[DIAG] competitions_total=%d competitions_succeeded=%d competitions_failed=%d competitions_returning_0=%d competitions_returning_gt0=%d",
                competitions_total, competitions_succeeded, competitions_failed, competitions_returning_0, competitions_returning_gt0)
    logger.info("[DIAG] catalogue_items_total=%d events_discovered=%d events_stored=%d markets_stored=%d",
                catalogue_items_total, len(events_seen), events_stored, markets_stored)
    logger.info("[DIAG] markets_stored_by_type: %s", markets_by_type)
    logger.info("[DIAG] dropped_by_reason: HT=%d normalize=%d other=%d", skipped_ht, skipped_normalize, skipped_other)
    logger.info("Top 10 competitions by market count: %s", [(cid, n) for cid, n in top10])
    if dropped_samples:
        logger.info("Sample dropped items (first %d): %s", len(dropped_samples),
                    [(d["market_id"], d["market_type"], d["reason"]) for d in dropped_samples[:5]])
    logger.info("=== DISCOVERY DIAGNOSTICS END ===")

    return {
        "competitions_total": competitions_total,
        "competitions_succeeded": competitions_succeeded,
        "competitions_failed": competitions_failed,
        "catalogue_items_total": catalogue_items_total,
        "events_discovered": len(events_seen),
        "events_stored": events_stored,
        "markets_stored": markets_stored,
        "markets_by_type": markets_by_type,
        "skipped_ht": skipped_ht,
        "skipped_normalize": skipped_normalize,
        "skipped_other": skipped_other,
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
        logger.info("Discovery complete: competitions=%d/%d catalogue_items=%d events_discovered=%s events_stored=%s markets_stored=%s",
                    counts["competitions_succeeded"], counts["competitions_total"], counts["catalogue_items_total"],
                    counts["events_discovered"], counts["events_stored"], counts["markets_stored"])
        conn.commit()  # Ensure discovery transaction is committed before follow-up

        try:
            events_needing = _get_events_needing_next_goal_followup(conn)
            if events_needing:
                fu = run_next_goal_followups(trading, conn, events_needing)
                logger.info("NEXT_GOAL follow-up: attempted=%s found=%s", fu["attempted"], fu["found"])
        except Exception as e:
            logger.warning("NEXT_GOAL follow-up failed: %s", e)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
