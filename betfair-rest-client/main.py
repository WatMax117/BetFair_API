#!/usr/bin/env python3
"""
Betfair REST client daemon – production-grade with Risk Index.
Event-based sleep, jittered backoff, tick deadline, dual heartbeats, session handling, PostgreSQL persistence.
"""
import json
import logging
import os
import random
import signal
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# -----------------------------------------------------------------------------
# Configuration from environment only
# -----------------------------------------------------------------------------
USERNAME = os.environ.get("BF_USERNAME") or os.environ.get("BETFAIR_USERNAME")
PASSWORD = os.environ.get("BF_PASSWORD") or os.environ.get("BETFAIR_PASSWORD")
APP_KEY = os.environ.get("BF_APP_KEY") or os.environ.get("BETFAIR_APP_KEY")
CERT_PATH = os.environ.get("BF_CERT_PATH", "/app/certs/client-2048.crt")
KEY_PATH = os.environ.get("BF_KEY_PATH", "/app/certs/client-2048.key")
HEARTBEAT_ALIVE_PATH = os.environ.get("BF_HEARTBEAT_ALIVE", "/app/data/heartbeat_alive")
HEARTBEAT_SUCCESS_PATH = os.environ.get("BF_HEARTBEAT_SUCCESS", "/app/data/heartbeat_success")
DEBUG_JSON = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
INTERVAL_SECONDS = int(os.environ.get("BF_INTERVAL_SECONDS", "900"))
TICK_DEADLINE_SECONDS = int(os.environ.get("BF_TICK_DEADLINE_SECONDS", "600"))  # 10 min
WINDOW_HOURS = float(os.environ.get("BF_WINDOW_HOURS", "24"))
LOOKBACK_MINUTES = int(os.environ.get("BF_LOOKBACK_MINUTES", "60"))
BACKOFF_BASE = [10, 30, 60]  # jitter 0.8–1.2 applied per delay
MARKET_BOOK_TOP_N = int(os.environ.get("BF_MARKET_BOOK_TOP_N", "10"))
DEPTH_LIMIT = int(os.environ.get("BF_DEPTH_LIMIT", "3"))
SINGLE_SHOT = os.environ.get("BF_SINGLE_SHOT", "").lower() in ("1", "true", "yes")
DEBUG_MARKET_SAMPLE_PATH = os.environ.get("DEBUG_MARKET_SAMPLE_PATH", "/opt/netbet/betfair-rest-client/debug_market_sample.json")

