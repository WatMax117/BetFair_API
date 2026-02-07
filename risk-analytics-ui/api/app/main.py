"""
Risk Analytics API – read-only FastAPI service for 3-layer DB.
Endpoints: /api/leagues, /api/leagues/{league}/events, /api/events/{market_id}/timeseries
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any
from urllib.parse import unquote

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db import cursor

app = FastAPI(title="Risk Analytics API", version="1.0.0")
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/leagues")
def get_leagues(
    from_ts: Optional[str] = Query(None, description="UTC ISO start"),
    to_ts: Optional[str] = Query(None, description="UTC ISO end"),
    q: Optional[str] = Query(None, description="Search substring (event/team name)"),
    include_in_play: bool = Query(True, description="Include events that have already started (in-play)"),
    in_play_lookback_hours: float = Query(6.0, ge=0, le=168, description="When include_in_play, extend window back this many hours for in-play"),
    limit: int = Query(100, ge=1, le=200, description="Max leagues to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List leagues (competition_name) with event counts in the given time window."""
    now = datetime.now(timezone.utc)
    from_dt = _parse_ts(from_ts, now)
    to_dt = _parse_ts(to_ts, now + timedelta(hours=24))
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
                ORDER BY e.competition_name
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
                ORDER BY e.competition_name
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
    include_in_play: bool = Query(True, description="Include in-play events"),
    in_play_lookback_hours: float = Query(6.0, ge=0, le=168),
    limit: int = Query(100, ge=1, le=200, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Events in the league with latest snapshot (odds + index + total_volume)."""
    league_decoded = unquote(league_name)
    now = datetime.now(timezone.utc)
    from_dt = _parse_ts(from_ts, now)
    to_dt = _parse_ts(to_ts, now + timedelta(hours=24))
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
                    d.home_risk, d.away_risk, d.draw_risk,
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
                e.event_name,
                e.event_open_date,
                e.competition_name,
                l.snapshot_at AS latest_snapshot_at,
                l.home_risk, l.away_risk, l.draw_risk,
                l.home_best_back, l.away_best_back, l.draw_best_back,
                l.home_best_lay, l.away_best_lay, l.draw_best_lay,
                l.total_volume,
                l.depth_limit,
                l.calculation_version
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
            "event_name": r["event_name"],
            "event_open_date": r["event_open_date"].isoformat() if r.get("event_open_date") else None,
            "competition_name": r["competition_name"],
            "latest_snapshot_at": r["latest_snapshot_at"].isoformat() if r.get("latest_snapshot_at") else None,
            "home_risk": float(r["home_risk"]) if r.get("home_risk") is not None else None,
            "away_risk": float(r["away_risk"]) if r.get("away_risk") is not None else None,
            "draw_risk": float(r["draw_risk"]) if r.get("draw_risk") is not None else None,
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
    Returns snapshot_at, best_back (home/away/draw), best_lay, risks, total_volume.
    """
    now = datetime.now(timezone.utc)
    to_dt = _parse_ts(to_ts, now)
    from_dt = _parse_ts(from_ts, now - timedelta(hours=24))
    interval_sec = interval_minutes * 60

    with cursor() as cur:
        cur.execute(
            """
            WITH bucketed AS (
                SELECT
                    (extract(epoch FROM snapshot_at)::bigint / %s) * %s AS bucket_epoch,
                    snapshot_at,
                    home_best_back, away_best_back, draw_best_back,
                    home_best_lay, away_best_lay, draw_best_lay,
                    home_risk, away_risk, draw_risk,
                    total_volume,
                    depth_limit,
                    calculation_version
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
                    home_risk, away_risk, draw_risk,
                    total_volume,
                    depth_limit,
                    calculation_version
                FROM bucketed
                ORDER BY bucket_epoch, snapshot_at DESC
            )
            SELECT
                snapshot_at,
                home_best_back, away_best_back, draw_best_back,
                home_best_lay, away_best_lay, draw_best_lay,
                home_risk, away_risk, draw_risk,
                total_volume,
                depth_limit,
                calculation_version
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
            "home_risk": float(r["home_risk"]) if r.get("home_risk") is not None else None,
            "away_risk": float(r["away_risk"]) if r.get("away_risk") is not None else None,
            "draw_risk": float(r["draw_risk"]) if r.get("draw_risk") is not None else None,
            "total_volume": float(r["total_volume"]) if r.get("total_volume") is not None else None,
            "depth_limit": r.get("depth_limit"),
            "calculation_version": r.get("calculation_version"),
        }

    return [_serialize(r) for r in rows]


@app.get("/events/{market_id}/latest_raw")
def get_event_latest_raw(market_id: str):
    """Return raw_payload (full marketBook JSON) for the latest snapshot. Read-only."""
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
    return {"market_id": market_id, "snapshot_at": row["snapshot_at"].isoformat() if row.get("snapshot_at") else None, "raw_payload": row["raw_payload"]}


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
