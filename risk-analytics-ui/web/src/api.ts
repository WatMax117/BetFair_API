// Base path for API (e.g. /api or /api/stream for stream UI). No trailing slash.
// When window.__API_BASE__ is set (e.g. by /stream route), that is used so the same app can call stream endpoints.
export function getApiBase(): string {
  if (typeof window !== 'undefined') {
    const win = window as unknown as { __API_BASE__?: string }
    if (win.__API_BASE__) {
      console.log('[api] getApiBase: using window.__API_BASE__', win.__API_BASE__)
      return win.__API_BASE__
    }
  }
  const defaultBase = import.meta.env.VITE_API_URL ?? '/api'
  console.log('[api] getApiBase: using default', defaultBase, 'pathname:', typeof window !== 'undefined' ? window.location.pathname : 'N/A')
  // If we're on /stream route but __API_BASE__ wasn't set, force it
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/stream')) {
    console.warn('[api] getApiBase: on /stream route but __API_BASE__ not set, forcing /api/stream')
    return '/api/stream'
  }
  return defaultBase
}

function toISO(d: Date): string {
  return d.toISOString()
}

export type LeagueItem = { league: string; event_count: number }

/** H/A/D triplet (e.g. Book Risk L3). Same ordering: home, away, draw. */
export type HadTriplet = { home: number | null; away: number | null; draw: number | null }

export type EventItem = {
  market_id: string
  event_name: string
  event_open_date: string | null
  competition_name: string | null
  latest_snapshot_at: string | null
  home_best_back: number | null
  away_best_back: number | null
  draw_best_back: number | null
  home_best_lay: number | null
  away_best_lay: number | null
  draw_best_lay: number | null
  total_volume: number | null
  depth_limit: number | null
  calculation_version: string | null
  home_book_risk_l3?: number | null
  away_book_risk_l3?: number | null
  draw_book_risk_l3?: number | null
  /** Last stream tick time; null if no stream data. UI may mark row as stale when old. */
  last_stream_update_at?: string | null
  /** True when last_stream_update_at < now - 120 min; informational only, never excludes row. */
  is_stale?: boolean
}

export type TimeseriesPoint = {
  snapshot_at: string | null
  home_best_back: number | null
  away_best_back: number | null
  draw_best_back: number | null
  home_best_lay: number | null
  away_best_lay: number | null
  draw_best_lay: number | null
  total_volume: number | null
  depth_limit?: number | null
  calculation_version?: string | null
  // 15-minute bucket medians (new)
  home_back_odds_median?: number | null
  home_back_size_median?: number | null
  away_back_odds_median?: number | null
  away_back_size_median?: number | null
  draw_back_odds_median?: number | null
  draw_back_size_median?: number | null
  // Legacy L1/L2/L3 fields (deprecated, kept for compatibility)
  home_best_back_size_l1?: number | null
  away_best_back_size_l1?: number | null
  draw_best_back_size_l1?: number | null
  home_best_lay_size_l1?: number | null
  away_best_lay_size_l1?: number | null
  draw_best_lay_size_l1?: number | null
  home_back_odds_l2?: number | null
  home_back_size_l2?: number | null
  home_back_odds_l3?: number | null
  home_back_size_l3?: number | null
  away_back_odds_l2?: number | null
  away_back_size_l2?: number | null
  away_back_odds_l3?: number | null
  away_back_size_l3?: number | null
  draw_back_odds_l2?: number | null
  draw_back_size_l2?: number | null
  draw_back_odds_l3?: number | null
  draw_back_size_l3?: number | null
  home_book_risk_l3?: number | null
  away_book_risk_l3?: number | null
  draw_book_risk_l3?: number | null
  // Impedance Index (15m) from medians only
  impedance_index_15m?: number | null
  impedance_abs_diff_home?: number | null
  impedance_abs_diff_away?: number | null
  impedance_abs_diff_draw?: number | null
  // Data coverage per outcome (seconds with value in bucket, tick update count)
  home_seconds_covered?: number
  home_update_count?: number
  away_seconds_covered?: number
  away_update_count?: number
  draw_seconds_covered?: number
  draw_update_count?: number
}

/** Single 15-min bucket from GET /events/{market_id}/buckets (all available, no window filter). */
export type BucketItem = TimeseriesPoint & {
  bucket_start: string
  bucket_end: string
  tick_count: number
}

export type TickRow = {
  publish_time: string | null
  selection_id: number | null
  back_odds: number | null
  back_size: number | null
  home_back_odds: number | null
  home_back_size: number | null
  away_back_odds: number | null
  away_back_size: number | null
  draw_back_odds: number | null
  draw_back_size: number | null
}

