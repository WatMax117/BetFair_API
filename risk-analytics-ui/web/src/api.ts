// Base path for API (e.g. /api). No trailing slash. Requests go to ${API_BASE}/leagues etc.
const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

function toISO(d: Date): string {
  return d.toISOString()
}

export type LeagueItem = { league: string; event_count: number }

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
  const res = await fetch(`${API_BASE}/leagues?${params}`)
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchLeagueEvents(
  league: string,
  from: Date,
  to: Date,
  includeInPlay = true,
  inPlayLookbackHours = 6,
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
  intervalMinutes = 15
): Promise<TimeseriesPoint[]> {
  const params = new URLSearchParams({
    from_ts: toISO(from),
    to_ts: toISO(to),
    interval_minutes: String(intervalMinutes),
  })
  const res = await fetch(
    `${API_BASE}/events/${encodeURIComponent(marketId)}/timeseries?${params}`
  )
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}
