"""
Stream UI API: same shapes as REST but from stream_ingest with 15-min UTC buckets.
Mount at prefix /stream. Staleness: STALE_MINUTES in stream_data.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.db import cursor
from app.stream_data import (
    STALE_MINUTES,
    get_events_by_date_snapshots_stream,
    get_event_timeseries_stream,
)


def _parse_ts_stream(s: Optional[str], default: datetime) -> datetime:
    if not s:
        return default
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return default


stream_router = APIRouter(tags=["stream"])


@stream_router.get("/events/by-date-snapshots")
def stream_events_by_date_snapshots(
    date: str = Query(..., description="UTC date YYYY-MM-DD"),
):
    """Snapshot-driven calendar from stream_ingest; 15-min UTC buckets; staleness > {} min excludes market.""".format(STALE_MINUTES)
    events = get_events_by_date_snapshots_stream(date)
    return events


@stream_router.get("/events/{market_id}/timeseries")
def stream_event_timeseries(
    market_id: str,
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    interval_minutes: int = Query(15, ge=1, le=60),
):
    """Timeseries from stream_ingest; fixed 15-min UTC buckets; last state in bucket."""
    now = datetime.now(timezone.utc)
    to_dt = min(_parse_ts_stream(to_ts, now), now)  # Cap to_dt at current time
    from_dt = _parse_ts_stream(from_ts, now - timedelta(hours=24))
    # Ensure from_dt <= to_dt
    if from_dt > to_dt:
        from_dt = to_dt - timedelta(hours=24)
    points = get_event_timeseries_stream(market_id, from_dt, to_dt, interval_minutes)
    return points


@stream_router.get("/events/{market_id}/meta")
def stream_event_meta(market_id: str):
    """Metadata from public.market_event_metadata (same as REST)."""
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


@stream_router.get("/events/{market_id}/latest_raw")
def stream_event_latest_raw(market_id: str):
    """Stream source has no raw_payload; return 404 so UI can handle gracefully."""
    raise HTTPException(
        status_code=404,
        detail="Raw snapshot not available for stream source (15-min bucket data only)",
    )


@stream_router.get("/debug/markets/{market_id}/snapshots")
def stream_market_snapshots(
    market_id: str,
    from_ts: Optional[str] = Query(None),
    to_ts: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    """Per-bucket snapshot rows from stream (15-min UTC); same shape as REST debug snapshots for table."""
    now = datetime.now(timezone.utc)
    to_dt = min(_parse_ts_stream(to_ts, now), now)  # Cap to_dt at current time
    from_dt = _parse_ts_stream(from_ts, now - timedelta(hours=24))
    # Ensure from_dt <= to_dt
    if from_dt > to_dt:
        from_dt = to_dt - timedelta(hours=24)
    points = get_event_timeseries_stream(market_id, from_dt, to_dt, 15)
    # Trim to limit and map to DebugSnapshotRow-like shape (no snapshot_id; use index)
    out = []
    for i, p in enumerate(points[:limit]):
        out.append({
            "snapshot_id": i + 1,
            "snapshot_at": p.get("snapshot_at"),
            "market_id": market_id,
            "mbs_total_matched": p.get("total_volume"),
            "mbs_inplay": None,
            "mbs_status": None,
            "mbs_depth_limit": p.get("depth_limit"),
            "mbs_source": "stream_15min",
            "mdm_total_volume": p.get("total_volume"),
            "home_best_back": p.get("home_best_back"),
            "away_best_back": p.get("away_best_back"),
            "draw_best_back": p.get("draw_best_back"),
            "home_best_lay": p.get("home_best_lay"),
            "away_best_lay": p.get("away_best_lay"),
            "draw_best_lay": p.get("draw_best_lay"),
            "home_book_risk_l3": p.get("home_book_risk_l3"),
            "away_book_risk_l3": p.get("away_book_risk_l3"),
            "draw_book_risk_l3": p.get("draw_book_risk_l3"),
        })
    return out


@stream_router.get("/debug/snapshots/{snapshot_id}/raw")
def stream_snapshot_raw(snapshot_id: int):
    """Stream has no raw payload per snapshot."""
    raise HTTPException(status_code=404, detail="Raw payload not available for stream source")


@stream_router.get("/markets/{market_id}/ticks")
def stream_market_ticks(
    market_id: str,
    from_ts: Optional[str] = Query(..., description="Start time (ISO 8601 UTC)"),
    to_ts: Optional[str] = Query(..., description="End time (ISO 8601 UTC)"),
    limit: int = Query(2000, ge=1, le=5000, description="Max number of ticks to return"),
):
    """
    Raw ticks (ladder_levels) for a market within a time range.
    Returns all level=0, side='B' ticks ordered by publish_time ascending.
    Used for audit view of ticks within a 15-minute bucket.
    """
    from_dt = _parse_ts_stream(from_ts, datetime.now(timezone.utc) - timedelta(hours=1))
    to_dt = _parse_ts_stream(to_ts, datetime.now(timezone.utc))
    
    if from_dt > to_dt:
        raise HTTPException(status_code=400, detail="from_ts must be <= to_ts")
    
    with cursor() as cur:
        # Get selection IDs for home/away/draw
        cur.execute(
            """
            SELECT home_selection_id, away_selection_id, draw_selection_id
            FROM market_event_metadata
            WHERE market_id = %s
            """,
            (market_id,),
        )
        meta = cur.fetchone()
        if not meta:
            raise HTTPException(status_code=404, detail="Market not found")
        
        home_sid = meta.get("home_selection_id")
        away_sid = meta.get("away_selection_id")
        draw_sid = meta.get("draw_selection_id")
        
        # Fetch raw ticks (level=0, side='B' only for back odds/size)
        # Filter by selection_id if any are available
        selection_ids = [sid for sid in [home_sid, away_sid, draw_sid] if sid is not None]
        if not selection_ids:
            return []
        
        cur.execute(
            """
            SELECT 
                publish_time,
                selection_id,
                price AS back_odds,
                size AS back_size
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s
              AND side = 'B'
              AND level = 0
              AND publish_time >= %s
              AND publish_time <= %s
              AND selection_id = ANY(%s)
            ORDER BY publish_time ASC
            LIMIT %s
            """,
            (market_id, from_dt, to_dt, selection_ids, limit),
        )
        rows = cur.fetchall()
    
    # Transform to per-tick format with H/A/D columns
    ticks = []
    for row in rows:
        tick = {
            "publish_time": row["publish_time"].isoformat() if row.get("publish_time") else None,
            "selection_id": row["selection_id"],
            "back_odds": float(row["back_odds"]) if row.get("back_odds") is not None else None,
            "back_size": float(row["back_size"]) if row.get("back_size") is not None else None,
        }
        # Add H/A/D specific fields
        if row["selection_id"] == home_sid:
            tick["home_back_odds"] = tick["back_odds"]
            tick["home_back_size"] = tick["back_size"]
            tick["away_back_odds"] = None
            tick["away_back_size"] = None
            tick["draw_back_odds"] = None
            tick["draw_back_size"] = None
        elif row["selection_id"] == away_sid:
            tick["home_back_odds"] = None
            tick["home_back_size"] = None
            tick["away_back_odds"] = tick["back_odds"]
            tick["away_back_size"] = tick["back_size"]
            tick["draw_back_odds"] = None
            tick["draw_back_size"] = None
        elif row["selection_id"] == draw_sid:
            tick["home_back_odds"] = None
            tick["home_back_size"] = None
            tick["away_back_odds"] = None
            tick["away_back_size"] = None
            tick["draw_back_odds"] = tick["back_odds"]
            tick["draw_back_size"] = tick["back_size"]
        else:
            # Should not happen, but handle gracefully
            tick["home_back_odds"] = None
            tick["home_back_size"] = None
            tick["away_back_odds"] = None
            tick["away_back_size"] = None
            tick["draw_back_odds"] = None
            tick["draw_back_size"] = None
        
        ticks.append(tick)
    
    return ticks