export type EventMeta = {
  market_id: string
  event_name: string | null
  event_open_date: string | null
  competition_name: string | null
  home_runner_name: string | null
  away_runner_name: string | null
  draw_runner_name: string | null
  home_selection_id?: number | null
  away_selection_id?: number | null
  draw_selection_id?: number | null
  has_raw_stream?: boolean
  has_full_raw_payload?: boolean
  supports_replay_snapshot?: boolean
  last_tick_time?: string | null
  retention_policy?: string | null
  /** Event-aware bucket metadata (from actual tick data). */
  bucket_interval_minutes?: number
  earliest_bucket_start?: string | null
  latest_bucket_start?: string | null
}

/** Response from GET /stream/events/{marketId}/available-buckets. */
export type AvailableBuckets = {
  market_id: string
  bucket_interval_minutes: number
  available_buckets: string[]
  earliest_bucket: string | null
  latest_bucket: string | null
}

/** Replay snapshot: reconstructed from ladder_levels (no raw payload). */
export type ReplaySnapshotSelection = {
  selection_id: string
  best_back_price: number | null
  best_back_size: number | null
  best_lay_price: number | null
  best_lay_size: number | null
}

export type ReplaySnapshot = {
  market_id: string
  snapshot_time: string
  is_reconstructed: boolean
  source: string
  selections: ReplaySnapshotSelection[]
  liquidity: {
    total_matched: number | null
    available_to_back: number | null
    available_to_lay: number | null
  }
}

/** Single row from GET /debug/markets/{market_id}/snapshots (per-snapshot, no raw_payload). */
export type DebugSnapshotRow = {
  snapshot_id: number
  snapshot_at: string | null
  market_id: string
  mbs_total_matched: number | null
  mbs_inplay: boolean | null
  mbs_status: string | null
  mbs_depth_limit: number | null
  mbs_source: string | null
  mbs_capture_version: string | null
  mdm_total_volume: number | null
  home_best_back: number | null
  away_best_back: number | null
  draw_best_back: number | null
  home_best_lay: number | null
  away_best_lay: number | null
  draw_best_lay: number | null
  home_spread: number | null
  away_spread: number | null
  draw_spread: number | null
  mdm_depth_limit: number | null
  mdm_calculation_version: string | null
  calculation_version: string | null
  home_back_size_sum_N?: number | null
  home_back_liability_sum_N?: number | null
  away_back_size_sum_N?: number | null
  away_back_liability_sum_N?: number | null
  draw_back_size_sum_N?: number | null
  draw_back_liability_sum_N?: number | null
  home_roi_N?: number | null
  away_roi_N?: number | null
  draw_roi_N?: number | null
  home_coverage_N?: number | null
  away_coverage_N?: number | null
  draw_coverage_N?: number | null
  home_roi_toxic_N?: number | null
  away_roi_toxic_N?: number | null
  draw_roi_toxic_N?: number | null
  /** L2/L3 back levels (odds and size per outcome). */
  home_back_odds_l2?: number | null
  home_back_size_l2?: number | null
  home_back_odds_l3?: number | null
  home_back_size_l3?: number | null
  away_back_odds_l2?: number | null
  away_back_size_l2?: number | null
  away_back_odds_l3?: number | null
  away_back_size_l3?: number | null
  draw_back_odds_l2?: number | null
  draw_back_size_l2?: number | null
  draw_back_odds_l3?: number | null
  draw_back_size_l3?: number | null
  home_best_back_size_l1?: number | null
  away_best_back_size_l1?: number | null
  draw_best_back_size_l1?: number | null
  total_volume?: number | null
  home_book_risk_l3?: number | null
  away_book_risk_l3?: number | null
  draw_book_risk_l3?: number | null
  event_id?: string | null
  event_name?: string | null
  competition_name?: string | null
  event_open_date?: string | null
  home_runner_name?: string | null
  away_runner_name?: string | null
  draw_runner_name?: string | null
  meta_market_name?: string | null
}

