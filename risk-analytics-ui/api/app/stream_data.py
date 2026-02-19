"""
Streaming-derived data with 15-minute UTC snapshot normalization.
Reads stream_ingest.ladder_levels and stream_ingest.market_liquidity_history;
metadata from public.market_event_metadata.
Staleness: markets with no update in the last N minutes are excluded (see STALE_MINUTES).

Bucket parameters: time-weighted medians of back_odds and back_size per 15-min UTC bucket.
Uses carry-forward logic: baseline from before bucket_start, then segments for updates in bucket.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from app.db import cursor

# No update in last N minutes (UTC) -> exclude market from bucket. Configurable.
# Temporarily 120 for diagnostics; reduce to 20 once streaming freshness is confirmed.
STALE_MINUTES = 120
DEPTH_LIMIT = 3  # Legacy: used only for ladder display compatibility, NOT for risk computation


def _bucket_15_utc(dt: datetime) -> datetime:
    """Floor to 15-min UTC: HH:00, HH:15, HH:30, HH:45."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


def _bucket_times_in_range(from_dt: datetime, to_dt: datetime) -> List[datetime]:
    """Yield 15-min bucket boundaries in [from_dt, to_dt) UTC."""
    start = _bucket_15_utc(from_dt)
    if start < from_dt:
        start += timedelta(minutes=15)
    out: List[datetime] = []
    t = start
    while t < to_dt:
        out.append(t)
        t += timedelta(minutes=15)
    return out


