// Base path for API (e.g. /api). No trailing slash. Requests go to ${API_BASE}/leagues etc.
const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

function toISO(d: Date): string {
  return d.toISOString()
}

export type LeagueItem = { league: string; event_count: number }

/** H/A/D triplet for Imbalance (risk) or Impedance. Same ordering: home, away, draw. */
export type HadTriplet = { home: number | null; away: number | null; draw: number | null }

/** Raw inputs per outcome for Impedance: backStake, backOdds, backProfit (backer profit if back wins), layStake, layOdds, layLiability (layer exposure if selection wins). */
export type ImpedanceInputsOutcome = {
  backStake: number | null
  backOdds: number | null
  /** Backer's potential profit if back wins = (backOdds - 1) * backStake. */
  backProfit: number | null
  layStake: number | null
  layOdds: number | null
  /** Layer's maximum loss / exposure if selection wins = (layOdds - 1) * layStake. */
  layLiability: number | null
}
export type ImpedanceInputs = { home: ImpedanceInputsOutcome; away: ImpedanceInputsOutcome; draw: ImpedanceInputsOutcome }

export type EventItem = {
  market_id: string
  event_name: string
  event_open_date: string | null
  competition_name: string | null
  latest_snapshot_at: string | null
  home_risk: number | null
  away_risk: number | null
  draw_risk: number | null
  home_best_back: number | null
  away_best_back: number | null
  draw_best_back: number | null
  home_best_lay: number | null
  away_best_lay: number | null
  draw_best_lay: number | null
  total_volume: number | null
  depth_limit: number | null
  calculation_version: string | null
  /** Imbalance index (H/A/D) as a distinct object; same values as home_risk/away_risk/draw_risk. */
  imbalance?: HadTriplet
  /** Present when includeImpedance=true. Raw impedance per H/A/D (debug). */
  impedance?: HadTriplet
  /** Present when includeImpedance=true. Normalized impedance (prefer for UI). */
  impedanceNorm?: HadTriplet
  /** Present when includeImpedance=true and include_impedance_inputs=true. Raw inputs per outcome for auditing. */
  impedanceInputs?: ImpedanceInputs
  /** Book Risk L3 (H/A/D) from latest snapshot. Present in book-risk-focus endpoint. */
  home_book_risk_l3?: number | null
  away_book_risk_l3?: number | null
  draw_book_risk_l3?: number | null
}

export type TimeseriesPoint = {
  snapshot_at: string | null
  home_best_back: number | null
  away_best_back: number | null
  draw_best_back: number | null
  home_best_lay: number | null
  away_best_lay: number | null
  draw_best_lay: number | null
  home_risk: number | null
  away_risk: number | null
  draw_risk: number | null
  total_volume: number | null
  depth_limit?: number | null
  calculation_version?: string | null
  /** Imbalance index (H/A/D) as distinct object; same as home_risk/away_risk/draw_risk. */
  imbalance?: HadTriplet
  impedance?: HadTriplet
  impedanceNorm?: HadTriplet
  /** Raw inputs per outcome when include_impedance_inputs=true. */
  impedanceInputs?: ImpedanceInputs
  /** Best-level (L1) sizes: back and lay, for backSize/laySize columns and Size Impedance L1. */
  home_best_back_size_l1?: number | null
  away_best_back_size_l1?: number | null
  draw_best_back_size_l1?: number | null
  home_best_lay_size_l1?: number | null
  away_best_lay_size_l1?: number | null
  draw_best_lay_size_l1?: number | null
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
  /** 3-way Book Risk (exposure) at 3 levels: R[o]=W[o]-L[o]. >0 = book loses if outcome wins. */
  home_book_risk_l3?: number | null
  away_book_risk_l3?: number | null
  draw_book_risk_l3?: number | null
}

export type EventMeta = {
  market_id: string
  event_name: string | null
  event_open_date: string | null
  competition_name: string | null
  home_runner_name: string | null
  away_runner_name: string | null
  draw_runner_name: string | null
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
  home_risk: number | null
  away_risk: number | null
  draw_risk: number | null
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
  home_impedance?: number | null
  away_impedance?: number | null
  draw_impedance?: number | null
  /** Timeseries uses impedance object; Debug uses flat home_impedance etc. */
  impedance?: HadTriplet | null
  /** Timeseries uses total_volume; Debug uses mdm_total_volume. */
  total_volume?: number | null
  home_impedance_norm?: number | null
  away_impedance_norm?: number | null
  draw_impedance_norm?: number | null
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
  includeInPlay = true,
  inPlayLookbackHours = 6,
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
  const url = `${API_BASE}/leagues?${params}`
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
  includeInPlay = true,
  inPlayLookbackHours = 6,
  includeImpedance = false,
  limit = 100,
  offset = 0
): Promise<EventItem[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    include_in_play: String(includeInPlay),
    in_play_lookback_hours: String(inPlayLookbackHours),
    include_impedance: String(includeImpedance),
    limit: String(limit),
    offset: String(offset),
  })
  const res = await fetch(
    `${API_BASE}/leagues/${encodeURIComponent(league)}/events?${params}`
  )
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchEventMeta(marketId: string): Promise<EventMeta> {
  const res = await fetch(`${API_BASE}/events/${encodeURIComponent(marketId)}/meta`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchEventLatestRaw(
  marketId: string
): Promise<{ market_id: string; snapshot_at: string | null; raw_payload: unknown }> {
  const res = await fetch(`${API_BASE}/events/${encodeURIComponent(marketId)}/latest_raw`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchEventTimeseries(
  marketId: string,
  from: Date,
  to: Date,
  intervalMinutes = 15,
  includeImpedance = false
): Promise<TimeseriesPoint[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    interval_minutes: String(intervalMinutes),
    include_impedance: String(includeImpedance),
    include_impedance_inputs: String(includeImpedance), // Always include inputs when impedance is requested
  })
  const res = await fetch(
    `${API_BASE}/events/${encodeURIComponent(marketId)}/timeseries?${params}`
  )
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

/** Book Risk focus: all events in window with latest metrics including Book Risk L3. */
export async function fetchBookRiskFocusEvents(
  from: Date,
  to: Date,
  includeInPlay = true,
  inPlayLookbackHours = 6,
  includeImpedance = true,
  requireBookRisk = true,
  limit = 500,
  offset = 0
): Promise<EventItem[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    include_in_play: String(includeInPlay),
    in_play_lookback_hours: String(inPlayLookbackHours),
    include_impedance: String(includeImpedance),
    require_book_risk: String(requireBookRisk),
    limit: String(limit),
    offset: String(offset),
  })
  const res = await fetch(`${API_BASE}/events/book-risk-focus?${params}`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

/** Debug: per-snapshot rows for a market (no raw_payload). Lazy-load when market selected. */
export async function fetchMarketSnapshots(
  marketId: string,
  from?: Date,
  to?: Date,
  limit = 200
): Promise<DebugSnapshotRow[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (from) params.set('from_ts', toISO(from))
  if (to) params.set('to_ts', toISO(to))
  const res = await fetch(
    `${API_BASE}/debug/markets/${encodeURIComponent(marketId)}/snapshots?${params}`
  )
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

/** Debug: raw_payload for one snapshot (on row click). */
export async function fetchSnapshotRaw(
  snapshotId: number
): Promise<{ snapshot_id: number; snapshot_at: string | null; market_id: string; raw_payload: unknown; truncated?: boolean; raw_payload_size_bytes?: number }> {
  const res = await fetch(`${API_BASE}/debug/snapshots/${snapshotId}/raw`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}