export async function fetchLeagues(
  from: Date,
  to: Date,
  q?: string,
  includeInPlay = false,
  inPlayLookbackHours = 2,
  limit = 100,
  offset = 0
): Promise<LeagueItem[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    include_in_play: String(includeInPlay),
    in_play_lookback_hours: String(inPlayLookbackHours),
    limit: String(limit),
    offset: String(offset),
  })
  if (q?.trim()) params.set('q', q.trim())
  const url = `${getApiBase()}/leagues?${params}`
  console.log('[api] fetchLeagues request', url)
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchLeagues response', { status: res.status, bodyLength: raw.length, bodyPreview: raw.slice(0, 200) })
  if (!res.ok) throw new Error(res.statusText)
  const data = JSON.parse(raw)
  if (!Array.isArray(data)) {
    console.warn('[api] fetchLeagues response is not an array', { type: typeof data, keys: data && typeof data === 'object' ? Object.keys(data) : null })
  }
  return data as LeagueItem[]
}

export async function fetchLeagueEvents(
  league: string,
  from: Date,
  to: Date,
  includeInPlay = false,
  inPlayLookbackHours = 2,
  limit = 100,
  offset = 0
): Promise<EventItem[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    include_in_play: String(includeInPlay),
    in_play_lookback_hours: String(inPlayLookbackHours),
    limit: String(limit),
    offset: String(offset),
  })
  const res = await fetch(
    `${getApiBase()}/leagues/${encodeURIComponent(league)}/events?${params}`
  )
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchEventMeta(marketId: string): Promise<EventMeta> {
  const apiBase = getApiBase()
  const url = `${apiBase}/events/${encodeURIComponent(marketId)}/meta`
  console.log('[api] fetchEventMeta request', { apiBase, marketId, url })
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchEventMeta response', { 
    status: res.status, 
    statusText: res.statusText,
    bodyLength: raw.length, 
    bodyPreview: raw.slice(0, 500) 
  })
  if (!res.ok) {
    console.error('[api] fetchEventMeta error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  let parsed: unknown = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    console.error('[api] fetchEventMeta json parse failed', e)
    throw new Error('Invalid JSON response')
  }
  console.log('[api] fetchEventMeta parsed', { 
    parsedType: typeof parsed,
    hasKeys: typeof parsed === 'object' && parsed !== null ? Object.keys(parsed) : null
  })
  return parsed as EventMeta
}

export async function fetchEventLatestRaw(
  marketId: string
): Promise<{ market_id: string; snapshot_at: string | null; raw_payload: unknown }> {
  const apiBase = getApiBase()
  const url = `${apiBase}/events/${encodeURIComponent(marketId)}/latest_raw`
  console.log('[api] fetchEventLatestRaw request', { apiBase, marketId, url })
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchEventLatestRaw response', { 
    status: res.status, 
    statusText: res.statusText,
    bodyLength: raw.length, 
    bodyPreview: raw.slice(0, 500) 
  })
  if (!res.ok) {
    console.error('[api] fetchEventLatestRaw error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  let parsed: unknown = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    console.error('[api] fetchEventLatestRaw json parse failed', e)
    throw new Error('Invalid JSON response')
  }
  console.log('[api] fetchEventLatestRaw parsed', { 
    parsedType: typeof parsed,
    hasMarketId: typeof parsed === 'object' && parsed !== null && 'market_id' in parsed,
    hasSnapshotAt: typeof parsed === 'object' && parsed !== null && 'snapshot_at' in parsed,
    hasRawPayload: typeof parsed === 'object' && parsed !== null && 'raw_payload' in parsed
  })
  return parsed as { market_id: string; snapshot_at: string | null; raw_payload: unknown }
}

/** Reconstructed snapshot from stream ticks (replay). Use when supports_replay_snapshot is true. */
export async function fetchReplaySnapshot(
  marketId: string,
  atTs?: string | null
): Promise<ReplaySnapshot> {
  const apiBase = getApiBase()
  const params = new URLSearchParams()
  if (atTs) params.set('at_ts', atTs)
  const url = `${apiBase}/events/${encodeURIComponent(marketId)}/replay_snapshot${params.toString() ? `?${params}` : ''}`
  const res = await fetch(url)
  const raw = await res.text()
  if (!res.ok) {
    if (res.status === 404) throw new Error('No tick data available for market.')
    throw new Error(res.statusText)
  }
  return JSON.parse(raw) as ReplaySnapshot
}

