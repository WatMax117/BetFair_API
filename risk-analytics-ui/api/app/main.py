"""
Risk Analytics API – read-only FastAPI service for 3-layer DB.
Endpoints: /api/leagues, /api/leagues/{league}/events, /api/events/{market_id}/timeseries

Do not log raw_payload, full snapshot rows, or full API responses (large JSON can break
IDE/agent serialization). Debug endpoints return scalar data only except /debug/snapshots/{id}/raw
which is on-demand and truncated when large.
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any, Literal
from urllib.parse import unquote

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.db import cursor
from app.stream_router import stream_router
from app.partition_provisioner import (
    start_background_provisioner,
    get_horizon_for_health,
    HORIZON_DEGRADE_THRESHOLD_DAYS,
)

# Max size for raw_payload in response to avoid huge payloads (IDE/agent serialization issues)
RAW_PAYLOAD_MAX_BYTES = 50 * 1024  # 50 KB

app = FastAPI(title="Risk Analytics API", version="1.0.0")
app.include_router(stream_router, prefix="/stream")


@app.on_event("startup")
def startup_partition_provisioner():
    """Start partition provisioner (stream_ingest.ladder_levels) on startup + every 12h."""
    start_background_provisioner()
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_ts(s: Optional[str], default: datetime) -> datetime:
    if not s:
        return default
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return default


def _safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _opt_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _price_size(level: Any) -> tuple[float, float]:
    """Extract (price, size) from a ladder level; supports [price, size] or {price, size}."""
    if isinstance(level, (list, tuple)) and len(level) >= 2:
        return _safe_float(level[0]), _safe_float(level[1])
    if isinstance(level, dict):
        p = _safe_float(level.get("price") or level.get("Price"))
        s = _safe_float(level.get("size") or level.get("Size"))
        return p, s
    return 0.0, 0.0


def _get_atb(runner: Any) -> list:
    """Get availableToBack list from runner.ex."""
    if not isinstance(runner, dict):
        return []
    ex = runner.get("ex")
    if not ex or not isinstance(ex, dict):
        return []
    atb = ex.get("availableToBack") or ex.get("available_to_back")
    return atb if isinstance(atb, list) else []


def _compute_back_depth_validators(
    raw_payload: Any,
    home_selection_id: Any,
    away_selection_id: Any,
    draw_selection_id: Any,
    depth_limit: Optional[int],
) -> dict[str, Optional[float]]:
    """
    From market_book_snapshots.raw_payload (market book with runners), compute per-runner
    back depth sums for the first N levels. N = depth_limit or 3. Returns 6 scalars.
    """
    out: dict[str, Optional[float]] = {
        "home_back_size_sum_N": None,
        "home_back_liability_sum_N": None,
        "away_back_size_sum_N": None,
        "away_back_liability_sum_N": None,
        "draw_back_size_sum_N": None,
        "draw_back_liability_sum_N": None,
    }
    if not isinstance(raw_payload, dict):
        return out
    runners = raw_payload.get("runners") or raw_payload.get("Runners")
    if not runners or not isinstance(runners, list):
        return out
    n = depth_limit if isinstance(depth_limit, int) and depth_limit > 0 else 3
    # Normalize selection IDs for lookup (API may return int or str)
    def _sid(r: Any) -> Optional[Any]:
        if not isinstance(r, dict):
            return None
        return r.get("selectionId") or r.get("selection_id")

    by_sid: dict[Any, Any] = {}
    for r in runners:
        sid = _sid(r)
        if sid is not None:
            by_sid[sid] = r
    # Map role -> runner using metadata selection IDs (int or str)
    def _runner(role_sid: Any) -> Optional[Any]:
        if role_sid is None:
            return None
        if role_sid in by_sid:
            return by_sid[role_sid]
        # Try int/str coercion
        try:
            k = int(role_sid)
            if k in by_sid:
                return by_sid[k]
        except (TypeError, ValueError):
            pass
        if str(role_sid) in by_sid:
            return by_sid[str(role_sid)]
        return None

    home_runner = _runner(home_selection_id)
    away_runner = _runner(away_selection_id)
    draw_runner = _runner(draw_selection_id)

    def _sums(runner: Any) -> tuple[float, float]:
        size_sum = 0.0
        liability_sum = 0.0
        atb = _get_atb(runner)
        for level in atb[:n]:
            price, size = _price_size(level)
            size_sum += size
            liability_sum += size * (price - 1.0)
        return size_sum, liability_sum

    if home_runner is not None:
        s, l = _sums(home_runner)
        out["home_back_size_sum_N"] = s
        out["home_back_liability_sum_N"] = l
    if away_runner is not None:
        s, l = _sums(away_runner)
        out["away_back_size_sum_N"] = s
        out["away_back_liability_sum_N"] = l
    if draw_runner is not None:
        s, l = _sums(draw_runner)
        out["draw_back_size_sum_N"] = s
        out["draw_back_liability_sum_N"] = l
    return out


def _compute_roi_toxic(out: dict[str, Any]) -> dict[str, Optional[float]]:
    """
    ROI Toxic (Uncovered ROI Pressure) at depth N.
    ROI_N(X) = back_liability_sum_N(X) / back_size_sum_N(X)  [profit per unit stake]
    Coverage_N(X) = back_size_sum_N(X) / TotalVolume  [participation]
    ROIToxic_N(X) = ROI_N(X) * (1 - Coverage_N(X))
    TotalVolume: mdm_total_volume preferred, else mbs_total_matched, else sum of back_size_sum_N.
    """
    result: dict[str, Optional[float]] = {
        "home_roi_N": None,
        "away_roi_N": None,
        "draw_roi_N": None,
        "home_coverage_N": None,
        "away_coverage_N": None,
        "draw_coverage_N": None,
        "home_roi_toxic_N": None,
        "away_roi_toxic_N": None,
        "draw_roi_toxic_N": None,
    }
    total_volume = _safe_float(out.get("mdm_total_volume")) or _safe_float(out.get("mbs_total_matched"))
    if total_volume <= 0:
        h = _safe_float(out.get("home_back_size_sum_N"))
        a = _safe_float(out.get("away_back_size_sum_N"))
        d = _safe_float(out.get("draw_back_size_sum_N"))
        total_volume = h + a + d
    if total_volume <= 0:
        return result

    for role in ("home", "away", "draw"):
        size = _opt_float(out.get(f"{role}_back_size_sum_N"))
        liab = _opt_float(out.get(f"{role}_back_liability_sum_N"))
        roi_n: Optional[float] = None
        if size is not None and size > 0 and liab is not None:
            roi_n = liab / size
        result[f"{role}_roi_N"] = roi_n

        coverage_n: Optional[float] = None
        if size is not None and total_volume > 0:
            coverage_n = size / total_volume
            coverage_n = max(0.0, min(1.0, coverage_n))
        result[f"{role}_coverage_N"] = coverage_n

        roi_toxic_n: Optional[float] = None
        if roi_n is not None and coverage_n is not None:
            roi_toxic_n = roi_n * (1.0 - coverage_n)
        result[f"{role}_roi_toxic_N"] = roi_toxic_n

    return result


@app.get("/health")
def health():
    horizon_days = get_horizon_for_health()
    payload = {"status": "ok"}
    if horizon_days is not None:
        payload["ladder_levels_partition_horizon_days"] = round(horizon_days, 1)
        if horizon_days < HORIZON_DEGRADE_THRESHOLD_DAYS:
            payload["status"] = "degraded"
            payload["detail"] = "partition horizon below threshold (stream_ingest.ladder_levels)"
    return payload


@app.get("/metrics")
def metrics():
    """Lightweight metrics for partition horizon (alert if ladder_levels_partition_horizon_days < 7)."""
    horizon_days = get_horizon_for_health()
    value = round(horizon_days, 1) if horizon_days is not None else -1.0
    body = "# HELP ladder_levels_partition_horizon_days Days of partition coverage ahead (stream_ingest.ladder_levels). Alert if < 7.\n"
    body += "# TYPE ladder_levels_partition_horizon_days gauge\n"
    body += f"ladder_levels_partition_horizon_days {value}\n"
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/leagues")
def get_leagues(
    from_ts: Optional[str] = Query(None, description="UTC ISO start"),
    to_ts: Optional[str] = Query(None, description="UTC ISO end"),
    q: Optional[str] = Query(None, description="Search substring (event/team name)"),
    include_in_play: bool = Query(False, description="Include events that have already started (in-play); default upcoming only"),
    in_play_lookback_hours: float = Query(2.0, ge=0, le=168, description="When include_in_play, extend window back this many hours for in-play (default 2h)"),
    limit: int = Query(100, ge=1, le=200, description="Max leagues to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List leagues (competition_name) with event counts. Default: current and upcoming only (now to now+48h UTC)."""
    now = datetime.now(timezone.utc)
    from_dt = _parse_ts(from_ts, now)
    to_dt = _parse_ts(to_ts, now + timedelta(hours=48))
    if include_in_play:
        in_play_from = now - timedelta(hours=in_play_lookback_hours)
        from_effective = min(from_dt, in_play_from)
    else:
        from_effective = from_dt

    search = f"%{q}%" if q else None
    with cursor() as cur:
        if search:
            cur.execute(
                """
                SELECT
                    e.competition_name AS league,
                    COUNT(DISTINCT e.market_id) AS event_count
                FROM market_event_metadata e
                WHERE e.event_open_date IS NOT NULL
                  AND e.event_open_date >= %s
                  AND e.event_open_date <= %s
                  AND (e.event_name ILIKE %s
                       OR e.home_runner_name ILIKE %s
                       OR e.away_runner_name ILIKE %s)
                GROUP BY e.competition_name
                ORDER BY COUNT(DISTINCT e.market_id) DESC, e.competition_name
                LIMIT %s OFFSET %s
                """,
                (from_effective, to_dt, search, search, search, limit, offset),
            )
        else:
            cur.execute(
                """
                SELECT
                    e.competition_name AS league,
                    COUNT(DISTINCT e.market_id) AS event_count
                FROM market_event_metadata e
                WHERE e.event_open_date IS NOT NULL
                  AND e.event_open_date >= %s
                  AND e.event_open_date <= %s
                GROUP BY e.competition_name
                ORDER BY COUNT(DISTINCT e.market_id) DESC, e.competition_name
                LIMIT %s OFFSET %s
                """,
                (from_effective, to_dt, limit, offset),
            )
        rows = cur.fetchall()
    return [{"league": r["league"], "event_count": r["event_count"]} for r in rows]