def _runners_from_ladder(
    cur: Any,
    market_id: str,
    bucket_time: datetime,
    home_sid: Optional[int],
    away_sid: Optional[int],
    draw_sid: Optional[int],
) -> Tuple[List[Dict], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    From stream_ingest.ladder_levels build runners with ex.availableToBack (and best back/lay L1).
    Returns (runners_list, home_bb, away_bb, draw_bb, home_bl, away_bl, draw_bl, total_volume).
    total_volume from market_liquidity_history at or before bucket_time.
    """
    cur.execute(
        """
        WITH latest_per_level AS (
            SELECT DISTINCT ON (selection_id, side, level)
                selection_id, side, level, price, size
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s AND publish_time <= %s
            ORDER BY selection_id, side, level, publish_time DESC
        )
        SELECT selection_id, side, level, price, size
        FROM latest_per_level
        ORDER BY selection_id, side, level
        """,
        (market_id, bucket_time),
    )
    rows = cur.fetchall()
    # total_volume for this market at or before bucket_time
    cur.execute(
        """
        SELECT total_matched
        FROM stream_ingest.market_liquidity_history
        WHERE market_id = %s AND publish_time <= %s
        ORDER BY publish_time DESC
        LIMIT 1
        """,
        (market_id, bucket_time),
    )
    tv_row = cur.fetchone()
    total_volume = float(tv_row["total_matched"]) if tv_row and tv_row.get("total_matched") is not None else None

    # Build per-selection back/lay ladders (level -> (price, size))
    by_sel: Dict[int, Dict[str, List[Tuple[float, float]]]] = {}
    for r in rows:
        sid = int(r["selection_id"])
        side = "B" if r["side"] in ("B", "b") else "L"
        level = int(r["level"])
        price = float(r["price"])
        size = float(r["size"])
        if sid not in by_sel:
            by_sel[sid] = {"B": [], "L": []}
        ladder = by_sel[sid][side]
        while len(ladder) <= level:
            ladder.append((0.0, 0.0))
        ladder[level] = (price, size)

    def best_l1(ladder: List[Tuple[float, float]]) -> Optional[float]:
        for p, s in ladder:
            if s > 0:
                return p
        return None

    runners: List[Dict] = []
    home_bb = away_bb = draw_bb = None
    home_bl = away_bl = draw_bl = None
    for sid, ladders in by_sel.items():
        back = ladders.get("B") or []
        lay = ladders.get("L") or []
        atb = [[p, s] for p, s in back if s > 0][:DEPTH_LIMIT]
        atl = [[p, s] for p, s in lay if s > 0][:DEPTH_LIMIT]
        runners.append({
            "selectionId": sid,
            "selection_id": sid,
            "ex": {"availableToBack": atb, "availableToLay": atl},
        })
        bb = best_l1(back)
        bl = best_l1(lay)
        if sid == home_sid:
            home_bb, home_bl = bb, bl
        elif sid == away_sid:
            away_bb, away_bl = bb, bl
        elif sid == draw_sid:
            draw_bb, draw_bl = bb, bl

    return runners, home_bb, away_bb, draw_bb, home_bl, away_bl, draw_bl, total_volume


def _latest_publish_before(cur: Any, market_id: str, bucket_time: datetime) -> Optional[datetime]:
    cur.execute(
        """
        SELECT MAX(publish_time) AS t
        FROM stream_ingest.ladder_levels
        WHERE market_id = %s AND publish_time <= %s
        """,
        (market_id, bucket_time),
    )
    row = cur.fetchone()
    return row["t"] if row and row.get("t") else None


def compute_book_risk_from_medians(
    home_odds_median: Optional[float],
    home_size_median: Optional[float],
    away_odds_median: Optional[float],
    away_size_median: Optional[float],
    draw_odds_median: Optional[float],
    draw_size_median: Optional[float],
) -> Optional[Dict[str, Optional[float]]]:
    """
    Compute Book Risk (15m) strictly from the six 15-minute bucket medians.
    
    Formula: R[o] = W[o] - L[o] where:
    - W[o] = median_size[o] * (median_odds[o] - 1)  [winners net payout]
    - L[o] = sum of median_size for other outcomes  [liability if other outcomes win]
    
    Returns None if any median is NULL (no partial computation).
    Otherwise returns dict with home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3.
    """
    # If any median is NULL, return None for all risks
    if any(m is None for m in [
        home_odds_median, home_size_median,
        away_odds_median, away_size_median,
        draw_odds_median, draw_size_median,
    ]):
        return None
    
    # Winners net payout: size * (odds - 1)
    w_home = home_size_median * (home_odds_median - 1.0)
    w_away = away_size_median * (away_odds_median - 1.0)
    w_draw = draw_size_median * (draw_odds_median - 1.0)
    
    # Liability: sum of stakes on other outcomes
    l_home = away_size_median + draw_size_median
    l_away = home_size_median + draw_size_median
    l_draw = home_size_median + away_size_median
    
    return {
        "home_book_risk_l3": w_home - l_home,
        "away_book_risk_l3": w_away - l_away,
        "draw_book_risk_l3": w_draw - l_draw,
    }


def compute_impedance_index_from_medians(
    home_odds_median: Optional[float],
    home_size_median: Optional[float],
    away_odds_median: Optional[float],
    away_size_median: Optional[float],
    draw_odds_median: Optional[float],
    draw_size_median: Optional[float],
) -> Optional[Dict[str, Optional[float]]]:
    """
    Compute Impedance Index (15m) strictly from the six 15-minute bucket medians.
    
    Structural metric: how liquidity distribution (median sizes) deviates from
    probability distribution (implied by median odds).
    
    Steps:
    1. p_i = 1/O_i (implied probabilities)
    2. w_i = p_i / (p_H + p_A + p_D) (normalized probabilities)
    3. S_total = S_H + S_A + S_D; if S_total <= 0 return None; s_i = S_i/S_total (normalized sizes)
    4. I = sum_i |s_i - w_i| (raw impedance)
    5. I_norm = I/2 (normalized to [0, 1])
    
    Returns None if any median is NULL or S_total <= 0.
    Otherwise returns dict with impedance_index_15m, impedance_abs_diff_home, away, draw.
    """
    if any(m is None for m in [
        home_odds_median, home_size_median,
        away_odds_median, away_size_median,
        draw_odds_median, draw_size_median,
    ]):
        return None
    
    # Avoid division by zero: odds must be > 0 for implied probability
    if home_odds_median <= 0 or away_odds_median <= 0 or draw_odds_median <= 0:
        return None
    
    # Implied probabilities p_i = 1/O_i
    p_h = 1.0 / home_odds_median
    p_a = 1.0 / away_odds_median
    p_d = 1.0 / draw_odds_median
    
    p_sum = p_h + p_a + p_d
    if p_sum <= 0:
        return None
    
    # Normalized probabilities w_i
    w_h = p_h / p_sum
    w_a = p_a / p_sum
    w_d = p_d / p_sum
    
    # Normalized sizes s_i = S_i / S_total
    s_total = home_size_median + away_size_median + draw_size_median
    if s_total <= 0:
        return None
    
    s_h = home_size_median / s_total
    s_a = away_size_median / s_total
    s_d = draw_size_median / s_total
    
    # Absolute differences d_i = |s_i - w_i|
    d_h = abs(s_h - w_h)
    d_a = abs(s_a - w_a)
    d_d = abs(s_d - w_d)
    
    # Raw impedance I = sum d_i; normalized I_norm = I/2 (range 0..1)
    i_raw = d_h + d_a + d_d
    i_norm = i_raw / 2.0
    
    return {
        "impedance_index_15m": i_norm,
        "impedance_abs_diff_home": d_h,
        "impedance_abs_diff_away": d_a,
        "impedance_abs_diff_draw": d_d,
    }


def _compute_median_from_rows(
    rows: List[Tuple[datetime, Optional[float], Optional[float]]],
    bucket_start: datetime,
    effective_end: datetime,
) -> Tuple[Optional[float], Optional[float], float, int]:
    """
    Compute time-weighted median from in-memory rows (publish_time, price, size).
    Same logic as _compute_bucket_median_back_odds_and_size but no DB.
    Returns (median_odds, median_size, seconds_covered, update_count).
    """
    if not rows:
        return (None, None, 0.0, 0)

    # Baseline: latest row with publish_time <= bucket_start
    baseline_row = None
    for r in sorted(rows, key=lambda x: x[0], reverse=True):
        if r[0] <= bucket_start:
            baseline_row = (r[0], r[1], r[2])
            break

    # Updates: rows with publish_time in (bucket_start, effective_end]
    update_rows = [(r[0], r[1], r[2]) for r in rows if bucket_start < r[0] <= effective_end]
    update_rows.sort(key=lambda x: x[0])
    update_count = len(update_rows)

    baseline_odds = baseline_row[1] if baseline_row else None
    baseline_size = baseline_row[2] if baseline_row else None

    if not baseline_row and not update_rows:
        return (None, None, 0.0, 0)

    if baseline_row:
        segment_start = bucket_start
        current_odds = baseline_odds
        current_size = baseline_size
    else:
        segment_start = bucket_start
        current_odds = update_rows[0][1] if update_rows else None
        current_size = update_rows[0][2] if update_rows else None

    segments: List[Tuple[Optional[float], Optional[float], float]] = []

    for pt, odds, size in update_rows:
        if pt > segment_start:
            duration = (pt - segment_start).total_seconds()
            if duration > 0:
                segments.append((current_odds, current_size, duration))
        current_odds = odds
        current_size = size
        segment_start = pt

    if segment_start < effective_end:
        duration = (effective_end - segment_start).total_seconds()
        if duration > 0:
            segments.append((current_odds, current_size, duration))

    odds_segments = [(1.0 / o, d) for o, _, d in segments if o is not None and o > 0]
    size_segments = [(s, d) for _, s, d in segments if s is not None]
    median_odds = None
    median_size = None
    if odds_segments:
        m = _time_weighted_median(odds_segments)
        if m is not None and m > 0:
            median_odds = 1.0 / m
    if size_segments:
        median_size = _time_weighted_median(size_segments)
    seconds_covered = sum(d for _, _, d in segments)
    return (median_odds, median_size, seconds_covered, update_count)


def _time_weighted_median(values_with_weights: List[Tuple[float, float]]) -> Optional[float]:
    """
    Compute time-weighted median from list of (value, weight_seconds) tuples.
    Returns None if empty, otherwise the value where cumulative weight >= 50% of total.
    """
    if not values_with_weights:
        return None
    
    # Sort by value
    sorted_items = sorted(values_with_weights, key=lambda x: x[0])
    
    # Total weight
    total_weight = sum(w for _, w in sorted_items)
    if total_weight == 0:
        return None
    
    # Find median: cumulative weight >= 50%
    cumulative = 0.0
    for value, weight in sorted_items:
        cumulative += weight
        if cumulative >= total_weight * 0.5:
            return value
    
    # Fallback (shouldn't happen)
    return sorted_items[-1][0]


def _compute_bucket_median_back_odds_and_size(
    cur: Any,
    market_id: str,
    selection_id: int,
    bucket_start: datetime,
    bucket_end: datetime,
    effective_end: datetime,
) -> Tuple[Optional[float], Optional[float], float, int]:
    """
    Compute time-weighted median of back_odds and back_size for a selection in a bucket.
    
    Returns (median_odds, median_size, seconds_covered, update_count).
    seconds_covered: total seconds in bucket with a carried/known value.
    update_count: number of tick updates in [bucket_start, effective_end].
    """
    # Step A: Baseline lookup (latest before bucket_start)
    cur.execute(
        """
        SELECT price, size, publish_time
        FROM stream_ingest.ladder_levels
        WHERE market_id = %s
          AND selection_id = %s
          AND side = 'B'
          AND level = 0
          AND publish_time <= %s
        ORDER BY publish_time DESC
        LIMIT 1
        """,
        (market_id, selection_id, bucket_start),
    )
    baseline_row = cur.fetchone()
    
    baseline_odds = None
    baseline_size = None
    if baseline_row:
        baseline_odds = float(baseline_row["price"]) if baseline_row.get("price") is not None else None
        baseline_size = float(baseline_row["size"]) if baseline_row.get("size") is not None else None
    
    # Step B: Get all updates in bucket
    cur.execute(
        """
        SELECT price, size, publish_time
        FROM stream_ingest.ladder_levels
        WHERE market_id = %s
          AND selection_id = %s
          AND side = 'B'
          AND level = 0
          AND publish_time > %s
          AND publish_time <= %s
        ORDER BY publish_time ASC
        """,
        (market_id, selection_id, bucket_start, effective_end),
    )
    update_rows = cur.fetchall()
    
    update_count = len(update_rows)
    # If no baseline and no updates, return NULL with zero coverage
    if not baseline_row and not update_rows:
        return (None, None, 0.0, 0)
    
    # Step C: Build time segments
    segments: List[Tuple[Optional[float], Optional[float], float]] = []  # (odds, size, duration_seconds)
    
    # Determine segment start time
    if baseline_row:
        # Baseline exists: first segment starts at bucket_start with baseline value
        segment_start = bucket_start
        current_odds = baseline_odds
        current_size = baseline_size
    elif update_rows:
        # No baseline but updates exist: first segment starts at bucket_start with first update value
        segment_start = bucket_start
        current_odds = float(update_rows[0]["price"]) if update_rows[0].get("price") is not None else None
        current_size = float(update_rows[0]["size"]) if update_rows[0].get("size") is not None else None
    else:
        return (None, None, 0.0, 0)
    
    # Process updates to build segments
    for i, row in enumerate(update_rows):
        update_time = row["publish_time"]
        update_odds = float(row["price"]) if row.get("price") is not None else None
        update_size = float(row["size"]) if row.get("size") is not None else None
        
        # Segment from segment_start to this update (if there's a gap)
        if update_time > segment_start:
            duration = (update_time - segment_start).total_seconds()
            if duration > 0:
                segments.append((current_odds, current_size, duration))
        
        # Update current values for next segment
        current_odds = update_odds
        current_size = update_size
        segment_start = update_time
    
    # Final segment: from last update (or bucket_start if no updates) to effective_end
    if segment_start < effective_end:
        duration = (effective_end - segment_start).total_seconds()
        if duration > 0:
            segments.append((current_odds, current_size, duration))
    
    # Step D: Compute time-weighted medians
    # For odds: use 1/odds for stability, then convert back
    odds_segments = [(1.0 / odds, duration) for odds, _, duration in segments if odds is not None and odds > 0]
    size_segments = [(size, duration) for _, size, duration in segments if size is not None]
    
    median_odds = None
    median_size = None
    
    if odds_segments:
        median_inv_odds = _time_weighted_median(odds_segments)
        if median_inv_odds is not None and median_inv_odds > 0:
            median_odds = 1.0 / median_inv_odds
    
    if size_segments:
        median_size = _time_weighted_median(size_segments)
    
    seconds_covered = sum(d for _, _, d in segments)
    return (median_odds, median_size, seconds_covered, update_count)


def get_stream_markets_with_ladder_for_date(from_dt: datetime, to_dt: datetime) -> List[str]:
    """Market IDs that have at least one ladder_levels row in [from_dt, to_dt] (for date filter)."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT market_id
            FROM stream_ingest.ladder_levels
            WHERE publish_time >= %s AND publish_time < %s
            """,
            (from_dt, to_dt),
        )
        return [r["market_id"] for r in cur.fetchall()]


def get_events_by_date_snapshots_stream(date_str: str) -> List[Dict[str, Any]]:
    """
    Same shape as REST get_events_by_date_snapshots but from stream_ingest.
    Uses the latest 15-min bucket that falls inside the date as "latest_snapshot_at".
    Staleness: exclude market if latest ladder update in that bucket is older than STALE_MINUTES.
    """
    try:
        from_dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return []
    to_dt = from_dt + timedelta(days=1)
    now = datetime.now(timezone.utc)
    # Only consider buckets up to current time (not end of day)
    effective_to_dt = min(to_dt, now)
    bucket_times = _bucket_times_in_range(from_dt, effective_to_dt)
    if not bucket_times:
        bucket_times = [_bucket_15_utc(from_dt)]

    # Use the latest bucket up to current time as "latest" for each market
    latest_bucket = bucket_times[-1] if bucket_times else _bucket_15_utc(effective_to_dt - timedelta(seconds=1))
    stale_cutoff = latest_bucket - timedelta(minutes=STALE_MINUTES)

    with cursor() as cur:
        # Stream-first approach: get markets with streaming data in this date range
        stream_markets = get_stream_markets_with_ladder_for_date(from_dt, to_dt)
        if not stream_markets:
            return []

        # Left join to metadata - don't require event_open_date to be in the date range
        # This allows events that started earlier but are still receiving streaming data today
        cur.execute(
            """
            SELECT m.market_id, m.event_id, m.event_name, m.event_open_date, m.competition_name,
                   m.home_selection_id, m.away_selection_id, m.draw_selection_id
            FROM market_event_metadata m
            WHERE m.market_id = ANY(%s)
            ORDER BY COALESCE(m.event_open_date, '1970-01-01'::timestamp) ASC, m.market_id
            """,
            (stream_markets,),
        )
        meta_rows = cur.fetchall()

    result: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for m in meta_rows:
        market_id = m["market_id"]
        with cursor() as c:
            last_pt = _latest_publish_before(c, market_id, latest_bucket)
        if last_pt is None:
            continue
        if last_pt < stale_cutoff:
            continue  # Stale: no update in last STALE_MINUTES
        
        bucket_start = latest_bucket
        bucket_end = latest_bucket + timedelta(minutes=15)
        effective_end = min(bucket_end, now)
        
        with cursor() as cur:
            home_odds_median, home_size_median = (None, None)
            away_odds_median, away_size_median = (None, None)
            draw_odds_median, draw_size_median = (None, None)
            home_seconds_covered = away_seconds_covered = draw_seconds_covered = 0.0
            home_update_count = away_update_count = draw_update_count = 0
            if m.get("home_selection_id") is not None:
                home_odds_median, home_size_median, home_seconds_covered, home_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, m["home_selection_id"], bucket_start, bucket_end, effective_end
                )
            if m.get("away_selection_id") is not None:
                away_odds_median, away_size_median, away_seconds_covered, away_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, m["away_selection_id"], bucket_start, bucket_end, effective_end
                )
            if m.get("draw_selection_id") is not None:
                draw_odds_median, draw_size_median, draw_seconds_covered, draw_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, m["draw_selection_id"], bucket_start, bucket_end, effective_end
                )
            book_risk = compute_book_risk_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            
            # Compute Impedance Index (15m) from medians only
            impedance = compute_impedance_index_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            
            # Also get latest state for best_back/best_lay (for compatibility with existing API shape)
            # Note: These are NOT used for risk computation, only for display compatibility
            runners, home_bb, away_bb, draw_bb, home_bl, away_bl, draw_bl, total_volume = _runners_from_ladder(
                cur, market_id, latest_bucket,
                m.get("home_selection_id"), m.get("away_selection_id"), m.get("draw_selection_id"),
            )

        result.append({
            "market_id": market_id,
            "event_id": m.get("event_id"),
            "event_name": m.get("event_name"),
            "event_open_date": m["event_open_date"].isoformat() if m.get("event_open_date") else None,
            "competition_name": m.get("competition_name"),
            "latest_snapshot_at": latest_bucket.isoformat(),
            "home_best_back": home_bb,
            "away_best_back": away_bb,
            "draw_best_back": draw_bb,
            "home_best_lay": home_bl,
            "away_best_lay": away_bl,
            "draw_best_lay": draw_bl,
            "total_volume": total_volume,
            "depth_limit": DEPTH_LIMIT,
            "calculation_version": "stream_15min",
            "home_book_risk_l3": book_risk["home_book_risk_l3"] if book_risk else None,
            "away_book_risk_l3": book_risk["away_book_risk_l3"] if book_risk else None,
            "draw_book_risk_l3": book_risk["draw_book_risk_l3"] if book_risk else None,
            "impedance_index_15m": impedance["impedance_index_15m"] if impedance else None,
            "impedance_abs_diff_home": impedance["impedance_abs_diff_home"] if impedance else None,
            "impedance_abs_diff_away": impedance["impedance_abs_diff_away"] if impedance else None,
            "impedance_abs_diff_draw": impedance["impedance_abs_diff_draw"] if impedance else None,
            "home_seconds_covered": home_seconds_covered,
            "home_update_count": home_update_count,
            "away_seconds_covered": away_seconds_covered,
            "away_update_count": away_update_count,
            "draw_seconds_covered": draw_seconds_covered,
            "draw_update_count": draw_update_count,
        })

    return result


def get_event_timeseries_stream(
    market_id: str,
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
    interval_minutes: int,
) -> List[Dict[str, Any]]:
    """
    Timeseries for one market from stream_ingest: 15-min buckets with time-weighted medians.
    Same response shape as REST timeseries. interval_minutes forced to 15 for stream.
    
    Uses time-weighted median for back_odds and back_size per bucket (carry-forward logic).
    """
    now = datetime.now(timezone.utc)
    to_dt = min(to_ts, now) if to_ts else now
    from_dt = from_ts or (now - timedelta(hours=24))
    # Ensure from_dt <= to_dt
    if from_dt > to_dt:
        from_dt = to_dt - timedelta(hours=24)
    interval_minutes = 15  # Stream: fixed 15-min UTC buckets
    bucket_times = _bucket_times_in_range(from_dt, to_dt)
    stale_cutoff_minutes = STALE_MINUTES

    with cursor() as cur:
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
        return []

    home_sid = meta.get("home_selection_id")
    away_sid = meta.get("away_selection_id")
    draw_sid = meta.get("draw_selection_id")
    out: List[Dict[str, Any]] = []
    # For staleness check, use current time, not bucket time
    now_for_staleness = datetime.now(timezone.utc)
    stale_cutoff_time = now_for_staleness - timedelta(minutes=stale_cutoff_minutes)
    
    for bucket_time in bucket_times:
        bucket_start = bucket_time
        bucket_end = bucket_time + timedelta(minutes=15)
        effective_end = min(bucket_end, now)
        
        with cursor() as cur:
            last_pt = _latest_publish_before(cur, market_id, bucket_time)
            if last_pt is None:
                continue
            # Check if last publish time is stale relative to NOW (not bucket_time)
            # This allows showing historical buckets even if they're old
            # Only skip if the latest data for this bucket is stale relative to current time
            if last_pt < stale_cutoff_time:
                continue
            
            # Compute time-weighted medians for back odds and size (and coverage)
            home_odds_median, home_size_median = (None, None)
            away_odds_median, away_size_median = (None, None)
            draw_odds_median, draw_size_median = (None, None)
            home_seconds_covered = away_seconds_covered = draw_seconds_covered = 0.0
            home_update_count = away_update_count = draw_update_count = 0
            if home_sid is not None:
                home_odds_median, home_size_median, home_seconds_covered, home_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, home_sid, bucket_start, bucket_end, effective_end
                )
            if away_sid is not None:
                away_odds_median, away_size_median, away_seconds_covered, away_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, away_sid, bucket_start, bucket_end, effective_end
                )
            if draw_sid is not None:
                draw_odds_median, draw_size_median, draw_seconds_covered, draw_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, draw_sid, bucket_start, bucket_end, effective_end
                )
            
            # Compute Book Risk strictly from medians
            book_risk = compute_book_risk_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            
            # Compute Impedance Index (15m) from medians only
            impedance = compute_impedance_index_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            
            # Also get latest state for best_back/best_lay (for compatibility with existing API shape)
            runners, home_bb, away_bb, draw_bb, home_bl, away_bl, draw_bl, total_volume = _runners_from_ladder(
                cur, market_id, bucket_time, home_sid, away_sid, draw_sid,
            )

        out.append({
            "snapshot_at": bucket_time.isoformat(),
            "home_best_back": home_bb,
            "away_best_back": away_bb,
            "draw_best_back": draw_bb,
            "home_best_lay": home_bl,
            "away_best_lay": away_bl,
            "draw_best_lay": draw_bl,
            "home_back_odds_median": home_odds_median,
            "home_back_size_median": home_size_median,
            "away_back_odds_median": away_odds_median,
            "away_back_size_median": away_size_median,
            "draw_back_odds_median": draw_odds_median,
            "draw_back_size_median": draw_size_median,
            "home_seconds_covered": home_seconds_covered,
            "home_update_count": home_update_count,
            "away_seconds_covered": away_seconds_covered,
            "away_update_count": away_update_count,
            "draw_seconds_covered": draw_seconds_covered,
            "draw_update_count": draw_update_count,
            "home_book_risk_l3": book_risk["home_book_risk_l3"] if book_risk else None,
            "away_book_risk_l3": book_risk["away_book_risk_l3"] if book_risk else None,
            "draw_book_risk_l3": book_risk["draw_book_risk_l3"] if book_risk else None,
            "impedance_index_15m": impedance["impedance_index_15m"] if impedance else None,
            "impedance_abs_diff_home": impedance["impedance_abs_diff_home"] if impedance else None,
            "impedance_abs_diff_away": impedance["impedance_abs_diff_away"] if impedance else None,
            "impedance_abs_diff_draw": impedance["impedance_abs_diff_draw"] if impedance else None,
            "total_volume": total_volume,
            "depth_limit": DEPTH_LIMIT,
            "calculation_version": "stream_15min",
        })

    return out


def _tick_count_in_bucket(cur: Any, market_id: str, bucket_start: datetime, bucket_end: datetime) -> int:
    """Count tick rows (level=0, side=B) in ladder_levels for market in [bucket_start, bucket_end)."""
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM stream_ingest.ladder_levels
        WHERE market_id = %s
          AND side = 'B'
          AND level = 0
          AND publish_time >= %s
          AND publish_time < %s
        """,
        (market_id, bucket_start, bucket_end),
    )
    row = cur.fetchone()
    return int(row["cnt"]) if row and row.get("cnt") is not None else 0


