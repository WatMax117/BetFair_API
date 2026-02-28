"""
Stream UI API: same shapes as REST but from stream_ingest with 15-min UTC buckets.
Mount at prefix /stream. Staleness: STALE_MINUTES in stream_data.
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.db import cursor

logger = logging.getLogger(__name__)
from app.stream_data import (
    get_events_by_date_rest_driven,
    get_events_by_date_volume,
    get_event_timeseries_stream,
    get_event_buckets_stream_bulk,
    get_event_buckets_stream,
    get_data_horizon,
    get_event_bucket_range,
    get_available_bucket_starts,
)

DATA_HORIZON_CACHE_TTL_SEC = 60
_data_horizon_cache: dict = {"value": None, "expires_at": 0}


def _parse_ts_stream(s: Optional[str], default: datetime) -> datetime:
    if not s:
        return default
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return default


stream_router = APIRouter(tags=["stream"])


@stream_router.get("/data-horizon")
def stream_data_horizon():
    """
    Streaming data horizon: oldest_tick, newest_tick, total_rows.
    Includes optional days[] for calendar UX (dates with ladder data).
    Cached 60 seconds to avoid heavy scans.

    Route: app mounts this router at prefix /stream, so full path is /stream/data-horizon.
    Behind a proxy that strips /api, the UI calls /api/stream/data-horizon; proxy forwards
    to backend as /stream/data-horizon. On VPS verify which works:
      curl -sS http://localhost:8000/stream/data-horizon | head
      curl -sS http://localhost:8000/api/stream/data-horizon | head
    The path the UI uses must match (getApiBase() + '/data-horizon' = /api/stream/data-horizon when on stream UI).
    """
    now_ts = time.time()
    if _data_horizon_cache["value"] is not None and now_ts < _data_horizon_cache["expires_at"]:
        return _data_horizon_cache["value"]
    result = get_data_horizon(include_days=True, days_limit=90)
    _data_horizon_cache["value"] = result
    _data_horizon_cache["expires_at"] = now_ts + DATA_HORIZON_CACHE_TTL_SEC
    return result


@stream_router.get("/events/by-date-snapshots")
def stream_events_by_date_snapshots(
    date: str = Query(..., description="UTC date YYYY-MM-DD"),
):
    """
    REST as source of truth: rest_events + rest_markets define event list.
    Streaming enriches only (LEFT JOIN); no exclusion for missing stream or staleness.
    Returns last_stream_update_at, is_stale for UI to mark stale rows.
    """
    events = get_events_by_date_rest_driven(date)
    logger.info("by_date_snapshots date=%s returned_count=%d", date, len(events))
    return events


@stream_router.get("/events/by-date-volume")
def stream_events_by_date_volume(
    date: str = Query(..., description="UTC date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    min_volume: float = Query(0.0, ge=0, description="Exclude events with volume_total < this"),
    sort: str = Query("volume_desc", description="volume_desc or volume_asc"),
):
    """
    Volume tab: events for the selected day ordered by traded volume (SUM of market volumes per event).
    Same data source as by-date-snapshots. No theoretical timestamps.
    """
    if sort not in ("volume_desc", "volume_asc"):
        sort = "volume_desc"
    result = get_events_by_date_volume(date, limit=limit, offset=offset, min_volume=min_volume, sort=sort)
    logger.info("by_date_volume date=%s total=%d returned=%d", date, result["paging"]["total"], len(result["items"]))
    return result


# Default bucket window: last 180 minutes (12 buckets)
BUCKETS_DEFAULT_WINDOW_MINUTES = 180


@stream_router.get("/events/{market_id}/buckets")
def stream_event_buckets(
    market_id: str,
    from_ts: Optional[str] = Query(None, description="Start time (ISO 8601 UTC). Default: now - 180 min"),
    to_ts: Optional[str] = Query(None, description="End time (ISO 8601 UTC). Default: now"),
    event_aware: bool = Query(False, description="If true, return only buckets that have tick data for this market (event-aware); ignores from_ts/to_ts default window."),
):
    """
    Bulk buckets: 3 DB queries total (metadata, ladder, liquidity). No per-bucket queries.
    Default: last 180 min (12 buckets). Same response shape as before.
    When event_aware=true: returns all buckets that actually contain ticks for this market (no global time window).
    """
    if event_aware:
        buckets = get_event_buckets_stream(market_id)
        logger.info("buckets_endpoint event_aware=true market_id=%s bucket_count=%d", market_id, len(buckets))
        return buckets
    t_start = time.perf_counter()
    now = datetime.now(timezone.utc)
    to_dt = _parse_ts_stream(to_ts, now)
    from_dt = _parse_ts_stream(from_ts, now - timedelta(minutes=BUCKETS_DEFAULT_WINDOW_MINUTES))
    if from_dt > to_dt:
        from_dt = to_dt - timedelta(minutes=BUCKETS_DEFAULT_WINDOW_MINUTES)
    buckets, db_count = get_event_buckets_stream_bulk(market_id, from_dt, to_dt)
    t_end = time.perf_counter()
    total_ms = (t_end - t_start) * 1000
    try:
        import json
        payload_bytes = len(json.dumps(buckets).encode("utf-8"))
    except Exception:
        payload_bytes = 0
    logger.info(
        "buckets_endpoint market_id=%s bucket_count=%d db_query_count=%d total_ms=%.1f payload_bytes=%d",
        market_id, len(buckets), db_count, total_ms, payload_bytes,
    )
    return buckets


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
    """Metadata from public.market_event_metadata; includes H/A/D selection IDs, replay support, and runner settlement status."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT market_id, event_name, event_open_date, competition_name,
                   home_runner_name, away_runner_name, draw_runner_name,
                   home_selection_id, away_selection_id, draw_selection_id
            FROM market_event_metadata
            WHERE market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")

    # Runner settlement status from stream_ingest.market_runner_settlement (WINNER, LOSER, REMOVED)
    home_runner_status = None
    away_runner_status = None
    draw_runner_status = None
    home_sid = row.get("home_selection_id")
    away_sid = row.get("away_selection_id")
    draw_sid = row.get("draw_selection_id")
    if home_sid is not None or away_sid is not None or draw_sid is not None:
        with cursor() as cur:
            cur.execute(
                """
                SELECT selection_id, runner_status
                FROM stream_ingest.market_runner_settlement
                WHERE market_id = %s AND selection_id = ANY(%s)
                """,
                (market_id, [s for s in [home_sid, away_sid, draw_sid] if s is not None]),
            )
            for r in cur.fetchall():
                status = r.get("runner_status")
                sid = r.get("selection_id")
                if sid == home_sid:
                    home_runner_status = status
                elif sid == away_sid:
                    away_runner_status = status
                elif sid == draw_sid:
                    draw_runner_status = status

    # Last tick time for replay (max publish_time in ladder_levels for this market)
    last_tick_time = None
    with cursor() as cur:
        cur.execute(
            """
            SELECT max(publish_time) AS last_tick_time
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s
            """,
            (market_id,),
        )
        r = cur.fetchone()
        if r and r.get("last_tick_time"):
            last_tick_time = r["last_tick_time"].isoformat() if hasattr(r["last_tick_time"], "isoformat") else str(r["last_tick_time"])

    # Event-aware bucket metadata: from actual tick data (not global time)
    bucket_range = get_event_bucket_range(market_id)
    earliest_bucket_start = None
    latest_bucket_start = None
    if bucket_range:
        earliest_bucket_start = bucket_range[0].isoformat()
        latest_bucket_start = bucket_range[1].isoformat()

    return {
        "market_id": row["market_id"],
        "event_name": row["event_name"],
        "event_open_date": row["event_open_date"].isoformat() if row.get("event_open_date") else None,
        "competition_name": row["competition_name"],
        "home_runner_name": row.get("home_runner_name"),
        "away_runner_name": row.get("away_runner_name"),
        "draw_runner_name": row.get("draw_runner_name"),
        "home_selection_id": row.get("home_selection_id"),
        "away_selection_id": row.get("away_selection_id"),
        "draw_selection_id": row.get("draw_selection_id"),
        "home_runner_status": home_runner_status,
        "away_runner_status": away_runner_status,
        "draw_runner_status": draw_runner_status,
        "has_raw_stream": False,
        "has_full_raw_payload": False,
        "supports_replay_snapshot": True,
        "last_tick_time": last_tick_time,
        "retention_policy": "Tick data in stream_ingest.ladder_levels; 15-min aggregates derived at read. See RETENTION_MATRIX.md.",
        "bucket_interval_minutes": 15,
        "earliest_bucket_start": earliest_bucket_start,
        "latest_bucket_start": latest_bucket_start,
    }