@app.get("/leagues/{league_name}/events")
def get_league_events(
    league_name: str,
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    include_in_play: bool = Query(False, description="Include in-play events; default upcoming only"),
    in_play_lookback_hours: float = Query(2.0, ge=0, le=168, description="When include_in_play, look back this many hours (default 2h)"),
    limit: int = Query(100, ge=1, le=200, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Events in the league with latest snapshot. Default: current and upcoming only (now to now+48h UTC), ORDER BY event_open_date ASC."""
    league_decoded = unquote(league_name)
    now = datetime.now(timezone.utc)
    from_dt = _parse_ts(from_ts, now)
    to_dt = _parse_ts(to_ts, now + timedelta(hours=48))
    if include_in_play:
        in_play_from = now - timedelta(hours=in_play_lookback_hours)
        from_effective = min(from_dt, in_play_from)
    else:
        from_effective = from_dt

    with cursor() as cur:
        cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (d.market_id)
                    d.market_id,
                    d.snapshot_id,
                    d.snapshot_at,
                    d.home_best_back, d.away_best_back, d.draw_best_back,
                    d.home_best_lay, d.away_best_lay, d.draw_best_lay,
                    d.total_volume,
                    d.depth_limit,
                    d.calculation_version,
                    d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3
                FROM market_derived_metrics d
                ORDER BY d.market_id, d.snapshot_at DESC
            )
            SELECT
                e.market_id,
                e.event_id,
                e.event_name,
                e.event_open_date,
                e.competition_name,
                l.snapshot_at AS latest_snapshot_at,
                l.home_best_back, l.away_best_back, l.draw_best_back,
                l.home_best_lay, l.away_best_lay, l.draw_best_lay,
                l.total_volume,
                l.depth_limit,
                l.calculation_version,
                l.home_book_risk_l3, l.away_book_risk_l3, l.draw_book_risk_l3
            FROM market_event_metadata e
            JOIN latest l ON l.market_id = e.market_id
            WHERE e.competition_name = %s
              AND e.event_open_date IS NOT NULL
              AND e.event_open_date >= %s
              AND e.event_open_date <= %s
            ORDER BY e.event_open_date ASC
            LIMIT %s OFFSET %s
            """,
            (league_decoded, from_effective, to_dt, limit, offset),
        )
        rows = cur.fetchall()

    def _row_to_event(r: Any) -> dict:
        return {
            "market_id": r["market_id"],
            "event_id": r.get("event_id"),
            "event_name": r["event_name"],
            "event_open_date": r["event_open_date"].isoformat() if r.get("event_open_date") else None,
            "competition_name": r["competition_name"],
            "latest_snapshot_at": r["latest_snapshot_at"].isoformat() if r.get("latest_snapshot_at") else None,
            "home_best_back": float(r["home_best_back"]) if r.get("home_best_back") is not None else None,
            "away_best_back": float(r["away_best_back"]) if r.get("away_best_back") is not None else None,
            "draw_best_back": float(r["draw_best_back"]) if r.get("draw_best_back") is not None else None,
            "home_best_lay": float(r["home_best_lay"]) if r.get("home_best_lay") is not None else None,
            "away_best_lay": float(r["away_best_lay"]) if r.get("away_best_lay") is not None else None,
            "draw_best_lay": float(r["draw_best_lay"]) if r.get("draw_best_lay") is not None else None,
            "total_volume": float(r["total_volume"]) if r.get("total_volume") is not None else None,
            "depth_limit": r.get("depth_limit"),
            "calculation_version": r.get("calculation_version"),
            "home_book_risk_l3": _opt_float(r.get("home_book_risk_l3")),
            "away_book_risk_l3": _opt_float(r.get("away_book_risk_l3")),
            "draw_book_risk_l3": _opt_float(r.get("draw_book_risk_l3")),
        }

    return [_row_to_event(r) for r in rows]


@app.get("/events/book-risk-focus")
def get_book_risk_focus_events(
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    include_in_play: bool = Query(False, description="Include in-play events; default upcoming only"),
    in_play_lookback_hours: float = Query(2.0, ge=0, le=168, description="When include_in_play, look back this many hours (default 2h)"),
    require_book_risk: bool = Query(True, description="Only return rows where all three book_risk_l3 are non-NULL"),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """All events in the time window with latest metrics including Book Risk L3. Default: current and upcoming only (now to now+48h UTC)."""
    now = datetime.now(timezone.utc)
    from_dt = _parse_ts(from_ts, now)
    to_dt = _parse_ts(to_ts, now + timedelta(hours=48))
    if include_in_play:
        in_play_from = now - timedelta(hours=in_play_lookback_hours)
        from_effective = min(from_dt, in_play_from)
    else:
        from_effective = from_dt

    with cursor() as cur:
        cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (d.market_id)
                    d.market_id,
                    d.snapshot_id,
                    d.snapshot_at,
                    d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
                    d.home_best_back, d.away_best_back, d.draw_best_back,
                    d.home_best_lay, d.away_best_lay, d.draw_best_lay,
                    d.total_volume,
                    d.depth_limit,
                    d.calculation_version
                FROM market_derived_metrics d
                ORDER BY d.market_id, d.snapshot_at DESC
            )
            SELECT
                e.market_id,
                e.event_id,
                e.event_name,
                e.event_open_date,
                e.competition_name,
                l.snapshot_at AS latest_snapshot_at,
                l.home_book_risk_l3, l.away_book_risk_l3, l.draw_book_risk_l3,
                l.home_best_back, l.away_best_back, l.draw_best_back,
                l.home_best_lay, l.away_best_lay, l.draw_best_lay,
                l.total_volume,
                l.depth_limit,
                l.calculation_version
            FROM market_event_metadata e
            JOIN latest l ON l.market_id = e.market_id
            WHERE e.event_open_date IS NOT NULL
              AND e.event_open_date >= %s
              AND e.event_open_date <= %s
              """ + (" AND l.home_book_risk_l3 IS NOT NULL AND l.away_book_risk_l3 IS NOT NULL AND l.draw_book_risk_l3 IS NOT NULL" if require_book_risk else "") + """
            ORDER BY e.event_open_date ASC
            LIMIT %s OFFSET %s
            """,
            (from_effective, to_dt, limit, offset),
        )
        rows = cur.fetchall()

    def _row_to_event(r: Any) -> dict:
        return {
            "market_id": r["market_id"],
            "event_id": r.get("event_id"),
            "event_name": r["event_name"],
            "event_open_date": r["event_open_date"].isoformat() if r.get("event_open_date") else None,
            "competition_name": r["competition_name"],
            "latest_snapshot_at": r["latest_snapshot_at"].isoformat() if r.get("latest_snapshot_at") else None,
            "home_book_risk_l3": _opt_float(r.get("home_book_risk_l3")),
            "away_book_risk_l3": _opt_float(r.get("away_book_risk_l3")),
            "draw_book_risk_l3": _opt_float(r.get("draw_book_risk_l3")),
            "home_best_back": float(r["home_best_back"]) if r.get("home_best_back") is not None else None,
            "away_best_back": float(r["away_best_back"]) if r.get("away_best_back") is not None else None,
            "draw_best_back": float(r["draw_best_back"]) if r.get("draw_best_back") is not None else None,
            "home_best_lay": float(r["home_best_lay"]) if r.get("home_best_lay") is not None else None,
            "away_best_lay": float(r["away_best_lay"]) if r.get("away_best_lay") is not None else None,
            "draw_best_lay": float(r["draw_best_lay"]) if r.get("draw_best_lay") is not None else None,
            "total_volume": float(r["total_volume"]) if r.get("total_volume") is not None else None,
            "depth_limit": r.get("depth_limit"),
            "calculation_version": r.get("calculation_version"),
        }

    return [_row_to_event(r) for r in rows]


@app.get("/events/by-date-snapshots")
def get_events_by_date_snapshots(
    date: str = Query(..., description="UTC date YYYY-MM-DD"),
):
    """
    Snapshot-driven calendar: all events for the given UTC day that have at least one
    snapshot in market_derived_metrics. No Book Risk filter, no limit. Deterministic by date.
    """
    try:
        from_dt = datetime.strptime(date.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    to_dt = from_dt + timedelta(days=1)

    with cursor() as cur:
        cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (d.market_id)
                    d.market_id,
                    d.snapshot_id,
                    d.snapshot_at,
                    d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
                    d.home_best_back, d.away_best_back, d.draw_best_back,
                    d.home_best_lay, d.away_best_lay, d.draw_best_lay,
                    d.total_volume,
                    d.depth_limit,
                    d.calculation_version
                FROM market_derived_metrics d
                ORDER BY d.market_id, d.snapshot_at DESC
            )
            SELECT
                e.market_id,
                e.event_id,
                e.event_name,
                e.event_open_date,
                e.competition_name,
                l.snapshot_at AS latest_snapshot_at,
                l.home_book_risk_l3, l.away_book_risk_l3, l.draw_book_risk_l3,
                l.home_best_back, l.away_best_back, l.draw_best_back,
                l.home_best_lay, l.away_best_lay, l.draw_best_lay,
                l.total_volume,
                l.depth_limit,
                l.calculation_version
            FROM market_event_metadata e
            JOIN latest l ON l.market_id = e.market_id
            WHERE e.event_open_date IS NOT NULL
              AND e.event_open_date >= %s
              AND e.event_open_date < %s
            ORDER BY e.event_open_date ASC, e.market_id ASC
            """,
            (from_dt, to_dt),
        )
        rows = cur.fetchall()

    def _row_to_event(r: Any) -> dict:
        return {
            "market_id": r["market_id"],
            "event_id": r.get("event_id"),
            "event_name": r["event_name"],
            "event_open_date": r["event_open_date"].isoformat() if r.get("event_open_date") else None,
            "competition_name": r["competition_name"],
            "latest_snapshot_at": r["latest_snapshot_at"].isoformat() if r.get("latest_snapshot_at") else None,
            "home_book_risk_l3": _opt_float(r.get("home_book_risk_l3")),
            "away_book_risk_l3": _opt_float(r.get("away_book_risk_l3")),
            "draw_book_risk_l3": _opt_float(r.get("draw_book_risk_l3")),
            "home_best_back": float(r["home_best_back"]) if r.get("home_best_back") is not None else None,
            "away_best_back": float(r["away_best_back"]) if r.get("away_best_back") is not None else None,
            "draw_best_back": float(r["draw_best_back"]) if r.get("draw_best_back") is not None else None,
            "home_best_lay": float(r["home_best_lay"]) if r.get("home_best_lay") is not None else None,
            "away_best_lay": float(r["away_best_lay"]) if r.get("away_best_lay") is not None else None,
            "draw_best_lay": float(r["draw_best_lay"]) if r.get("draw_best_lay") is not None else None,
            "total_volume": float(r["total_volume"]) if r.get("total_volume") is not None else None,
            "depth_limit": r.get("depth_limit"),
            "calculation_version": r.get("calculation_version"),
        }

    return [_row_to_event(r) for r in rows]