export async function fetchEventTimeseries(
  marketId: string,
  from: Date,
  to: Date,
  intervalMinutes = 15
): Promise<TimeseriesPoint[]> {
  const apiBase = getApiBase()
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    interval_minutes: String(intervalMinutes),
  })
  const url = `${apiBase}/events/${encodeURIComponent(marketId)}/timeseries?${params}`
  console.log('[api] fetchEventTimeseries request', { 
    apiBase, 
    marketId, 
    from: from.toISOString(), 
    to: to.toISOString(), 
    intervalMinutes,
    url 
  })
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchEventTimeseries response', { 
    status: res.status, 
    statusText: res.statusText,
    bodyLength: raw.length, 
    bodyPreview: raw.slice(0, 500) 
  })
  if (!res.ok) {
    console.error('[api] fetchEventTimeseries error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  let parsed: unknown = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    console.error('[api] fetchEventTimeseries json parse failed', e)
    throw new Error('Invalid JSON response')
  }
  console.log('[api] fetchEventTimeseries parsed', { 
    parsedType: typeof parsed,
    isArray: Array.isArray(parsed), 
    length: Array.isArray(parsed) ? parsed.length : null,
    firstItemKeys: Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object' && parsed[0] !== null ? Object.keys(parsed[0]) : null
  })
  if (!Array.isArray(parsed)) {
    console.warn('[api] fetchEventTimeseries response is not an array', { type: typeof parsed })
    return []
  }
  return parsed as TimeseriesPoint[]
}