# PostgreSQL (optional – Risk Index persistence)
POSTGRES_HOST = os.environ.get("POSTGRES_HOST") or os.environ.get("BF_POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT") or os.environ.get("BF_POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if DEBUG_JSON else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("betfair_rest_client")

_shutdown_requested = False
_trading_client = None
_tick_id = 0
_sleep_event = threading.Event()


def _request_shutdown(*_args):
    global _shutdown_requested
    _shutdown_requested = True
    _sleep_event.set()
    logger.info("Shutdown requested (SIGTERM/SIGINT), will exit after current work.")


def _touch_heartbeat_alive():
    try:
        Path(HEARTBEAT_ALIVE_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(HEARTBEAT_ALIVE_PATH).write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not write heartbeat_alive %s: %s", HEARTBEAT_ALIVE_PATH, e)


def _touch_heartbeat_success():
    try:
        Path(HEARTBEAT_SUCCESS_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(HEARTBEAT_SUCCESS_PATH).write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not write heartbeat_success %s: %s", HEARTBEAT_SUCCESS_PATH, e)


def _past_deadline(start_ts: float) -> bool:
    return (time.monotonic() - start_ts) > TICK_DEADLINE_SECONDS


def is_session_error(ex: Exception) -> bool:
    """True if exception indicates session/auth failure: INVALID_SESSION, TIMEOUT, or Betfair auth codes."""
    msg = str(ex).upper()
    if "INVALID_SESSION" in msg or "SESSION_EXPIRED" in msg or "SESSION EXPIRED" in msg:
        return True
    if "TIMEOUT" in msg or "TIMED OUT" in msg:
        return True
    if "LOGIN_REQUIRED" in msg or "AUTHENTICATION" in msg or "NO_SESSION" in msg:
        return True
    # Betfair API error code in JSON/dict
    if hasattr(ex, "error_code"):
        code = getattr(ex, "error_code", None)
        if code in ("INVALID_SESSION_INFORMATION", "SESSION_EXPIRED", "NO_SESSION"):
            return True
    return False


def _ensure_session(trading):
    if getattr(trading, "session_expired", True):
        logger.info("Session expired or missing, performing login...")
        try:
            trading.login()
        except Exception as e:
            logger.exception("Login failed: %s", e)
            return False
    else:
        try:
            trading.keep_alive()
        except Exception as e:
            logger.warning("keep_alive failed (%s), will re-login", e)
            try:
                trading.login()
            except Exception as e2:
                logger.exception("Re-login after keep_alive failed: %s", e2)
                return False
    if getattr(trading, "session_expired", True):
        logger.error("Session still expired after login.")
        return False
    return True


def _backoff_delays():
    return [max(1, int(d * random.uniform(0.8, 1.2))) for d in BACKOFF_BASE]


def _run_with_backoff(fn, *args, **kwargs):
    """Retry with jittered exponential backoff. On session error, re-raise (skip backoff)."""
    last_error = None
    for attempt, delay in enumerate(_backoff_delays()):
        try:
            return True, fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if is_session_error(e):
                logger.warning("Session error (attempt %d): %s", attempt + 1, e)
                raise
            logger.warning("API/network error (attempt %d/%d): %s", attempt + 1, len(BACKOFF_BASE), e)
        if attempt < len(BACKOFF_BASE) - 1 and not _shutdown_requested:
            logger.info("Backoff: waiting %ds before retry...", delay)
            _sleep_event.wait(timeout=delay)
    return False, last_error


def _fetch_catalogue(trading, start_ts: float):
    from betfairlightweight import filters

    if _past_deadline(start_ts):
        raise TimeoutError("Tick deadline exceeded before catalogue")
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(minutes=LOOKBACK_MINUTES)
    to_ts = now + timedelta(hours=WINDOW_HOURS)
    time_range = filters.time_range(from_=from_ts, to=to_ts)
    market_filter = filters.market_filter(
        event_type_ids=[1],
        market_type_codes=["MATCH_ODDS"],
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
        max_results=max(200, MARKET_BOOK_TOP_N),
        sort="MAXIMUM_TRADED",
    )


def _fetch_market_books(trading, market_ids, start_ts: float):
    from betfairlightweight import filters

    if _past_deadline(start_ts) or not market_ids:
        return []
    # EX_ALL_OFFERS so raw_payload has availableToBack/availableToLay for derived metrics
    price_proj = filters.price_projection(price_data=filters.price_data(ex_all_offers=True))
    return trading.betting.list_market_book(
        market_ids=market_ids,
        price_projection=price_proj,
    )


def _back_level_at(runner: Any, level: int) -> tuple:
    """Extract (price, size) from availableToBack level index (0=L1, 1=L2, 2=L3). Returns (0.0, 0.0) if missing or invalid."""
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


def _best_back_lay(runner: Any) -> tuple:
    """First-level best back and best lay from runner.ex. Returns (best_back, best_lay, best_back_size_l1, best_lay_size_l1); 0.0 if missing or invalid (price <= 1 or size <= 0)."""
    ex = runner.get("ex") if isinstance(runner, dict) else getattr(runner, "ex", None)
    if not ex:
        return 0.0, 0.0, 0.0, 0.0
    atb = ex.get("availableToBack") if isinstance(ex, dict) else getattr(ex, "availableToBack", None) or getattr(ex, "available_to_back", None)
    atl = ex.get("availableToLay") if isinstance(ex, dict) else getattr(ex, "availableToLay", None) or getattr(ex, "available_to_lay", None)
    best_back, best_lay = 0.0, 0.0
    best_back_size_l1, best_lay_size_l1 = 0.0, 0.0
    if atb and len(atb) > 0:
        lev = atb[0]
        if isinstance(lev, (list, tuple)) and len(lev) >= 1:
            best_back = _safe_float(lev[0])
            best_back_size_l1 = _safe_float(lev[1]) if len(lev) >= 2 else 0.0
        elif isinstance(lev, dict):
            best_back = _safe_float(lev.get("price") or lev.get("Price"))
            best_back_size_l1 = _safe_float(lev.get("size") or lev.get("Size") or 0)
        if best_back <= 1 or best_back_size_l1 <= 0:
            best_back_size_l1 = 0.0
    if atl and len(atl) > 0:
        lev = atl[0]
        if isinstance(lev, (list, tuple)) and len(lev) >= 1:
            best_lay = _safe_float(lev[0])
            best_lay_size_l1 = _safe_float(lev[1]) if len(lev) >= 2 else 0.0
        elif isinstance(lev, dict):
            best_lay = _safe_float(lev.get("price") or lev.get("Price"))
            best_lay_size_l1 = _safe_float(lev.get("size") or lev.get("Size") or 0)
        if best_lay <= 1 or best_lay_size_l1 <= 0:
            best_lay_size_l1 = 0.0
    return best_back, best_lay, best_back_size_l1, best_lay_size_l1


def _runner_best_prices(runners: list, runner_metadata: Dict) -> Dict[str, float]:
    """Build role -> best_back, best_lay and L1 sizes from runners and metadata. Keys: home_best_back, away_best_back, ..., home_best_back_size_l1, ..., home_best_lay_size_l1, ..."""
    by_sid = {}
    for r in runners:
        sid = r.get("selectionId") if isinstance(r, dict) else getattr(r, "selectionId", None) or getattr(r, "selection_id", None)
        if sid is not None:
            by_sid[sid] = r
    out = {}
    for sid_key, role in (runner_metadata or {}).items():
        role_lower = (role or "").lower()
        if role_lower not in ("home", "away", "draw"):
            continue
        r = by_sid.get(sid_key)
        if not r:
            continue
        best_back, best_lay, best_back_size_l1, best_lay_size_l1 = _best_back_lay(r)
        out[f"{role_lower}_best_back"] = best_back
        out[f"{role_lower}_best_lay"] = best_lay
        out[f"{role_lower}_best_back_size_l1"] = best_back_size_l1
        out[f"{role_lower}_best_lay_size_l1"] = best_lay_size_l1
        # L2 and L3 back levels
        odds_l2, size_l2 = _back_level_at(r, 1)
        odds_l3, size_l3 = _back_level_at(r, 2)
        out[f"{role_lower}_back_odds_l2"] = odds_l2 if odds_l2 > 0 else None
        out[f"{role_lower}_back_size_l2"] = size_l2 if size_l2 > 0 else None
        out[f"{role_lower}_back_odds_l3"] = odds_l3 if odds_l3 > 0 else None
        out[f"{role_lower}_back_size_l3"] = size_l3 if size_l3 > 0 else None
    return out


def _get_attr(obj: Any, key: str, *alt_keys: str):
    """Get attribute from dict or object; try key and alt_keys (e.g. snake and camel)."""
    if obj is None:
        return None
    for k in (key,) + alt_keys:
        if isinstance(obj, dict):
            if k in obj:
                return obj[k]
        else:
            v = getattr(obj, k, None)
            if v is not None:
                return v
    return None


def _extract_metadata_row(catalogue_entry: Any) -> Optional[Dict]:
    """
    Build one row for market_event_metadata from listMarketCatalogue entry.
    Uses sortPriority: 1=HOME, 2=AWAY, 3=DRAW. Returns None if mapping incomplete.
    """
    market_id = _get_attr(catalogue_entry, "market_id", "marketId")
    if not market_id:
        return None
    market_id = str(market_id)

    def _desc(attr: str, *alts: str):
        d = _get_attr(catalogue_entry, "description", "market_description")
        return _get_attr(d, attr, *alts) if d else None

    market_name = _desc("market_name", "marketName")
    market_start_time = _get_attr(catalogue_entry, "market_start_time", "marketStartTime")

    event = _get_attr(catalogue_entry, "event", "event")
    event_id = _get_attr(event, "id") if event else None
    event_name = _get_attr(event, "name") if event else None
    event_open_date = _get_attr(event, "open_date", "openDate") if event else None
    country_code = _get_attr(event, "country_code", "countryCode") if event else None

    comp = _get_attr(catalogue_entry, "competition", "competition")
    competition_id = _get_attr(comp, "id") if comp else None
    competition_name = _get_attr(comp, "name") if comp else None

    sport = _get_attr(catalogue_entry, "event_type", "eventType")
    sport_id = _get_attr(sport, "id") if sport else None
    sport_name = _get_attr(sport, "name") if sport else None

    timezone_val = _get_attr(event, "timezone") if event else None
    if event_id is not None:
        event_id = str(event_id)

    runners_cat = _get_attr(catalogue_entry, "runners")
    if not runners_cat or len(runners_cat) < 3:
        return None
    priority_to_role = {1: "HOME", 2: "AWAY", 3: "DRAW"}
    home_sid, away_sid, draw_sid = None, None, None
    home_name, away_name, draw_name = None, None, None
    for r in runners_cat:
        sp = _get_attr(r, "sort_priority", "sortPriority")
        if sp is None:
            continue
        sp = int(sp)
        if sp not in priority_to_role:
            continue
        role = priority_to_role[sp]
        sid = _get_attr(r, "selection_id", "selectionId")
        rname = _get_attr(r, "runner_name", "runnerName")
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
        "market_id": market_id,
        "market_name": market_name,
        "market_start_time": market_start_time,
        "sport_id": str(sport_id) if sport_id is not None else None,
        "sport_name": sport_name,
        "event_id": event_id,
        "event_name": event_name,
        "event_open_date": event_open_date,
        "country_code": country_code,
        "competition_id": str(competition_id) if competition_id is not None else None,
        "competition_name": competition_name,
        "timezone": timezone_val,
        "home_selection_id": home_sid,
        "away_selection_id": away_sid,
        "draw_selection_id": draw_sid,
        "home_runner_name": home_name,
        "away_runner_name": away_name,
        "draw_runner_name": draw_name,
        "metadata_version": "v1",
    }


def _ensure_three_layer_tables(conn):
    """Create Layer 0/1/2 tables if not exist (idempotent)."""
    with conn.cursor() as cur:
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_book_snapshots (
                snapshot_id BIGSERIAL PRIMARY KEY,
                snapshot_at TIMESTAMPTZ NOT NULL,
                market_id TEXT NOT NULL REFERENCES market_event_metadata(market_id) ON DELETE CASCADE,
                raw_payload JSONB NOT NULL,
                total_matched DOUBLE PRECISION NULL, inplay BOOLEAN NULL, status TEXT NULL,
                depth_limit INTEGER NULL,
                source TEXT NOT NULL DEFAULT 'rest_listMarketBook',
                capture_version TEXT NULL DEFAULT 'v1'
            );
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mbs_market_snapshot_unique ON market_book_snapshots (market_id, snapshot_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mbs_market_id ON market_book_snapshots (market_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mbs_snapshot_at ON market_book_snapshots (snapshot_at);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_derived_metrics (
                snapshot_id BIGINT PRIMARY KEY REFERENCES market_book_snapshots(snapshot_id) ON DELETE CASCADE,
                snapshot_at TIMESTAMPTZ NOT NULL, market_id TEXT NOT NULL,
                home_risk DOUBLE PRECISION NOT NULL, away_risk DOUBLE PRECISION NOT NULL, draw_risk DOUBLE PRECISION NOT NULL,
                total_volume DOUBLE PRECISION NOT NULL,
                home_best_back DOUBLE PRECISION NULL, away_best_back DOUBLE PRECISION NULL, draw_best_back DOUBLE PRECISION NULL,
                home_best_lay DOUBLE PRECISION NULL, away_best_lay DOUBLE PRECISION NULL, draw_best_lay DOUBLE PRECISION NULL,
                home_spread DOUBLE PRECISION NULL, away_spread DOUBLE PRECISION NULL, draw_spread DOUBLE PRECISION NULL,
                depth_limit INTEGER NULL, calculation_version TEXT NULL DEFAULT 'v1'
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mdm_market_snapshot ON market_derived_metrics (market_id, snapshot_at);")
        for col in (
            "home_impedance", "away_impedance", "draw_impedance",
            "home_impedance_norm", "away_impedance_norm", "draw_impedance_norm",
            "home_book_risk_l3", "away_book_risk_l3", "draw_book_risk_l3",
            "home_back_stake", "home_back_odds", "home_lay_stake", "home_lay_odds",
            "away_back_stake", "away_back_odds", "away_lay_stake", "away_lay_odds",
            "draw_back_stake", "draw_back_odds", "draw_lay_stake", "draw_lay_odds",
            "home_best_back_size_l1", "away_best_back_size_l1", "draw_best_back_size_l1",
            "home_best_lay_size_l1", "away_best_lay_size_l1", "draw_best_lay_size_l1",
            "home_back_odds_l2", "home_back_size_l2", "home_back_odds_l3", "home_back_size_l3",
            "away_back_odds_l2", "away_back_size_l2", "away_back_odds_l3", "away_back_size_l3",
            "draw_back_odds_l2", "draw_back_size_l2", "draw_back_odds_l3", "draw_back_size_l3",
        ):
            cur.execute(
                """
                DO $$ BEGIN
                    ALTER TABLE market_derived_metrics ADD COLUMN """ + col + """ DOUBLE PRECISION NULL;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
    conn.commit()


def _upsert_metadata(conn, row: Dict):
    """Upsert market_event_metadata by market_id; set last_seen_at=NOW(); overwrite selection/names only if new non-null."""
    with conn.cursor() as cur:
        cur.execute(
            """
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
            """,
            {
                "market_id": row["market_id"],
                "market_name": row.get("market_name"),
                "market_start_time": row.get("market_start_time"),
                "sport_id": row.get("sport_id"),
                "sport_name": row.get("sport_name"),
                "event_id": row.get("event_id"),
                "event_name": row.get("event_name"),
                "event_open_date": row.get("event_open_date"),
                "country_code": row.get("country_code"),
                "competition_id": row.get("competition_id"),
                "competition_name": row.get("competition_name"),
                "timezone": row.get("timezone"),
                "home_selection_id": row.get("home_selection_id"),
                "away_selection_id": row.get("away_selection_id"),
                "draw_selection_id": row.get("draw_selection_id"),
                "home_runner_name": row.get("home_runner_name"),
                "away_runner_name": row.get("away_runner_name"),
                "draw_runner_name": row.get("draw_runner_name"),
                "metadata_version": row.get("metadata_version", "v1"),
            },
        )
    conn.commit()


def _insert_raw_snapshot(
    conn, snapshot_at, market_id: str, raw_payload: dict,
    total_matched=None, inplay=None, status=None, depth_limit=None,
) -> Optional[int]:
    """Insert one row into market_book_snapshots; return snapshot_id or None."""
    import psycopg2
    from psycopg2.extras import Json
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_book_snapshots (
                snapshot_at, market_id, raw_payload, total_matched, inplay, status, depth_limit, source, capture_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'rest_listMarketBook', 'v1')
            RETURNING snapshot_id
            """,
            (
                snapshot_at, market_id, Json(raw_payload) if isinstance(raw_payload, dict) else raw_payload,
                _safe_float(total_matched) if total_matched is not None else None,
                inplay, status, depth_limit,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None


def _insert_derived_metrics(conn, snapshot_id: int, snapshot_at, market_id: str, metrics: Dict):
    """Insert one row into market_derived_metrics (no raw_payload). Includes optional impedance and impedance-input columns."""
    params = {
        "snapshot_id": snapshot_id, "snapshot_at": snapshot_at, "market_id": market_id,
        "home_risk": metrics["home_risk"], "away_risk": metrics["away_risk"],
        "draw_risk": metrics["draw_risk"], "total_volume": metrics["total_volume"],
        "home_best_back": metrics.get("home_best_back"), "away_best_back": metrics.get("away_best_back"),
        "draw_best_back": metrics.get("draw_best_back"),
        "home_best_lay": metrics.get("home_best_lay"), "away_best_lay": metrics.get("away_best_lay"),
        "draw_best_lay": metrics.get("draw_best_lay"),
        "home_spread": metrics.get("home_spread"), "away_spread": metrics.get("away_spread"),
        "draw_spread": metrics.get("draw_spread"),
        "depth_limit": metrics.get("depth_limit"),
        "calculation_version": metrics.get("calculation_version", "v1"),
        "home_impedance": metrics.get("home_impedance"), "away_impedance": metrics.get("away_impedance"),
        "draw_impedance": metrics.get("draw_impedance"),
        "home_impedance_norm": metrics.get("home_impedance_norm"),
        "away_impedance_norm": metrics.get("away_impedance_norm"),
        "draw_impedance_norm": metrics.get("draw_impedance_norm"),
        "home_book_risk_l3": metrics.get("home_book_risk_l3"),
        "away_book_risk_l3": metrics.get("away_book_risk_l3"),
        "draw_book_risk_l3": metrics.get("draw_book_risk_l3"),
        "home_back_stake": metrics.get("home_back_stake"), "home_back_odds": metrics.get("home_back_odds"),
        "home_lay_stake": metrics.get("home_lay_stake"), "home_lay_odds": metrics.get("home_lay_odds"),
        "away_back_stake": metrics.get("away_back_stake"), "away_back_odds": metrics.get("away_back_odds"),
        "away_lay_stake": metrics.get("away_lay_stake"), "away_lay_odds": metrics.get("away_lay_odds"),
        "draw_back_stake": metrics.get("draw_back_stake"), "draw_back_odds": metrics.get("draw_back_odds"),
        "draw_lay_stake": metrics.get("draw_lay_stake"), "draw_lay_odds": metrics.get("draw_lay_odds"),
        "home_best_back_size_l1": metrics.get("home_best_back_size_l1"),
        "away_best_back_size_l1": metrics.get("away_best_back_size_l1"),
        "draw_best_back_size_l1": metrics.get("draw_best_back_size_l1"),
        "home_best_lay_size_l1": metrics.get("home_best_lay_size_l1"),
        "away_best_lay_size_l1": metrics.get("away_best_lay_size_l1"),
        "draw_best_lay_size_l1": metrics.get("draw_best_lay_size_l1"),
        "home_back_odds_l2": metrics.get("home_back_odds_l2"),
        "home_back_size_l2": metrics.get("home_back_size_l2"),
        "home_back_odds_l3": metrics.get("home_back_odds_l3"),
        "home_back_size_l3": metrics.get("home_back_size_l3"),
        "away_back_odds_l2": metrics.get("away_back_odds_l2"),
        "away_back_size_l2": metrics.get("away_back_size_l2"),
        "away_back_odds_l3": metrics.get("away_back_odds_l3"),
        "away_back_size_l3": metrics.get("away_back_size_l3"),
        "draw_back_odds_l2": metrics.get("draw_back_odds_l2"),
        "draw_back_size_l2": metrics.get("draw_back_size_l2"),
        "draw_back_odds_l3": metrics.get("draw_back_odds_l3"),
        "draw_back_size_l3": metrics.get("draw_back_size_l3"),
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_derived_metrics (
                snapshot_id, snapshot_at, market_id,
                home_risk, away_risk, draw_risk, total_volume,
                home_best_back, away_best_back, draw_best_back,
                home_best_lay, away_best_lay, draw_best_lay,
                home_spread, away_spread, draw_spread,
                depth_limit, calculation_version,
                home_impedance, away_impedance, draw_impedance,
                home_impedance_norm, away_impedance_norm, draw_impedance_norm,
                home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
                home_back_stake, home_back_odds, home_lay_stake, home_lay_odds,
                away_back_stake, away_back_odds, away_lay_stake, away_lay_odds,
                draw_back_stake, draw_back_odds, draw_lay_stake, draw_lay_odds,
                home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1,
                home_best_lay_size_l1, away_best_lay_size_l1, draw_best_lay_size_l1,
                home_back_odds_l2, home_back_size_l2, home_back_odds_l3, home_back_size_l3,
                away_back_odds_l2, away_back_size_l2, away_back_odds_l3, away_back_size_l3,
                draw_back_odds_l2, draw_back_size_l2, draw_back_odds_l3, draw_back_size_l3
            )
            VALUES (
                %(snapshot_id)s, %(snapshot_at)s, %(market_id)s,
                %(home_risk)s, %(away_risk)s, %(draw_risk)s, %(total_volume)s,
                %(home_best_back)s, %(away_best_back)s, %(draw_best_back)s,
                %(home_best_lay)s, %(away_best_lay)s, %(draw_best_lay)s,
                %(home_spread)s, %(away_spread)s, %(draw_spread)s,
                %(depth_limit)s, %(calculation_version)s,
                %(home_impedance)s, %(away_impedance)s, %(draw_impedance)s,
                %(home_impedance_norm)s, %(away_impedance_norm)s, %(draw_impedance_norm)s,
                %(home_book_risk_l3)s, %(away_book_risk_l3)s, %(draw_book_risk_l3)s,
                %(home_back_stake)s, %(home_back_odds)s, %(home_lay_stake)s, %(home_lay_odds)s,
                %(away_back_stake)s, %(away_back_odds)s, %(away_lay_stake)s, %(away_lay_odds)s,
                %(draw_back_stake)s, %(draw_back_odds)s, %(draw_lay_stake)s, %(draw_lay_odds)s,
                %(home_best_back_size_l1)s, %(away_best_back_size_l1)s, %(draw_best_back_size_l1)s,
                %(home_best_lay_size_l1)s, %(away_best_lay_size_l1)s, %(draw_best_lay_size_l1)s,
                %(home_back_odds_l2)s, %(home_back_size_l2)s, %(home_back_odds_l3)s, %(home_back_size_l3)s,
                %(away_back_odds_l2)s, %(away_back_size_l2)s, %(away_back_odds_l3)s, %(away_back_size_l3)s,
                %(draw_back_odds_l2)s, %(draw_back_size_l2)s, %(draw_back_odds_l3)s, %(draw_back_size_l3)s
            )
            """,
            params,
        )
    conn.commit()


def _get_conn():
    """Open DB connection for 3-layer persistence."""
    import psycopg2
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=10,
    )


def _runner_metadata_from_metadata_table(conn, market_id: str) -> Optional[Dict]:
    """Build selectionId -> HOME|AWAY|DRAW from market_event_metadata for risk/price computation."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT home_selection_id, away_selection_id, draw_selection_id
            FROM market_event_metadata WHERE market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
    if not row or row[0] is None or row[1] is None or row[2] is None:
        return None
    return {row[0]: "HOME", row[1]: "AWAY", row[2]: "DRAW"}


def _runner_metadata_from_catalogue(catalogue_entry: Any) -> Optional[Dict]:
    """
    Build selectionId -> role mapping from listMarketCatalogue runners.
    Map by sortPriority: 1=HOME, 2=AWAY, 3=DRAW (safer than list order).
    """
    runners_cat = catalogue_entry.get("runners") if isinstance(catalogue_entry, dict) else getattr(catalogue_entry, "runners", None)
    if not runners_cat or len(runners_cat) < 3:
        return None
    priority_to_role = {1: "HOME", 2: "AWAY", 3: "DRAW"}
    metadata = {}
    for r in runners_cat:
        sid = r.get("selectionId") if isinstance(r, dict) else getattr(r, "selectionId", None) or getattr(r, "selection_id", None)
        sp = r.get("sortPriority") if isinstance(r, dict) else getattr(r, "sortPriority", None) or getattr(r, "sort_priority", None)
        if sid is not None and sp is not None and int(sp) in priority_to_role:
            metadata[sid] = priority_to_role[int(sp)]
    return metadata if len(metadata) == 3 else None


def _tick(trading) -> bool:
    global _tick_id
    _tick_id += 1
    tick_id = _tick_id
    start_ts = time.monotonic()
    _touch_heartbeat_alive()

    if not _ensure_session(trading):
        return False

    # Fetch catalogue
    try:
        success, result = _run_with_backoff(_fetch_catalogue, trading, start_ts)
    except Exception as session_err:
        logger.warning("Session error, re-login and retry once: %s", session_err)
        if not _ensure_session(trading):
            return False
        success, result = _run_with_backoff(_fetch_catalogue, trading, start_ts)

    if not success or result is None:
        logger.error("listMarketCatalogue failed (non-fatal).")
        return False

    catalogues = result if isinstance(result, list) else []
    if not catalogues:
        logger.warning("listMarketCatalogue returned no markets.")
        _touch_heartbeat_success()
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        logger.info(
            "tick_id=%s duration_ms=%s markets_count=0",
            tick_id, duration_ms,
        )
        return True

    # Only 3-way markets (e.g. Match Odds); exclude 2-way (Draw No Bet, Tennis, etc.)
    def _runner_count(m):
        rc = m.get("runnerCount") if isinstance(m, dict) else getattr(m, "runnerCount", None) or getattr(m, "runner_count", None)
        if rc is not None:
            return int(rc) if str(rc).isdigit() else len(m.get("runners") or getattr(m, "runners", None) or [])
        return len(m.get("runners") or getattr(m, "runners", None) or [])
    catalogues = [c for c in catalogues if _runner_count(c) == 3]
    if not catalogues:
        logger.warning("No markets with exactly 3 runners (filtered out 2-way markets).")
        _touch_heartbeat_success()
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        logger.info("tick_id=%s duration_ms=%s markets_count=0", tick_id, duration_ms)
        return True

    # 3-layer flow: upsert metadata for top N, then fetch books, then insert raw + derived per market.
    if not POSTGRES_PASSWORD:
        logger.warning("POSTGRES_PASSWORD not set; skipping 3-layer persistence.")
        _touch_heartbeat_success()
        return True

    snapshot_at = datetime.now(timezone.utc)
    market_ids = []
    try:
        conn = _get_conn()
        _ensure_three_layer_tables(conn)
        for m in catalogues[:MARKET_BOOK_TOP_N]:
            meta_row = _extract_metadata_row(m)
            if meta_row is None:
                continue
            _upsert_metadata(conn, meta_row)
            market_ids.append(meta_row["market_id"])
        conn.close()
    except Exception as e:
        logger.warning("Metadata upsert failed: %s", e)
        _touch_heartbeat_success()
        return True

    if not market_ids:
        logger.warning("No markets with complete metadata mapping (HOME/AWAY/DRAW).")
        _touch_heartbeat_success()
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        logger.info("tick_id=%s duration_ms=%s markets_count=0", tick_id, duration_ms)
        return True

    if _past_deadline(start_ts):
        logger.warning("Tick deadline exceeded after catalogue.")
        return False

    try:
        success, books_result = _run_with_backoff(_fetch_market_books, trading, market_ids, start_ts)
    except Exception as session_err:
        if not _ensure_session(trading):
            return False
        success, books_result = _run_with_backoff(_fetch_market_books, trading, market_ids, start_ts)

    if not success:
        logger.error("listMarketBook failed (non-fatal).")
        return False

    books = books_result if isinstance(books_result, list) else []
    from risk import calculate_risk, compute_impedance_index, compute_book_risk_l3

    risk_by_market = []
    try:
        conn = _get_conn()
        for book in books:
            if _past_deadline(start_ts):
                break
            market_id = book.get("marketId") if isinstance(book, dict) else getattr(book, "market_id", None) or getattr(book, "marketId", None)
            if not market_id:
                continue
            market_id = str(market_id)
            runners = book.get("runners") if isinstance(book, dict) else getattr(book, "runners", None) or []
            if len(runners) < 3:
                continue
            runner_metadata = _runner_metadata_from_metadata_table(conn, market_id)
            if not runner_metadata:
                logger.warning("Skipping market %s: no metadata mapping in DB.", market_id)
                continue
            if isinstance(book, dict):
                book_dict = book
            else:
                book_dict = getattr(book, "json", None) or (getattr(book, "__dict__", None) or {})
                if not isinstance(book_dict, dict):
                    book_dict = {"marketId": market_id, "runners": []}
            total_matched = book.get("totalMatched") if isinstance(book, dict) else getattr(book, "totalMatched", None) or getattr(book, "total_matched", None)
            inplay = book.get("inplay") if isinstance(book, dict) else getattr(book, "inplay", None)
            status = book.get("status") if isinstance(book, dict) else getattr(book, "status", None)

            snapshot_id = _insert_raw_snapshot(
                conn, snapshot_at, market_id, book_dict,
                total_matched=total_matched, inplay=inplay, status=status, depth_limit=DEPTH_LIMIT,
            )
            if snapshot_id is None:
                continue

            impedance_out = compute_impedance_index(runners, snapshot_ts=snapshot_at)
            home_impedance = away_impedance = draw_impedance = None
            home_impedance_norm = away_impedance_norm = draw_impedance_norm = None
            home_back_stake = home_back_odds = home_lay_stake = home_lay_odds = None
            away_back_stake = away_back_odds = away_lay_stake = away_lay_odds = None
            draw_back_stake = draw_back_odds = draw_lay_stake = draw_lay_odds = None
            if impedance_out and impedance_out.get("runners"):
                for ro in impedance_out["runners"]:
                    logger.info(
                        "[Impedance] market=%s selectionId=%s impedance=%.2f normImpedance=%.4f backStake=%.2f backOdds=%.2f layStake=%.2f layOdds=%.2f",
                        market_id,
                        ro.get("selectionId"),
                        ro.get("impedance", 0),
                        ro.get("normImpedance", 0),
                        ro.get("backStake", 0),
                        ro.get("backOdds", 0),
                        ro.get("layStake", 0),
                        ro.get("layOdds", 0),
                    )
                for ro in impedance_out["runners"]:
                    sid = ro.get("selectionId")
                    role = (runner_metadata.get(sid) or "").strip().upper() if sid is not None else None
                    if not role and sid is not None:
                        try:
                            role = (runner_metadata.get(int(sid)) or "").strip().upper()
                        except (TypeError, ValueError):
                            pass
                    if role == "HOME":
                        home_impedance = ro.get("impedance")
                        home_impedance_norm = ro.get("normImpedance")
                        home_back_stake = ro.get("backStake")
                        home_back_odds = ro.get("backOdds")
                        home_lay_stake = ro.get("layStake")
                        home_lay_odds = ro.get("layOdds")
                    elif role == "AWAY":
                        away_impedance = ro.get("impedance")
                        away_impedance_norm = ro.get("normImpedance")
                        away_back_stake = ro.get("backStake")
                        away_back_odds = ro.get("backOdds")
                        away_lay_stake = ro.get("layStake")
                        away_lay_odds = ro.get("layOdds")
                    elif role == "DRAW":
                        draw_impedance = ro.get("impedance")
                        draw_impedance_norm = ro.get("normImpedance")
                        draw_back_stake = ro.get("backStake")
                        draw_back_odds = ro.get("backOdds")
                        draw_lay_stake = ro.get("layStake")
                        draw_lay_odds = ro.get("layOdds")

            result = calculate_risk(runners, runner_metadata, depth_limit=DEPTH_LIMIT, market_total_matched=total_matched)
            if result is None:
                continue
            home_risk, away_risk, draw_risk, total_volume, _ = result
            book_risk_l3 = compute_book_risk_l3(runners, runner_metadata, depth_limit=DEPTH_LIMIT)
            best_prices = _runner_best_prices(runners, runner_metadata)
            def _spread(back, lay):
                if back is not None and lay is not None:
                    return float(lay) - float(back)
                return None
            home_spread = _spread(best_prices.get("home_best_back"), best_prices.get("home_best_lay"))
            away_spread = _spread(best_prices.get("away_best_back"), best_prices.get("away_best_lay"))
            draw_spread = _spread(best_prices.get("draw_best_back"), best_prices.get("draw_best_lay"))
            metrics = {
                "home_risk": home_risk, "away_risk": away_risk, "draw_risk": draw_risk,
                "total_volume": total_volume, "depth_limit": DEPTH_LIMIT, "calculation_version": "imbalance_v1",
                **best_prices,
                "home_spread": home_spread, "away_spread": away_spread, "draw_spread": draw_spread,
                "home_impedance": home_impedance, "away_impedance": away_impedance, "draw_impedance": draw_impedance,
                "home_impedance_norm": home_impedance_norm, "away_impedance_norm": away_impedance_norm, "draw_impedance_norm": draw_impedance_norm,
                "home_book_risk_l3": (book_risk_l3 or {}).get("home_book_risk_l3"),
                "away_book_risk_l3": (book_risk_l3 or {}).get("away_book_risk_l3"),
                "draw_book_risk_l3": (book_risk_l3 or {}).get("draw_book_risk_l3"),
                "home_back_stake": home_back_stake, "home_back_odds": home_back_odds, "home_lay_stake": home_lay_stake, "home_lay_odds": home_lay_odds,
                "away_back_stake": away_back_stake, "away_back_odds": away_back_odds, "away_lay_stake": away_lay_stake, "away_lay_odds": away_lay_odds,
                "draw_back_stake": draw_back_stake, "draw_back_odds": draw_back_odds, "draw_lay_stake": draw_lay_stake, "draw_lay_odds": draw_lay_odds,
            }
            _insert_derived_metrics(conn, snapshot_id, snapshot_at, market_id, metrics)
            risk_by_market.append((market_id, home_risk, away_risk, draw_risk, total_volume))
        conn.close()
    except Exception as e:
        logger.warning("3-layer persist failed: %s", e)

    duration_ms = int((time.monotonic() - start_ts) * 1000)
    markets_count = len(risk_by_market)

    # Log: tick_id, duration_ms, markets_count; then [Imbalance] per market
    logger.info(
        "tick_id=%s duration_ms=%s markets_count=%s",
        tick_id, duration_ms, markets_count,
    )
    for mid, hr, ar, dr, vol in risk_by_market:
        logger.info(
            "[Imbalance] Market: %s | H: %.2f | A: %.2f | D: %.2f | Vol: %.2f",
            mid, hr, ar, dr, vol,
        )

    if DEBUG_JSON and risk_by_market:
        logger.debug("Risk by market: %s", risk_by_market)

    _touch_heartbeat_success()
    return True


def _run_single_shot(trading) -> bool:
    """
    Single-shot: fetch one Match Odds market, log login, print raw JSON, save to file, insert with raw_payload, exit.
    """
    if not _ensure_session(trading):
        logger.error("Login FAILED.")
        return False
    logger.info("Login SUCCESS.")

    start_ts = time.monotonic()
    catalogues = []
    try:
        success, result = _run_with_backoff(_fetch_catalogue, trading, start_ts)
        if success and result:
            catalogues = result if isinstance(result, list) else []
    except Exception as e:
        logger.exception("Catalogue fetch failed: %s", e)
        return False

    def _runner_count(m):
        rc = m.get("runnerCount") if isinstance(m, dict) else getattr(m, "runnerCount", None) or getattr(m, "runner_count", None)
        if rc is not None:
            return int(rc) if str(rc).isdigit() else len(m.get("runners") or getattr(m, "runners", None) or [])
        return len(m.get("runners") or getattr(m, "runners", None) or [])
    catalogues = [c for c in catalogues if _runner_count(c) == 3]
    if not catalogues:
        logger.warning("No markets with exactly 3 runners.")
        return False

    first_market_id = None
    for m in catalogues[:1]:
        mid = m.get("marketId") if isinstance(m, dict) else getattr(m, "market_id", None) or getattr(m, "marketId", None)
        if mid:
            first_market_id = str(mid)
            break
    if not first_market_id:
        logger.warning("No market id in catalogue.")
        return False

    logger.info("Fetching listMarketBook for single market: %s", first_market_id)
    try:
        success, books_result = _run_with_backoff(_fetch_market_books, trading, [first_market_id], start_ts)
    except Exception as e:
        logger.exception("listMarketBook failed: %s", e)
        return False
    if not success or not books_result:
        logger.error("listMarketBook returned no data.")
        return False

    books = books_result if isinstance(books_result, list) else []
    if not books:
        logger.error("No market book returned.")
        return False
    book = books[0]
    if isinstance(book, dict):
        book_dict = book
    else:
        book_dict = getattr(book, "json", None) or (getattr(book, "__dict__", None) or {})
        if not isinstance(book_dict, dict):
            book_dict = {"marketId": first_market_id, "raw": str(book)}
    raw_json_str = json.dumps(book_dict, indent=2, default=str)

    logger.info("Raw market JSON (single market):\n%s", raw_json_str)

    market_total = _safe_float(book.get("totalMatched") if isinstance(book, dict) else getattr(book, "totalMatched", None) or getattr(book, "total_matched", None))
    runner_total_matched_values = []
    for r in (book.get("runners") if isinstance(book, dict) else getattr(book, "runners", None) or []):
        tm = r.get("totalMatched", r.get("total_matched")) if isinstance(r, dict) else (getattr(r, "totalMatched", None) or getattr(r, "total_matched", None))
        runner_total_matched_values.append(_safe_float(tm))
    logger.info(
        "Phase A confirmation: runner.totalMatched for all selections = %s (all zero: %s); market.totalMatched = %s (>0: %s)",
        runner_total_matched_values, all(x == 0.0 for x in runner_total_matched_values), market_total, market_total > 0,
    )

    sample_path = Path(DEBUG_MARKET_SAMPLE_PATH)
    try:
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(raw_json_str, encoding="utf-8")
        logger.info("Saved raw JSON to %s", sample_path)
    except Exception as e:
        logger.warning("Could not write debug sample file %s: %s", sample_path, e)

    cat = next((c for c in catalogues if (c.get("marketId") or getattr(c, "market_id", None) or getattr(c, "marketId")) == first_market_id), None)
    if not cat:
        logger.warning("Catalogue entry not found for market %s.", first_market_id)
        return False
    meta_row = _extract_metadata_row(cat)
    if not meta_row:
        logger.warning("Metadata mapping incomplete for market %s.", first_market_id)
        return False
    runners = book.get("runners") if isinstance(book, dict) else getattr(book, "runners", None) or []
    market_total_matched = book.get("totalMatched") if isinstance(book, dict) else getattr(book, "total_matched", None) or getattr(book, "totalMatched", None)
    inplay = book.get("inplay") if isinstance(book, dict) else getattr(book, "inplay", None)
    status = book.get("status") if isinstance(book, dict) else getattr(book, "status", None)

    if POSTGRES_PASSWORD:
        try:
            conn = _get_conn()
            _ensure_three_layer_tables(conn)
            _upsert_metadata(conn, meta_row)
            snapshot_at = datetime.now(timezone.utc)
            snapshot_id = _insert_raw_snapshot(
                conn, snapshot_at, first_market_id, book_dict,
                total_matched=market_total_matched, inplay=inplay, status=status, depth_limit=DEPTH_LIMIT,
            )
            if snapshot_id is not None and len(runners) >= 3:
                from risk import calculate_risk
                runner_metadata = _runner_metadata_from_metadata_table(conn, first_market_id)
                if runner_metadata:
                    result = calculate_risk(runners, runner_metadata, depth_limit=DEPTH_LIMIT, market_total_matched=market_total_matched)
                    if result:
                        hr, ar, dr, vol, _ = result
                        best_prices = _runner_best_prices(runners, runner_metadata)
                        def _s(b, l):
                            return float(l) - float(b) if b is not None and l is not None else None
                        home_spread = _s(best_prices.get("home_best_back"), best_prices.get("home_best_lay"))
                        away_spread = _s(best_prices.get("away_best_back"), best_prices.get("away_best_lay"))
                        draw_spread = _s(best_prices.get("draw_best_back"), best_prices.get("draw_best_lay"))
                        metrics = {
                            "home_risk": hr, "away_risk": ar, "draw_risk": dr, "total_volume": vol,
                            "depth_limit": DEPTH_LIMIT, "calculation_version": "imbalance_v1",
                            **best_prices,
                            "home_spread": home_spread, "away_spread": away_spread, "draw_spread": draw_spread,
                        }
                        _insert_derived_metrics(conn, snapshot_id, snapshot_at, first_market_id, metrics)
            conn.close()
        except Exception as e:
            logger.warning("3-layer persist failed: %s", e)
    logger.info("Single-shot complete: snapshot persisted (3-layer).")
    return True


def _safe_float(val: Any) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    if not all([USERNAME, PASSWORD, APP_KEY]):
        missing = [k for k, v in [("BF_USERNAME/BETFAIR_USERNAME", USERNAME), ("BF_PASSWORD/BETFAIR_PASSWORD", PASSWORD), ("BF_APP_KEY/BETFAIR_APP_KEY", APP_KEY)] if not v]
        logger.error("Missing required env: %s.", ", ".join(missing))
        return 1

    if not os.path.isfile(CERT_PATH) or not os.path.isfile(KEY_PATH):
        logger.error("Certificate or key file missing. CERT_PATH=%s KEY_PATH=%s", CERT_PATH, KEY_PATH)
        return 1

    import betfairlightweight

    global _trading_client
    _trading_client = betfairlightweight.APIClient(
        username=USERNAME,
        password=PASSWORD,
        app_key=APP_KEY,
        cert_files=(CERT_PATH, KEY_PATH),
        lightweight=True,
    )

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    if SINGLE_SHOT:
        logger.info("Single-shot mode: fetch one market, print raw JSON, save to file, persist with raw_payload, then exit.")
        try:
            _run_single_shot(_trading_client)
        except Exception as e:
            logger.exception("Single-shot failed: %s", e)
        logger.info("Shutting down (single-shot), closing Betfair session...")
        try:
            _trading_client.logout()
            logger.info("Logout completed.")
        except Exception as e:
            logger.warning("Logout failed: %s", e)
        return 0

    logger.info(
        "Daemon started. Interval=%ds, deadline=%ds, window_hours=%s, lookback_min=%s, heartbeat_alive=%s",
        INTERVAL_SECONDS, TICK_DEADLINE_SECONDS, WINDOW_HOURS, LOOKBACK_MINUTES, HEARTBEAT_ALIVE_PATH,
    )

    try:
        _tick(_trading_client)
    except Exception as e:
        logger.exception("Initial tick failed (non-fatal): %s", e)

    while not _shutdown_requested:
        if _sleep_event.wait(timeout=INTERVAL_SECONDS):
            if _shutdown_requested:
                break
        if _shutdown_requested:
            break
        try:
            _tick(_trading_client)
        except Exception as e:
            logger.exception("Cycle failed (non-fatal): %s", e)

    logger.info("Shutting down, closing Betfair session...")
    try:
        _trading_client.logout()
        logger.info("Logout completed.")
    except Exception as e:
        logger.warning("Logout failed: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