@app.get("/events/{market_id}/timeseries")
def get_event_timeseries(
    market_id: str,
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    interval_minutes: int = Query(15, ge=1, le=60),
):
    """
    Time series for one event: 15-min buckets, latest point per bucket.
    Returns snapshot_at, best_back, best_lay, book_risk_l3, total_volume. Imbalance/Impedance removed (MVP).
    """
    now = datetime.now(timezone.utc)
    to_dt = _parse_ts(to_ts, now)
    from_dt = _parse_ts(from_ts, now - timedelta(hours=24))
    interval_sec = interval_minutes * 60
    _l1_size_cols = ", home_best_back_size_l1, away_best_back_size_l1, draw_best_back_size_l1, home_best_lay_size_l1, away_best_lay_size_l1, draw_best_lay_size_l1"
    _l2_l3_cols = ", home_back_odds_l2, home_back_size_l2, home_back_odds_l3, home_back_size_l3, away_back_odds_l2, away_back_size_l2, away_back_odds_l3, away_back_size_l3, draw_back_odds_l2, draw_back_size_l2, draw_back_odds_l3, draw_back_size_l3"

    with cursor() as cur:
        cur.execute(
            """
            WITH bucketed AS (
                SELECT
                    (extract(epoch FROM snapshot_at)::bigint / %s) * %s AS bucket_epoch,
                    snapshot_at,
                    home_best_back, away_best_back, draw_best_back,
                    home_best_lay, away_best_lay, draw_best_lay,
                    home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
                    total_volume,
                    depth_limit,
                    calculation_version
                    """ + _l1_size_cols + """
                    """ + _l2_l3_cols + """
                FROM market_derived_metrics
                WHERE market_id = %s
                  AND snapshot_at >= %s
                  AND snapshot_at <= %s
            ),
            latest_in_bucket AS (
                SELECT DISTINCT ON (bucket_epoch)
                    bucket_epoch,
                    snapshot_at,
                    home_best_back, away_best_back, draw_best_back,
                    home_best_lay, away_best_lay, draw_best_lay,
                    home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
                    total_volume,
                    depth_limit,
                    calculation_version
                    """ + _l1_size_cols + """
                    """ + _l2_l3_cols + """
                FROM bucketed
                ORDER BY bucket_epoch, snapshot_at DESC
            )
            SELECT
                snapshot_at,
                home_best_back, away_best_back, draw_best_back,
                home_best_lay, away_best_lay, draw_best_lay,
                home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3,
                total_volume,
                depth_limit,
                calculation_version
                """ + _l1_size_cols + """
                """ + _l2_l3_cols + """
            FROM latest_in_bucket
            ORDER BY snapshot_at ASC
            """,
            (interval_sec, interval_sec, market_id, from_dt, to_dt),
        )
        rows = cur.fetchall()

    def _serialize(r: Any) -> dict:
        return {
            "snapshot_at": r["snapshot_at"].isoformat() if r.get("snapshot_at") else None,
            "home_best_back": float(r["home_best_back"]) if r.get("home_best_back") is not None else None,
            "away_best_back": float(r["away_best_back"]) if r.get("away_best_back") is not None else None,
            "draw_best_back": float(r["draw_best_back"]) if r.get("draw_best_back") is not None else None,
            "home_best_lay": float(r["home_best_lay"]) if r.get("home_best_lay") is not None else None,
            "away_best_lay": float(r["away_best_lay"]) if r.get("away_best_lay") is not None else None,
            "draw_best_lay": float(r["draw_best_lay"]) if r.get("draw_best_lay") is not None else None,
            "home_book_risk_l3": _opt_float(r.get("home_book_risk_l3")),
            "away_book_risk_l3": _opt_float(r.get("away_book_risk_l3")),
            "draw_book_risk_l3": _opt_float(r.get("draw_book_risk_l3")),
            "total_volume": float(r["total_volume"]) if r.get("total_volume") is not None else None,
            "depth_limit": r.get("depth_limit"),
            "calculation_version": r.get("calculation_version"),
            "home_best_back_size_l1": _opt_float(r.get("home_best_back_size_l1")),
            "away_best_back_size_l1": _opt_float(r.get("away_best_back_size_l1")),
            "draw_best_back_size_l1": _opt_float(r.get("draw_best_back_size_l1")),
            "home_best_lay_size_l1": _opt_float(r.get("home_best_lay_size_l1")),
            "away_best_lay_size_l1": _opt_float(r.get("away_best_lay_size_l1")),
            "draw_best_lay_size_l1": _opt_float(r.get("draw_best_lay_size_l1")),
            "home_back_odds_l2": _opt_float(r.get("home_back_odds_l2")),
            "home_back_size_l2": _opt_float(r.get("home_back_size_l2")),
            "home_back_odds_l3": _opt_float(r.get("home_back_odds_l3")),
            "home_back_size_l3": _opt_float(r.get("home_back_size_l3")),
            "away_back_odds_l2": _opt_float(r.get("away_back_odds_l2")),
            "away_back_size_l2": _opt_float(r.get("away_back_size_l2")),
            "away_back_odds_l3": _opt_float(r.get("away_back_odds_l3")),
            "away_back_size_l3": _opt_float(r.get("away_back_size_l3")),
            "draw_back_odds_l2": _opt_float(r.get("draw_back_odds_l2")),
            "draw_back_size_l2": _opt_float(r.get("draw_back_size_l2")),
            "draw_back_odds_l3": _opt_float(r.get("draw_back_odds_l3")),
            "draw_back_size_l3": _opt_float(r.get("draw_back_size_l3")),
        }

    return [_serialize(r) for r in rows]