def get_event_buckets_stream_bulk(
    market_id: str,
    from_dt: datetime,
    to_dt: datetime,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Bulk buckets: 3 DB queries total. No per-bucket queries.
    Returns (buckets_list, db_query_count).
    Default range: last 180 min (12 buckets).

    Assumptions (see docs/BULK_BUCKETS_EXPLAIN_ANALYZE.md):
    - Impedance index and Book Risk use only top-of-book back (level 0, side B).
    - No lay prices or multiple levels required for these metrics.
    """
    db_count = 0

    with cursor() as cur:
        cur.execute(
            """
            SELECT m.market_id, m.event_id, m.event_name, m.event_open_date, m.competition_name,
                   m.home_selection_id, m.away_selection_id, m.draw_selection_id
            FROM market_event_metadata m
            WHERE m.market_id = %s
            """,
            (market_id,),
        )
        meta = cur.fetchone()
        db_count += 1
    if not meta:
        return [], db_count

    home_sid = meta.get("home_selection_id")
    away_sid = meta.get("away_selection_id")
    draw_sid = meta.get("draw_selection_id")
    selection_ids = [s for s in [home_sid, away_sid, draw_sid] if s is not None]
    if not selection_ids:
        return [], db_count

    # Extend range 15 min back for baseline of first bucket
    fetch_from = from_dt - timedelta(minutes=15)
    fetch_to = to_dt + timedelta(minutes=15)
    now = datetime.now(timezone.utc)

    # Query 2: ladder_levels - only top-of-book back (level 0, side B) for impedance + book risk
    with cursor() as cur:
        cur.execute(
            """
            SELECT publish_time, selection_id, price, size
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s
              AND selection_id = ANY(%s)
              AND side = 'B'
              AND level = 0
              AND publish_time >= %s
              AND publish_time <= %s
            ORDER BY publish_time ASC
            """,
            (market_id, selection_ids, fetch_from, fetch_to),
        )
        all_rows = cur.fetchall()
        db_count += 1

    # Query 3: market_liquidity_history - total_volume (total_matched) per bucket
    with cursor() as cur:
        cur.execute(
            """
            SELECT publish_time, total_matched
            FROM stream_ingest.market_liquidity_history
            WHERE market_id = %s
              AND publish_time >= %s
              AND publish_time <= %s
            ORDER BY publish_time ASC
            """,
            (market_id, fetch_from, fetch_to),
        )
        liq_rows = cur.fetchall()
        db_count += 1

    # Build liquidity lookup: for each bucket_end, latest total_matched at or before bucket_end
    liq_list: List[Tuple[datetime, Optional[float]]] = []
    for r in liq_rows:
        pt = r["publish_time"]
        if pt.tzinfo is None:
            pt = pt.replace(tzinfo=timezone.utc)
        tv = float(r["total_matched"]) if r.get("total_matched") is not None else None
        liq_list.append((pt, tv))

    def total_volume_at(bucket_end_ts: datetime) -> Optional[float]:
        best = None
        for pt, tv in liq_list:
            if pt <= bucket_end_ts:
                best = tv
        return best

    # Group by selection_id for efficient lookup
    by_sel: Dict[int, List[Tuple[datetime, Optional[float], Optional[float]]]] = {}
    for sid in selection_ids:
        by_sel[sid] = []
    for r in all_rows:
        sid = int(r["selection_id"])
        if sid not in by_sel:
            continue
        pt = r["publish_time"]
        if pt.tzinfo is None:
            pt = pt.replace(tzinfo=timezone.utc)
        price = float(r["price"]) if r.get("price") is not None else None
        size = float(r["size"]) if r.get("size") is not None else None
        by_sel[sid].append((pt, price, size))

    bucket_times = _bucket_times_in_range(from_dt, to_dt)
    out: List[Dict[str, Any]] = []

    for bucket_time in bucket_times:
        bucket_start = bucket_time
        bucket_end = bucket_time + timedelta(minutes=15)
        effective_end = min(bucket_end, now)

        # Tick count: rows with publish_time in [bucket_start, bucket_end) for any selection
        tick_count = 0
        for sid in selection_ids:
            for pt, _, _ in by_sel.get(sid, []):
                if bucket_start <= pt < bucket_end:
                    tick_count += 1

        home_odds_median, home_size_median = (None, None)
        away_odds_median, away_size_median = (None, None)
        draw_odds_median, draw_size_median = (None, None)
        home_seconds_covered = away_seconds_covered = draw_seconds_covered = 0.0
        home_update_count = away_update_count = draw_update_count = 0

        if home_sid is not None:
            home_odds_median, home_size_median, home_seconds_covered, home_update_count = _compute_median_from_rows(
                by_sel.get(home_sid, []), bucket_start, effective_end
            )
        if away_sid is not None:
            away_odds_median, away_size_median, away_seconds_covered, away_update_count = _compute_median_from_rows(
                by_sel.get(away_sid, []), bucket_start, effective_end
            )
        if draw_sid is not None:
            draw_odds_median, draw_size_median, draw_seconds_covered, draw_update_count = _compute_median_from_rows(
                by_sel.get(draw_sid, []), bucket_start, effective_end
            )

        book_risk = compute_book_risk_from_medians(
            home_odds_median, home_size_median,
            away_odds_median, away_size_median,
            draw_odds_median, draw_size_median,
        )
        impedance = compute_impedance_index_from_medians(
            home_odds_median, home_size_median,
            away_odds_median, away_size_median,
            draw_odds_median, draw_size_median,
        )

        # Best back at bucket_time: latest row with publish_time <= bucket_time
        def best_back_at(sid: int) -> Optional[float]:
            rows = [(pt, price) for pt, price, _ in by_sel.get(sid, [])
                    if pt <= bucket_time and price is not None]
            if not rows:
                return None
            return max(rows, key=lambda x: x[0])[1]

        home_bb = best_back_at(home_sid) if home_sid else None
        away_bb = best_back_at(away_sid) if away_sid else None
        draw_bb = best_back_at(draw_sid) if draw_sid else None

        out.append({
            "bucket_start": bucket_start.isoformat(),
            "bucket_end": bucket_end.isoformat(),
            "tick_count": tick_count,
            "snapshot_at": bucket_start.isoformat(),
            "home_best_back": home_bb,
            "away_best_back": away_bb,
            "draw_best_back": draw_bb,
            "home_best_lay": None,
            "away_best_lay": None,
            "draw_best_lay": None,
            "home_back_odds_median": home_odds_median,
            "home_back_size_median": home_size_median,
            "away_back_odds_median": away_odds_median,
            "away_back_size_median": away_size_median,
            "draw_back_odds_median": draw_odds_median,
            "draw_back_size_median": draw_size_median,
            "home_seconds_covered": home_seconds_covered,
            "home_update_count": home_update_count,
            "away_seconds_covered": away_seconds_covered,
            "away_update_count": away_update_count,
            "draw_seconds_covered": draw_seconds_covered,
            "draw_update_count": draw_update_count,
            "home_book_risk_l3": book_risk["home_book_risk_l3"] if book_risk else None,
            "away_book_risk_l3": book_risk["away_book_risk_l3"] if book_risk else None,
            "draw_book_risk_l3": book_risk["draw_book_risk_l3"] if book_risk else None,
            "impedance_index_15m": impedance["impedance_index_15m"] if impedance else None,
            "impedance_abs_diff_home": impedance["impedance_abs_diff_home"] if impedance else None,
            "impedance_abs_diff_away": impedance["impedance_abs_diff_away"] if impedance else None,
            "impedance_abs_diff_draw": impedance["impedance_abs_diff_draw"] if impedance else None,
            "total_volume": total_volume_at(effective_end),
            "depth_limit": DEPTH_LIMIT,
            "calculation_version": "stream_15min_bulk",
        })

    return out, db_count


def get_event_buckets_stream(market_id: str) -> List[Dict[str, Any]]:
    """
    All 15-min UTC buckets for a market that have at least one tick.
    No date/window filter; no staleness filter. Ordered oldest first (ASC) for consistent
    chart (left→right) and table (top→bottom) chronology; latest = last element.
    Uses same medians/coverage/risk shape as timeseries for UI compatibility.
    """
    with cursor() as cur:
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
        return []

    with cursor() as cur:
        cur.execute(
            """
            SELECT MIN(publish_time) AS min_pt, MAX(publish_time) AS max_pt
            FROM stream_ingest.ladder_levels
            WHERE market_id = %s
            """,
            (market_id,),
        )
        row = cur.fetchone()
    if not row or row.get("min_pt") is None or row.get("max_pt") is None:
        return []

    min_pt = row["min_pt"]
    max_pt = row["max_pt"]
    if min_pt.tzinfo is None:
        min_pt = min_pt.replace(tzinfo=timezone.utc)
    if max_pt.tzinfo is None:
        max_pt = max_pt.replace(tzinfo=timezone.utc)
    from_dt = _bucket_15_utc(min_pt)
    # Include bucket that contains max_pt
    to_dt = max_pt + timedelta(minutes=1)
    now = datetime.now(timezone.utc)
    bucket_times = _bucket_times_in_range(from_dt, to_dt)

    home_sid = meta.get("home_selection_id")
    away_sid = meta.get("away_selection_id")
    draw_sid = meta.get("draw_selection_id")
    out: List[Dict[str, Any]] = []

    for bucket_time in bucket_times:
        bucket_start = bucket_time
        bucket_end = bucket_time + timedelta(minutes=15)
        effective_end = min(bucket_end, now)

        with cursor() as cur:
            last_pt = _latest_publish_before(cur, market_id, bucket_time)
            if last_pt is None:
                continue

            tick_count = _tick_count_in_bucket(cur, market_id, bucket_start, bucket_end)

            home_odds_median, home_size_median = (None, None)
            away_odds_median, away_size_median = (None, None)
            draw_odds_median, draw_size_median = (None, None)
            home_seconds_covered = away_seconds_covered = draw_seconds_covered = 0.0
            home_update_count = away_update_count = draw_update_count = 0
            if home_sid is not None:
                home_odds_median, home_size_median, home_seconds_covered, home_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, home_sid, bucket_start, bucket_end, effective_end
                )
            if away_sid is not None:
                away_odds_median, away_size_median, away_seconds_covered, away_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, away_sid, bucket_start, bucket_end, effective_end
                )
            if draw_sid is not None:
                draw_odds_median, draw_size_median, draw_seconds_covered, draw_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, draw_sid, bucket_start, bucket_end, effective_end
                )

            book_risk = compute_book_risk_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            impedance = compute_impedance_index_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            runners, home_bb, away_bb, draw_bb, home_bl, away_bl, draw_bl, total_volume = _runners_from_ladder(
                cur, market_id, bucket_time, home_sid, away_sid, draw_sid,
            )

        out.append({
            "bucket_start": bucket_start.isoformat(),
            "bucket_end": bucket_end.isoformat(),
            "tick_count": tick_count,
            "snapshot_at": bucket_start.isoformat(),
            "home_best_back": home_bb,
            "away_best_back": away_bb,
            "draw_best_back": draw_bb,
            "home_best_lay": home_bl,
            "away_best_lay": away_bl,
            "draw_best_lay": draw_bl,
            "home_back_odds_median": home_odds_median,
            "home_back_size_median": home_size_median,
            "away_back_odds_median": away_odds_median,
            "away_back_size_median": away_size_median,
            "draw_back_odds_median": draw_odds_median,
            "draw_back_size_median": draw_size_median,
            "home_seconds_covered": home_seconds_covered,
            "home_update_count": home_update_count,
            "away_seconds_covered": away_seconds_covered,
            "away_update_count": away_update_count,
            "draw_seconds_covered": draw_seconds_covered,
            "draw_update_count": draw_update_count,
            "home_book_risk_l3": book_risk["home_book_risk_l3"] if book_risk else None,
            "away_book_risk_l3": book_risk["away_book_risk_l3"] if book_risk else None,
            "draw_book_risk_l3": book_risk["draw_book_risk_l3"] if book_risk else None,
            "impedance_index_15m": impedance["impedance_index_15m"] if impedance else None,
            "impedance_abs_diff_home": impedance["impedance_abs_diff_home"] if impedance else None,
            "impedance_abs_diff_away": impedance["impedance_abs_diff_away"] if impedance else None,
            "impedance_abs_diff_draw": impedance["impedance_abs_diff_draw"] if impedance else None,
            "total_volume": total_volume,
            "depth_limit": DEPTH_LIMIT,
            "calculation_version": "stream_15min",
        })

    # Return oldest first (ASC): chart left→right, table top→bottom; latest = last
    return out


def get_leagues_stream(
    from_dt: datetime,
    to_dt: datetime,
    q: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, str]]:
    """Leagues (competition_name) that have stream ladder data in the window. Uses metadata + stream_ingest."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT e.competition_name AS league
            FROM market_event_metadata e
            INNER JOIN stream_ingest.ladder_levels l ON l.market_id = e.market_id
            WHERE e.event_open_date IS NOT NULL
              AND e.event_open_date >= %s
              AND e.event_open_date <= %s
              AND l.publish_time >= %s
              AND l.publish_time <= %s
            """,
            (from_dt, to_dt, from_dt, to_dt),
        )
        leagues = [r["league"] or "Unknown" for r in cur.fetchall() if r.get("league")]

        if q and q.strip():
            search = f"%{q.strip()}%"
            cur.execute(
                """
                SELECT e.competition_name AS league, COUNT(DISTINCT e.market_id) AS event_count
                FROM market_event_metadata e
                INNER JOIN stream_ingest.ladder_levels l ON l.market_id = e.market_id
                WHERE e.event_open_date IS NOT NULL
                  AND e.event_open_date >= %s AND e.event_open_date <= %s
                  AND l.publish_time >= %s AND l.publish_time <= %s
                  AND (e.event_name ILIKE %s OR e.home_runner_name ILIKE %s OR e.away_runner_name ILIKE %s)
                GROUP BY e.competition_name
                ORDER BY event_count DESC, e.competition_name
                LIMIT %s OFFSET %s
                """,
                (from_dt, to_dt, from_dt, to_dt, search, search, search, limit, offset),
            )
            rows = cur.fetchall()
            return [{"league": r["league"] or "Unknown", "event_count": r["event_count"]} for r in rows]

        cur.execute(
            """
            SELECT e.competition_name AS league, COUNT(DISTINCT e.market_id) AS event_count
            FROM market_event_metadata e
            INNER JOIN stream_ingest.ladder_levels l ON l.market_id = e.market_id
            WHERE e.event_open_date IS NOT NULL
              AND e.event_open_date >= %s AND e.event_open_date <= %s
              AND l.publish_time >= %s AND l.publish_time <= %s
            GROUP BY e.competition_name
            ORDER BY event_count DESC, e.competition_name
            LIMIT %s OFFSET %s
            """,
            (from_dt, to_dt, from_dt, to_dt, limit, offset),
        )
        rows = cur.fetchall()
    return [{"league": r["league"] or "Unknown", "event_count": r["event_count"]} for r in rows]


def get_league_events_stream(
    league_name: str,
    from_dt: datetime,
    to_dt: datetime,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    """Events in league with latest 15-min bucket from stream. Same shape as REST league events."""
    # Latest bucket in range
    bucket_times = _bucket_times_in_range(from_dt, to_dt)
    latest_bucket = bucket_times[-1] if bucket_times else _bucket_15_utc(to_dt - timedelta(seconds=1))
    stale_cutoff = latest_bucket - timedelta(minutes=STALE_MINUTES)

    with cursor() as cur:
        cur.execute(
            """
            SELECT e.market_id, e.event_id, e.event_name, e.event_open_date, e.competition_name,
                   e.home_selection_id, e.away_selection_id, e.draw_selection_id
            FROM market_event_metadata e
            WHERE e.competition_name = %s
              AND e.event_open_date IS NOT NULL
              AND e.event_open_date >= %s AND e.event_open_date <= %s
            ORDER BY e.event_open_date ASC
            LIMIT %s OFFSET %s
            """,
            (league_name, from_dt, to_dt, limit, offset),
        )
        meta_rows = cur.fetchall()

    result: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for m in meta_rows:
        market_id = m["market_id"]
        bucket_start = latest_bucket
        bucket_end = latest_bucket + timedelta(minutes=15)
        effective_end = min(bucket_end, now)
        
        with cursor() as cur:
            last_pt = _latest_publish_before(cur, market_id, latest_bucket)
            if last_pt is None or last_pt < stale_cutoff:
                continue
            
            home_seconds_covered = away_seconds_covered = draw_seconds_covered = 0.0
            home_update_count = away_update_count = draw_update_count = 0
            if m.get("home_selection_id") is not None:
                home_odds_median, home_size_median, home_seconds_covered, home_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, m["home_selection_id"], bucket_start, bucket_end, effective_end
                )
            if m.get("away_selection_id") is not None:
                away_odds_median, away_size_median, away_seconds_covered, away_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, m["away_selection_id"], bucket_start, bucket_end, effective_end
                )
            if m.get("draw_selection_id") is not None:
                draw_odds_median, draw_size_median, draw_seconds_covered, draw_update_count = _compute_bucket_median_back_odds_and_size(
                    cur, market_id, m["draw_selection_id"], bucket_start, bucket_end, effective_end
                )
            
            book_risk = compute_book_risk_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            impedance = compute_impedance_index_from_medians(
                home_odds_median, home_size_median,
                away_odds_median, away_size_median,
                draw_odds_median, draw_size_median,
            )
            runners, home_bb, away_bb, draw_bb, home_bl, away_bl, draw_bl, total_volume = _runners_from_ladder(
                cur, market_id, latest_bucket,
                m.get("home_selection_id"), m.get("away_selection_id"), m.get("draw_selection_id"),
            )

        result.append({
            "market_id": market_id,
            "event_id": m.get("event_id"),
            "event_name": m.get("event_name"),
            "event_open_date": m["event_open_date"].isoformat() if m.get("event_open_date") else None,
            "competition_name": m.get("competition_name"),
            "latest_snapshot_at": latest_bucket.isoformat(),
            "home_best_back": home_bb, "away_best_back": away_bb, "draw_best_back": draw_bb,
            "home_best_lay": home_bl, "away_best_lay": away_bl, "draw_best_lay": draw_bl,
            "total_volume": total_volume,
            "depth_limit": DEPTH_LIMIT,
            "calculation_version": "stream_15min",
            "home_book_risk_l3": book_risk["home_book_risk_l3"] if book_risk else None,
            "away_book_risk_l3": book_risk["away_book_risk_l3"] if book_risk else None,
            "draw_book_risk_l3": book_risk["draw_book_risk_l3"] if book_risk else None,
            "impedance_index_15m": impedance["impedance_index_15m"] if impedance else None,
            "impedance_abs_diff_home": impedance["impedance_abs_diff_home"] if impedance else None,
            "impedance_abs_diff_away": impedance["impedance_abs_diff_away"] if impedance else None,
            "impedance_abs_diff_draw": impedance["impedance_abs_diff_draw"] if impedance else None,
            "home_seconds_covered": home_seconds_covered,
            "home_update_count": home_update_count,
            "away_seconds_covered": away_seconds_covered,
            "away_update_count": away_update_count,
            "draw_seconds_covered": draw_seconds_covered,
            "draw_update_count": draw_update_count,
        })

    return result