/** All 15-min buckets for a market. Default: last 180 min. Pass from_ts/to_ts for custom range. When eventAware=true, returns only buckets that have tick data for this market (no global time window). */
export async function fetchEventBuckets(
  marketId: string,
  fromTs?: string | null,
  toTs?: string | null,
  eventAware?: boolean
): Promise<BucketItem[]> {
  const apiBase = getApiBase()
  const params = new URLSearchParams()
  if (fromTs) params.set('from_ts', fromTs)
  if (toTs) params.set('to_ts', toTs)
  if (eventAware) params.set('event_aware', 'true')
  const qs = params.toString()
  const url = `${apiBase}/events/${encodeURIComponent(marketId)}/buckets${qs ? `?${qs}` : ''}`
  const res = await fetch(url)
  const raw = await res.text()
  if (!res.ok) {
    console.error('[api] fetchEventBuckets error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  const parsed = JSON.parse(raw)
  if (!Array.isArray(parsed)) return []
  return parsed as BucketItem[]
}

/** Event-aware bucket list: distinct 15-min bucket starts that have ticks for this market. */
export async function fetchAvailableBuckets(marketId: string): Promise<AvailableBuckets> {
  const apiBase = getApiBase()
  const url = `${apiBase}/events/${encodeURIComponent(marketId)}/available-buckets`
  const res = await fetch(url)
  const raw = await res.text()
  if (!res.ok) throw new Error(res.statusText)
  return JSON.parse(raw) as AvailableBuckets
}

/** Book Risk focus: all events in window with latest metrics including Book Risk L3. */
export async function fetchBookRiskFocusEvents(
  from: Date,
  to: Date,
  includeInPlay = false,
  inPlayLookbackHours = 2,
  requireBookRisk = true,
  limit = 500,
  offset = 0
): Promise<EventItem[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    include_in_play: String(includeInPlay),
    in_play_lookback_hours: String(inPlayLookbackHours),
    require_book_risk: String(requireBookRisk),
    limit: String(limit),
    offset: String(offset),
  })
  const res = await fetch(`${getApiBase()}/events/book-risk-focus?${params}`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

/** Streaming data horizon: oldest/newest tick, total_rows, optional days[] for calendar UX. */
export type DataHorizon = {
  oldest_tick: string | null
  newest_tick: string | null
  total_rows: number
  days?: Array<{ day: string; ladder_rows: number; markets: number }>
}

/** Uses getApiBase() so path matches proxy: /api/stream/data-horizon when on stream UI; backend serves /stream/data-horizon (prefix stripped by proxy). */
export async function fetchDataHorizon(): Promise<DataHorizon> {
  const apiBase = getApiBase()
  const url = `${apiBase}/data-horizon`
  const res = await fetch(url)
  const raw = await res.text()
  if (!res.ok) {
    console.error('[api] fetchDataHorizon error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  return JSON.parse(raw) as DataHorizon
}

/** Snapshot-driven calendar: all events for a UTC day that have at least one snapshot. No limit, no Book Risk filter. */
export async function fetchEventsByDateSnapshots(date: string): Promise<EventItem[]> {
  const apiBase = getApiBase()
  const params = new URLSearchParams({ date: date.trim() })
  const url = `${apiBase}/events/by-date-snapshots?${params}`
  console.log('[api] fetchEventsByDateSnapshots request', { apiBase, date: date.trim(), url })
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchEventsByDateSnapshots response', { 
    status: res.status, 
    statusText: res.statusText,
    bodyLength: raw.length, 
    bodyPreview: raw.slice(0, 500) 
  })
  if (!res.ok) {
    console.error('[api] fetchEventsByDateSnapshots error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  let parsed: unknown = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    console.error('[api] fetchEventsByDateSnapshots json parse failed', e)
    throw new Error('Invalid JSON response')
  }
  console.log('[api] fetchEventsByDateSnapshots parsed', { 
    parsedType: typeof parsed,
    isArray: Array.isArray(parsed), 
    length: Array.isArray(parsed) ? parsed.length : null,
    firstItemKeys: Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object' && parsed[0] !== null ? Object.keys(parsed[0]) : null
  })
  if (!Array.isArray(parsed)) {
    console.warn('[api] fetchEventsByDateSnapshots response is not an array', { type: typeof parsed })
    return []
  }
  return parsed as EventItem[]
}

/** Debug: per-snapshot rows for a market (no raw_payload). Lazy-load when market selected. */
export async function fetchMarketSnapshots(
  marketId: string,
  from?: Date,
  to?: Date,
  limit = 200
): Promise<DebugSnapshotRow[]> {
  const apiBase = getApiBase()
  const params = new URLSearchParams({ limit: String(limit) })
  if (from) params.set('from_ts', toISO(from))
  if (to) params.set('to_ts', toISO(to))
  const url = `${apiBase}/debug/markets/${encodeURIComponent(marketId)}/snapshots?${params}`
  console.log('[api] fetchMarketSnapshots request', { 
    apiBase, 
    marketId, 
    from: from?.toISOString(), 
    to: to?.toISOString(), 
    limit,
    url 
  })
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchMarketSnapshots response', { 
    status: res.status, 
    statusText: res.statusText,
    bodyLength: raw.length, 
    bodyPreview: raw.slice(0, 500) 
  })
  if (!res.ok) {
    console.error('[api] fetchMarketSnapshots error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  let parsed: unknown = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    console.error('[api] fetchMarketSnapshots json parse failed', e)
    throw new Error('Invalid JSON response')
  }
  console.log('[api] fetchMarketSnapshots parsed', { 
    parsedType: typeof parsed,
    isArray: Array.isArray(parsed), 
    length: Array.isArray(parsed) ? parsed.length : null,
    firstItemKeys: Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object' && parsed[0] !== null ? Object.keys(parsed[0]) : null
  })
  if (!Array.isArray(parsed)) {
    console.warn('[api] fetchMarketSnapshots response is not an array', { type: typeof parsed })
    return []
  }
  return parsed as DebugSnapshotRow[]
}

/** Debug: raw_payload for one snapshot (on row click). */
export async function fetchSnapshotRaw(
  snapshotId: number
): Promise<{ snapshot_id: number; snapshot_at: string | null; market_id: string; raw_payload: unknown; truncated?: boolean; raw_payload_size_bytes?: number }> {
  const res = await fetch(`${getApiBase()}/debug/snapshots/${snapshotId}/raw`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

/** Fetch raw ticks for a market within a time range (for audit view). */
export async function fetchMarketTicks(
  marketId: string,
  from: Date,
  to: Date,
  limit = 2000
): Promise<TickRow[]> {
  const apiBase = getApiBase()
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    limit: String(limit),
  })
  const url = `${apiBase}/markets/${encodeURIComponent(marketId)}/ticks?${params}`
  console.log('[api] fetchMarketTicks request', { 
    apiBase, 
    marketId, 
    from: from.toISOString(), 
    to: to.toISOString(), 
    limit,
    url 
  })
  const res = await fetch(url)
  const raw = await res.text()
  console.log('[api] fetchMarketTicks response', { 
    status: res.status, 
    statusText: res.statusText,
    bodyLength: raw.length, 
    bodyPreview: raw.slice(0, 500) 
  })
  if (!res.ok) {
    console.error('[api] fetchMarketTicks error', { status: res.status, statusText: res.statusText, body: raw })
    throw new Error(res.statusText)
  }
  let parsed: unknown = null
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    console.error('[api] fetchMarketTicks json parse failed', e)
    throw new Error('Invalid JSON response')
  }
  console.log('[api] fetchMarketTicks parsed', { 
    parsedType: typeof parsed,
    isArray: Array.isArray(parsed), 
    length: Array.isArray(parsed) ? parsed.length : null,
  })
  if (!Array.isArray(parsed)) {
    console.warn('[api] fetchMarketTicks response is not an array', { type: typeof parsed })
    return []
  }
  return parsed as TickRow[]
}