def _truncate_raw_payload(payload: Any) -> tuple[Any, bool, int]:
    """Return (payload_for_response, truncated, size_bytes). Never log payload."""
    try:
        full_str = json.dumps(payload) if not isinstance(payload, str) else payload
    except (TypeError, ValueError):
        full_str = str(payload)
    size_bytes = len(full_str.encode("utf-8"))
    if size_bytes <= RAW_PAYLOAD_MAX_BYTES:
        return payload, False, size_bytes
    preview = full_str[:RAW_PAYLOAD_MAX_BYTES] + "\n... [truncated, total " + str(size_bytes) + " bytes]"
    return preview, True, size_bytes


@app.get("/events/{market_id}/latest_raw")
def get_event_latest_raw(market_id: str):
    """Return raw_payload (full marketBook JSON) for the latest snapshot. Read-only. Truncated when > 50KB."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT raw_payload, snapshot_at
            FROM market_book_snapshots
            WHERE market_id = %s
            ORDER BY snapshot_at DESC
            LIMIT 1
            """,
            (market_id,),
        )
        row = cur.fetchone()
    if not row or not row.get("raw_payload"):
        raise HTTPException(status_code=404, detail="No raw snapshot found for this market")
    payload, truncated, size_bytes = _truncate_raw_payload(row["raw_payload"])
    return {
        "market_id": market_id,
        "snapshot_at": row["snapshot_at"].isoformat() if row.get("snapshot_at") else None,
        "raw_payload": payload,
        "truncated": truncated,
        "raw_payload_size_bytes": size_bytes,
    }