@stream_router.get("/events/{market_id}/available-buckets")
def stream_event_available_buckets(market_id: str):
    """
    Distinct 15-min UTC bucket starts that have at least one tick for this market.
    Source of truth for event-aware bucket selector; no global time window.
    """
    bucket_starts = get_available_bucket_starts(market_id)
    available_buckets = [bt.isoformat() for bt in bucket_starts]
    earliest_bucket = bucket_starts[0].isoformat() if bucket_starts else None
    latest_bucket = bucket_starts[-1].isoformat() if bucket_starts else None
    return {
        "market_id": market_id,
        "bucket_interval_minutes": 15,
        "available_buckets": available_buckets,
        "earliest_bucket": earliest_bucket,
        "latest_bucket": latest_bucket,
    }


@stream_router.get("/events/{market_id}/replay_snapshot")
def stream_event_replay_snapshot(
    market_id: str,
    at_ts: Optional[str] = Query(None, description="Point-in-time (ISO 8601 UTC); omit for latest"),
    mode: Optional[str] = Query(None, description="utc | local (formatting only)"),
):
    """
    Reconstruct a market snapshot from stored stream ticks (ladder_levels).
    Returns latest available tick snapshot, or snapshot at or before at_ts.
    No raw payload storage; snapshot is reconstructed from ladder + liquidity.
    """
    at_dt = _parse_ts_stream(at_ts, datetime.now(timezone.utc)) if at_ts else None
    with cursor() as cur:
        # 1) Resolve snapshot_time: max(publish_time) for market [at or before at_ts]
        if at_dt is not None:
            cur.execute(
                """
                SELECT publish_time
                FROM stream_ingest.ladder_levels
                WHERE market_id = %s AND publish_time <= %s
                ORDER BY publish_time DESC
                LIMIT 1
                """,
                (market_id, at_dt),
            )
        else:
            cur.execute(
                """
                SELECT publish_time
                FROM stream_ingest.ladder_levels
                WHERE market_id = %s
                ORDER BY publish_time DESC
                LIMIT 1
                """,
                (market_id,),
            )
        row = cur.fetchone()
        if not row or not row.get("publish_time"):
            raise HTTPException(status_code=404, detail="No tick data available for market.")
        snapshot_time = row["publish_time"]

        # 2) All ladder rows at that snapshot_time
        cur.execute(
            """
            SELECT selection_id, side, level, price, size
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s AND publish_time = %s
            """,
            (market_id, snapshot_time),
        )
        ladder_rows = cur.fetchall()

        # 3) Latest liquidity at or before snapshot_time
        cur.execute(
            """
            SELECT total_matched
            FROM stream_ingest.market_liquidity_history
            WHERE market_id = %s AND publish_time <= %s
            ORDER BY publish_time DESC
            LIMIT 1
            """,
            (market_id, snapshot_time),
        )
        liq_row = cur.fetchone()
        total_matched = float(liq_row["total_matched"]) if liq_row and liq_row.get("total_matched") is not None else None

    # Aggregate per selection: best back (side=B, level=0), best lay (side=L, level=0)
    by_sel: dict = {}
    for r in ladder_rows:
        sid = str(r["selection_id"])
        if sid not in by_sel:
            by_sel[sid] = {"best_back_price": None, "best_back_size": None, "best_lay_price": None, "best_lay_size": None}
        side = (r.get("side") or "").upper()
        level = int(r["level"]) if r.get("level") is not None else None
        if level != 0:
            continue
        price = float(r["price"]) if r.get("price") is not None else None
        size = float(r["size"]) if r.get("size") is not None else None
        if side == "B":
            by_sel[sid]["best_back_price"] = price
            by_sel[sid]["best_back_size"] = size
        elif side == "L":
            by_sel[sid]["best_lay_price"] = price
            by_sel[sid]["best_lay_size"] = size

    selections = [
        {
            "selection_id": sid,
            "best_back_price": v["best_back_price"],
            "best_back_size": v["best_back_size"],
            "best_lay_price": v["best_lay_price"],
            "best_lay_size": v["best_lay_size"],
        }
        for sid, v in sorted(by_sel.items())
    ]

    # available_to_back / available_to_lay: sum of level-0 sizes from ladder at this snapshot
    available_to_back = sum(
        v["best_back_size"] or 0 for v in by_sel.values()
    )
    available_to_lay = sum(
        v["best_lay_size"] or 0 for v in by_sel.values()
    )

    snapshot_time_iso = snapshot_time.isoformat() if hasattr(snapshot_time, "isoformat") else str(snapshot_time)
    return {
        "market_id": market_id,
        "snapshot_time": snapshot_time_iso,
        "is_reconstructed": True,
        "source": "ladder_levels",
        "selections": selections,
        "liquidity": {
            "total_matched": total_matched,
            "available_to_back": available_to_back if available_to_back else None,
            "available_to_lay": available_to_lay if available_to_lay else None,
        },
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
    t_start = time.perf_counter()
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

    t_end = time.perf_counter()
    total_ms = (t_end - t_start) * 1000
    try:
        import json
        payload_bytes = len(json.dumps(ticks).encode("utf-8"))
    except Exception:
        payload_bytes = 0
    logger.info(
        "ticks_endpoint market_id=%s rows=%d total_ms=%.1f payload_bytes=%d",
        market_id, len(ticks), total_ms, payload_bytes,
    )
    return ticks