# ---------------------------------------------------------------------------
# Debug endpoints: full fields, segmented, raw_payload on demand
# ---------------------------------------------------------------------------

def _rows_to_markets(rows: List[Any]) -> list:
    """Build list of market dicts for response (array shape, backward-compatible)."""
    return [
        {
            "event_id": r["event_id"],
            "market_id": r["market_id"],
            "market_name": r.get("market_name"),
            "event_name": r.get("event_name"),
            "competition_name": r.get("competition_name"),
            "event_open_date": r["event_open_date"].isoformat() if r.get("event_open_date") else None,
            "home_runner_name": r.get("home_runner_name"),
            "away_runner_name": r.get("away_runner_name"),
            "draw_runner_name": r.get("draw_runner_name"),
        }
        for r in rows
    ]


@app.get("/debug/events/{event_or_market_id}/markets")
def get_event_markets(event_or_market_id: str, response: Response):
    """
    List all markets for the same event. Path param can be either market_id or event_id.
    Uses the same lookup as the validation query: market_event_metadata WHERE market_id = %s OR event_id = %s.
    No extra filters (status, inplay, etc.). 404 only if no row matches.
    Returns array of market objects (backward-compatible). Debug: X-Lookup-Mode header + server log.
    """
    # Normalize: treat as string, strip whitespace (proxy/routing can add it)
    id_param = (event_or_market_id or "").strip()
    if not id_param:
        raise HTTPException(status_code=404, detail="Event or market id is empty")

    lookup_mode: Optional[Literal["event_id", "market_id", "fallback_single_market"]] = None
    rows: List[Any] = []

    # Single query aligned with validation: same table, same WHERE (market_id = X OR event_id = X)
    with cursor() as cur:
        cur.execute(
            """
            SELECT e.event_id, e.market_id, e.market_name, e.event_name, e.competition_name,
                   e.event_open_date, e.home_runner_name, e.away_runner_name, e.draw_runner_name
            FROM market_event_metadata e
            WHERE e.market_id = %s OR e.event_id = %s
            ORDER BY CASE WHEN e.market_name ILIKE '%%match odds%%' OR e.market_name ILIKE '%%match_odds%%' THEN 0 ELSE 1 END,
                     e.market_id
            """,
            (id_param, id_param),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Event or market not found")

    # If we got multiple rows, we matched by event_id (all markets for that event)
    if len(rows) > 1:
        lookup_mode = "event_id"
    else:
        row = rows[0]
        event_id = row.get("event_id")
        if event_id:
            with cursor() as cur:
                cur.execute(
                    """
                    SELECT e.event_id, e.market_id, e.market_name, e.event_name, e.competition_name,
                           e.event_open_date, e.home_runner_name, e.away_runner_name, e.draw_runner_name
                    FROM market_event_metadata e
                    WHERE e.event_id = %s
                    ORDER BY CASE WHEN e.market_name ILIKE '%%match odds%%' OR e.market_name ILIKE '%%match_odds%%' THEN 0 ELSE 1 END,
                             e.market_id
                    """,
                    (event_id,),
                )
                sibling_rows = cur.fetchall()
            if sibling_rows:
                rows = sibling_rows
                lookup_mode = "market_id"
        if not lookup_mode:
            lookup_mode = "fallback_single_market"

    logger.info("debug: markets lookup via %s for id=%s", lookup_mode, id_param)
    response.headers["X-Lookup-Mode"] = lookup_mode or "fallback_single_market"
    return _rows_to_markets(rows)


@app.get("/debug/markets/{market_id}/snapshots")
def get_market_snapshots(
    market_id: str,
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=500, description="Max rows (default 500)"),
):
    """
    Full snapshot summary: all scalar columns from market_book_snapshots + market_derived_metrics + metadata.
    No raw_payload. Use /debug/snapshots/{snapshot_id}/raw for raw_payload on row click.
    Time window: default 24h, max 7d. Limit: max 500 points.
    """
    now = datetime.now(timezone.utc)
    to_dt = _parse_ts(to_ts, now)
    from_dt = _parse_ts(from_ts, now - timedelta(hours=24))
    max_window = timedelta(days=7)
    if to_dt - from_dt > max_window:
        from_dt = to_dt - max_window
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                m.snapshot_id,
                m.snapshot_at,
                m.market_id,
                m.raw_payload,
                m.total_matched AS mbs_total_matched,
                m.inplay AS mbs_inplay,
                m.status AS mbs_status,
                m.depth_limit AS mbs_depth_limit,
                m.source AS mbs_source,
                m.capture_version AS mbs_capture_version,
                d.total_volume AS mdm_total_volume,
                d.home_best_back, d.away_best_back, d.draw_best_back,
                d.home_best_lay, d.away_best_lay, d.draw_best_lay,
                d.home_spread, d.away_spread, d.draw_spread,
                d.depth_limit AS mdm_depth_limit,
                d.calculation_version AS mdm_calculation_version,
                d.home_book_risk_l3, d.away_book_risk_l3, d.draw_book_risk_l3,
                d.home_best_back_size_l1, d.away_best_back_size_l1, d.draw_best_back_size_l1,
                d.home_back_odds_l2, d.home_back_size_l2, d.home_back_odds_l3, d.home_back_size_l3,
                d.away_back_odds_l2, d.away_back_size_l2, d.away_back_odds_l3, d.away_back_size_l3,
                d.draw_back_odds_l2, d.draw_back_size_l2, d.draw_back_odds_l3, d.draw_back_size_l3,
                e.event_id, e.event_name, e.competition_name, e.event_open_date,
                e.home_runner_name, e.away_runner_name, e.draw_runner_name,
                e.market_name AS meta_market_name,
                e.home_selection_id, e.away_selection_id, e.draw_selection_id
            FROM market_book_snapshots m
            JOIN market_derived_metrics d ON d.snapshot_id = m.snapshot_id
            LEFT JOIN market_event_metadata e ON e.market_id = m.market_id
            WHERE m.market_id = %s
              AND m.snapshot_at >= %s
              AND m.snapshot_at <= %s
            ORDER BY m.snapshot_at DESC
            LIMIT %s
            """,
            (market_id, from_dt, to_dt, limit),
        )
        rows = cur.fetchall()

    def _serialize(r: Any) -> dict:
        row = dict(r)
        raw_payload = row.get("raw_payload")
        home_sid = row.get("home_selection_id")
        away_sid = row.get("away_selection_id")
        draw_sid = row.get("draw_selection_id")
        depth_limit = row.get("mdm_depth_limit")
        out = {}
        skip = {"raw_payload", "home_selection_id", "away_selection_id", "draw_selection_id"}
        for k, v in row.items():
            if k in skip:
                continue
            if v is None:
                out[k] = None
            elif hasattr(v, "isoformat"):
                out[k] = v.isoformat()
            elif isinstance(v, (int, float, str, bool)):
                out[k] = v
            else:
                out[k] = str(v)
        if "mdm_calculation_version" in out:
            out["calculation_version"] = out["mdm_calculation_version"]
        validators = _compute_back_depth_validators(
            raw_payload, home_sid, away_sid, draw_sid, depth_limit
        )
        out.update(validators)
        roi_toxic = _compute_roi_toxic(out)
        out.update(roi_toxic)
        return out

    return [_serialize(r) for r in rows]


@app.get("/debug/snapshots/{snapshot_id}/raw")
def get_snapshot_raw(snapshot_id: int):
    """Return raw_payload for a single snapshot (on row click). Truncated when > 50KB to avoid IDE serialization issues."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT snapshot_id, snapshot_at, market_id, raw_payload
            FROM market_book_snapshots WHERE snapshot_id = %s
            """,
            (snapshot_id,),
        )
        row = cur.fetchone()
    if not row or not row.get("raw_payload"):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    payload, truncated, size_bytes = _truncate_raw_payload(row["raw_payload"])
    return {
        "snapshot_id": row["snapshot_id"],
        "snapshot_at": row["snapshot_at"].isoformat() if row.get("snapshot_at") else None,
        "market_id": row["market_id"],
        "raw_payload": payload,
        "truncated": truncated,
        "raw_payload_size_bytes": size_bytes,
    }


@app.get("/events/{market_id}/meta")
def get_event_meta(market_id: str):
    """Single event metadata for detail header (league, event name, start time)."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT market_id, event_name, event_open_date, competition_name,
                   home_runner_name, away_runner_name, draw_runner_name
            FROM market_event_metadata
            WHERE market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "market_id": row["market_id"],
        "event_name": row["event_name"],
        "event_open_date": row["event_open_date"].isoformat() if row.get("event_open_date") else None,
        "competition_name": row["competition_name"],
        "home_runner_name": row.get("home_runner_name"),
        "away_runner_name": row.get("away_runner_name"),
        "draw_runner_name": row.get("draw_runner_name"),
    }
