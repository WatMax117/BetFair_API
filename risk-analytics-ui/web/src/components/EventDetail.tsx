import { useState, useEffect, useCallback, useMemo } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import ToggleButton from '@mui/material/ToggleButton'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import Tooltip from '@mui/material/Tooltip'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CodeIcon from '@mui/icons-material/Code'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { fetchEventMeta, fetchEventTimeseries, fetchEventLatestRaw, fetchReplaySnapshot, fetchMarketTicks, getApiBase } from '../api'
import type { EventMeta, TimeseriesPoint, TickRow } from '../api'

const TIME_RANGES = [
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '72h', hours: 72 },
] as const

const ODDS_EXTREME_THRESHOLD = 1000

/** Format ISO timestamp: UTC or local with timezone label. */
function formatTime(iso: string | null, useUtc: boolean): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (useUtc) {
      return d.toLocaleString('en-GB', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' }) + ' UTC'
    }
    return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) + ' (local)'
  } catch {
    return iso
  }
}

/** Format number; "—" for null. For risk/impedance always use "—" for null, never 0. */
function num(v: number | null | undefined): string {
  if (v == null) return '—'
  return Number.isInteger(v) ? String(v) : v.toFixed(2)
}

/** Odds display: "—" if null or ≤1; "≥1000" if ≥threshold with extreme flag; else numeric. */
function formatOdds(odds: number | null | undefined, opts?: { extremeThreshold?: number }): { text: string; extreme?: boolean } {
  const max = opts?.extremeThreshold ?? ODDS_EXTREME_THRESHOLD
  if (odds == null || odds <= 1.0) return { text: '—' }
  if (odds >= max) return { text: `≥${max}`, extreme: true }
  return { text: Number.isInteger(odds) ? String(odds) : odds.toFixed(2) }
}

function spread(back: number | null, lay: number | null): number | null {
  if (back != null && lay != null) return lay - back
  return null
}


export function EventDetail({
  marketId,
  eventName: _eventName,
  competitionName: _competitionName,
  eventOpenDate: _eventOpenDate,
  selectedDate,
  onBack,
}: {
  marketId: string
  eventName: string | null
  competitionName: string | null
  eventOpenDate: string | null
  selectedDate?: string | null
  onBack: () => void
}) {
  const [meta, setMeta] = useState<EventMeta | null>(null)
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([])
  const [ticks, setTicks] = useState<TickRow[]>([])
  const [loadingMeta, setLoadingMeta] = useState(true)
  const [loadingTs, setLoadingTs] = useState(true)
  const [loadingTicks, setLoadingTicks] = useState(false)
  const [timeRangeHours, setTimeRangeHours] = useState(24)
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null)
  const [rawModalOpen, setRawModalOpen] = useState(false)
  const [rawPayload, setRawPayload] = useState<unknown>(null)
  const [rawLoading, setRawLoading] = useState(false)
  const [isReplayView, setIsReplayView] = useState(false)
  const [useUtc, setUseUtc] = useState(true)
  const [apiDebugOpen, setApiDebugOpen] = useState(false)
  const [lastRequestInfo, setLastRequestInfo] = useState<{ timeseries?: { from_ts: string; to_ts: string }; ticks?: { from_ts: string; to_ts: string } }>({})

  // Use selectedDate to determine time window, fallback to rolling 24h if not available
  const { from, to } = useMemo(() => {
    if (selectedDate) {
      // Use selected date's UTC day range: 00:00:00Z to 23:59:59Z (or now if today)
      const dayStart = new Date(`${selectedDate}T00:00:00.000Z`)
      const dayEnd = new Date(`${selectedDate}T23:59:59.999Z`)
      const now = new Date()
      const effectiveTo = dayEnd > now ? now : dayEnd
      console.log('[EventDetail] Using selected date range', { selectedDate, from: dayStart.toISOString(), to: effectiveTo.toISOString() })
      return { from: dayStart, to: effectiveTo }
    } else {
      // Fallback to rolling 24h window
      const fromDate = new Date(Date.now() - timeRangeHours * 60 * 60 * 1000)
      const toDate = new Date()
      console.log('[EventDetail] Using rolling time range', { timeRangeHours, from: fromDate.toISOString(), to: toDate.toISOString() })
      return { from: fromDate, to: toDate }
    }
  }, [selectedDate, timeRangeHours])

  useEffect(() => {
    console.log('[EventDetail] Loading meta for marketId', { marketId })
    setLoadingMeta(true)
    fetchEventMeta(marketId)
      .then((meta: EventMeta) => {
        console.log('[EventDetail] Meta received', { meta })
        setMeta(meta)
      })
      .catch((e: unknown) => {
        console.error('[EventDetail] Meta load error', e)
        setMeta(null)
      })
      .finally(() => setLoadingMeta(false))
  }, [marketId])

  const loadTimeseries = useCallback(() => {
    const from_ts = from.toISOString()
    const to_ts = to.toISOString()
    setLastRequestInfo((prev) => ({ ...prev, timeseries: { from_ts, to_ts } }))
    setLoadingTs(true)
    fetchEventTimeseries(marketId, from, to, 15)
      .then((data: TimeseriesPoint[]) => {
        setTimeseries(data)
      })
      .catch((e: unknown) => {
        console.error('[EventDetail] Timeseries load error', e)
        setTimeseries([])
      })
      .finally(() => setLoadingTs(false))
  }, [marketId, from, to])

  useEffect(() => {
    loadTimeseries()
  }, [loadTimeseries])

  // Load ticks for selected bucket
  const loadTicks = useCallback(() => {
    if (!selectedBucket) {
      setTicks([])
      return
    }
    
    const bucketStart = new Date(selectedBucket)
    const bucketEnd = new Date(bucketStart.getTime() + 15 * 60 * 1000) // +15 minutes
    
    console.log('[EventDetail] Loading ticks', { 
      marketId, 
      bucketStart: bucketStart.toISOString(), 
      bucketEnd: bucketEnd.toISOString() 
    })
    setLastRequestInfo((prev) => ({ ...prev, ticks: { from_ts: bucketStart.toISOString(), to_ts: bucketEnd.toISOString() } }))
    setLoadingTicks(true)
    fetchMarketTicks(marketId, bucketStart, bucketEnd, 2000)
      .then((data: TickRow[]) => {
        setTicks(data)
      })
      .catch((e: unknown) => {
        console.error('[EventDetail] Ticks load error', e)
        setTicks([])
      })
      .finally(() => setLoadingTicks(false))
  }, [marketId, selectedBucket])

  useEffect(() => {
    loadTicks()
  }, [loadTicks])
  
  // Auto-select latest bucket when timeseries loads
  useEffect(() => {
    if (timeseries.length > 0 && !selectedBucket) {
      const latest = timeseries[timeseries.length - 1]
      if (latest.snapshot_at) {
        setSelectedBucket(latest.snapshot_at)
      }
    }
  }, [timeseries, selectedBucket])

  const chartData = timeseries.map((p) => ({
    time: p.snapshot_at
      ? (useUtc
          ? new Date(p.snapshot_at).toLocaleTimeString('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' })
          : new Date(p.snapshot_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
      : '',
    fullTime: p.snapshot_at,
    home_back: p.home_best_back ?? null,
    away_back: p.away_best_back ?? null,
    draw_back: p.draw_best_back ?? null,
    total_volume: p.total_volume ?? null,
    home_book_risk_l3: p.home_book_risk_l3 ?? null,
    away_book_risk_l3: p.away_book_risk_l3 ?? null,
    draw_book_risk_l3: p.draw_book_risk_l3 ?? null,
  }))
  const hasBookRiskL3 = timeseries.some((p) => p.home_book_risk_l3 != null || p.away_book_risk_l3 != null || p.draw_book_risk_l3 != null)

  // Find selected bucket data
  const selectedBucketData = selectedBucket 
    ? timeseries.find(p => p.snapshot_at === selectedBucket) 
    : null
  
  const homeSpread = selectedBucketData ? spread(selectedBucketData.home_best_back, selectedBucketData.home_best_lay) : null
  const awaySpread = selectedBucketData ? spread(selectedBucketData.away_best_back, selectedBucketData.away_best_lay) : null
  const drawSpread = selectedBucketData ? spread(selectedBucketData.draw_best_back, selectedBucketData.draw_best_lay) : null
  
  const formatBucketTime = (iso: string | null): string => {
    if (!iso) return '—'
    return formatTime(iso, useUtc)
  }

  // Selection IDs from backend meta; show banner if missing or duplicated
  const selectionIdsOk = useMemo(() => {
    if (!meta) return true
    const h = meta.home_selection_id
    const a = meta.away_selection_id
    const d = meta.draw_selection_id
    const ids = [h, a, d].filter((x): x is number => x != null)
    if (ids.length === 0) return false
    const set = new Set(ids)
    return set.size === ids.length
  }, [meta])

  const handleCopyMarketId = () => {
    navigator.clipboard.writeText(marketId)
  }
  const useReplaySnapshot = Boolean(meta && meta.has_full_raw_payload === false && meta.supports_replay_snapshot === true)

  const handleViewRaw = () => {
    setRawModalOpen(true)
    setRawLoading(true)
    setRawPayload(null)
    if (useReplaySnapshot) {
      setIsReplayView(true)
      fetchReplaySnapshot(marketId)
        .then((r) => setRawPayload(r))
        .catch(() => setRawPayload(null))
        .finally(() => setRawLoading(false))
    } else {
      setIsReplayView(false)
      fetchEventLatestRaw(marketId)
        .then((r: { raw_payload: unknown }) => setRawPayload(r.raw_payload))
        .catch(() => setRawPayload(null))
        .finally(() => setRawLoading(false))
    }
  }
  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2 }}>
        Back to leagues
      </Button>

      {loadingMeta ? (
        <Typography color="text.secondary">Loading event…</Typography>
      ) : meta ? (
        <>
          {!selectionIdsOk && (
            <Paper sx={{ p: 1.5, mb: 2, bgcolor: 'error.light', color: 'error.contrastText' }}>
              <Typography variant="body2">
                Selection IDs missing or duplicated (H/A/D). Check backend meta. Risk and ticks may be misaligned.
              </Typography>
            </Paper>
          )}
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6">{meta.event_name || marketId}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <Typography color="text.secondary">
                {meta.competition_name} · Start: {formatTime(meta.event_open_date, useUtc)}
              </Typography>
              <ToggleButtonGroup value={useUtc ? 'utc' : 'local'} exclusive size="small" onChange={(_, v) => v != null && setUseUtc(v === 'utc')}>
                <ToggleButton value="utc">UTC</ToggleButton>
                <ToggleButton value="local">Local</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              market_id: {marketId}
            </Typography>
            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <Button size="small" startIcon={<ContentCopyIcon />} onClick={handleCopyMarketId}>
                Copy market_id
              </Button>
              <Button size="small" startIcon={<CodeIcon />} onClick={handleViewRaw}>
                {useReplaySnapshot ? 'View reconstructed snapshot' : 'View latest raw snapshot (JSON)'}
              </Button>
            </Box>
            {selectedBucketData && (
              <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Best back</Typography>
                  <Typography>
                    {(['H', 'A', 'D'] as const).map((label, i) => {
                      const odds = [selectedBucketData.home_best_back, selectedBucketData.away_best_back, selectedBucketData.draw_best_back][i]
                      const { text, extreme } = formatOdds(odds)
                      const content = extreme ? <Typography component="span" sx={{ color: 'warning.main' }}>{text}</Typography> : text
                      return (
                        <Tooltip key={label} title={extreme ? 'Extreme odds (stale/unmatched?)' : ''}>
                          <span>{label} {content}{i < 2 ? ' / ' : ''}</span>
                        </Tooltip>
                      )
                    })}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Best lay</Typography>
                  <Typography>
                    H {formatOdds(selectedBucketData.home_best_lay).text} / A {formatOdds(selectedBucketData.away_best_lay).text} / D {formatOdds(selectedBucketData.draw_best_lay).text}
                  </Typography>
                </Box>
                <Tooltip title="Spread = best lay − best back (per selection)">
                  <Box>
                    <Typography variant="caption" color="text.secondary">Spreads (lay − back)</Typography>
                    <Typography>H {num(homeSpread)} / A {num(awaySpread)} / D {num(drawSpread)}</Typography>
                  </Box>
                </Tooltip>
                <Box>
                  <Typography variant="caption" color="text.secondary">Total volume</Typography>
                  <Typography>{num(selectedBucketData.total_volume)}</Typography>
                </Box>
              </Box>
            )}
          </Paper>

          <Dialog open={rawModalOpen} onClose={() => setRawModalOpen(false)} maxWidth="md" fullWidth>
            <DialogTitle>{isReplayView ? 'Reconstructed snapshot' : 'Latest raw snapshot'} — {marketId}</DialogTitle>
            <DialogContent>
              {rawLoading ? (
                <Typography color="text.secondary">Loading…</Typography>
              ) : rawPayload != null ? (
                <>
                  {isReplayView && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Reconstructed from stored ladder ticks. Full raw payload is not retained.
                    </Typography>
                  )}
                  <Box component="pre" sx={{ overflow: 'auto', fontSize: '0.75rem', p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
                    {JSON.stringify(rawPayload, null, 2)}
                  </Box>
                </>
              ) : (
                <>
                  <Typography color="text.secondary">
                    {isReplayView ? 'No tick data available for market.' : 'No raw snapshot available for this source.'}
                  </Typography>
                  {!isReplayView && meta?.has_raw_stream === false && (
                    <Typography variant="body2" sx={{ mt: 1 }} color="text.secondary">
                      Stream source does not store full raw payloads; tick data is retained per retention policy. This is not data loss.
                      {meta.retention_policy && ` ${meta.retention_policy}`}
                    </Typography>
                  )}
                </>
              )}
            </DialogContent>
          </Dialog>

          <Typography variant="subtitle1" sx={{ mb: 1 }}>History (15‑min snapshots)</Typography>
          <ToggleButtonGroup
            value={timeRangeHours}
            exclusive
            onChange={(_, v) => v != null && setTimeRangeHours(v)}
            size="small"
            sx={{ mb: 2 }}
          >
            {TIME_RANGES.map(({ label, hours }) => (
              <ToggleButton key={hours} value={hours}>
                {label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>

          {loadingTs ? (
            <Typography color="text.secondary">Loading time series…</Typography>
          ) : (
            <>
              {/* Chart 1: Risk (Book Risk L3) */}
              {hasBookRiskL3 && (
                <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>Risk (Book Risk L3 H/A/D)</Typography>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <RechartsTooltip />
                      <Legend />
                      <Line type="monotone" dataKey="home_book_risk_l3" name="Home" stroke="#1976d2" dot={false} />
                      <Line type="monotone" dataKey="away_book_risk_l3" name="Away" stroke="#9c27b0" dot={false} />
                      <Line type="monotone" dataKey="draw_book_risk_l3" name="Draw" stroke="#2e7d32" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </Paper>
              )}

              {/* Bucket Selection */}
              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Select 15-minute bucket</Typography>
              <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {timeseries.map((point) => (
                  <Button
                    key={point.snapshot_at || Math.random()}
                    variant={selectedBucket === point.snapshot_at ? 'contained' : 'outlined'}
                    size="small"
                    onClick={() => setSelectedBucket(point.snapshot_at || null)}
                    sx={{ minWidth: 'auto' }}
                  >
                    {point.snapshot_at
                      ? (useUtc
                          ? new Date(point.snapshot_at).toLocaleTimeString('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' })
                          : new Date(point.snapshot_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
                      : '—'}
                  </Button>
                ))}
              </Box>

              {/* 15-Minute Median Matrix */}
              {selectedBucketData && (
                <>
                  <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                    15-Minute Bucket Medians — {formatBucketTime(selectedBucket)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                    Book Risk and Impedance: computed from medians only.
                  </Typography>
                  <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Outcome</TableCell>
                          <TableCell align="right">Median Back Odds (15m)</TableCell>
                          <TableCell align="right">Median Back Size (15m)</TableCell>
                          <TableCell align="right">Coverage (s / #ticks)</TableCell>
                          <TableCell align="right">Book Risk (15m)</TableCell>
                          <TableCell align="right">Impedance Index (15m)</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        <TableRow>
                          <TableCell><strong>H</strong></TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_back_odds_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_back_size_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_seconds_covered)}s / {selectedBucketData.home_update_count ?? 0}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_book_risk_l3 ?? null)}</TableCell>
                          <TableCell align="right" rowSpan={4}>{num(selectedBucketData.impedance_index_15m ?? null)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell><strong>A</strong></TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_back_odds_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_back_size_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_seconds_covered)}s / {selectedBucketData.away_update_count ?? 0}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_book_risk_l3 ?? null)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell><strong>D</strong></TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_back_odds_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_back_size_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_seconds_covered)}s / {selectedBucketData.draw_update_count ?? 0}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_book_risk_l3 ?? null)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell colSpan={4} variant="footer" sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                            |s−w| H: {num(selectedBucketData.impedance_abs_diff_home ?? null)} A: {num(selectedBucketData.impedance_abs_diff_away ?? null)} D: {num(selectedBucketData.impedance_abs_diff_draw ?? null)}
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </TableContainer>
                </>
              )}

              {/* Tick Audit View */}
              {selectedBucket && (
                <>
                  <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                    Tick Audit View — {formatBucketTime(selectedBucket)}
                  </Typography>
                  {(() => {
                    const bucketStart = new Date(selectedBucket)
                    const bucketEnd = new Date(bucketStart.getTime() + 15 * 60 * 1000)
                    const firstTick = ticks.length > 0 ? ticks[0]?.publish_time : null
                    const lastTick = ticks.length > 0 ? ticks[ticks.length - 1]?.publish_time : null
                    const mediansNonNull = selectedBucketData && (
                      selectedBucketData.home_back_odds_median != null || selectedBucketData.away_back_odds_median != null || selectedBucketData.draw_back_odds_median != null
                    )
                    const carryForwardWarning = ticks.length === 0 && mediansNonNull
                    return (
                      <>
                        <Box sx={{ mb: 1, fontSize: '0.8rem', color: 'text.secondary' }}>
                          bucket_start: {formatTime(selectedBucket, useUtc)} · bucket_end: {formatTime(bucketEnd.toISOString(), useUtc)} · tick_count: {ticks.length}
                          {firstTick != null && <> · first_tick: {formatTime(firstTick, useUtc)}</>}
                          {lastTick != null && <> · last_tick: {formatTime(lastTick, useUtc)}</>}
                        </Box>
                        {carryForwardWarning && (
                          <Typography variant="body2" color="warning.main" sx={{ mb: 1 }}>
                            tick_count is 0 but medians are non-null — bucket is driven by carry-forward baseline.
                          </Typography>
                        )}
                      </>
                    )
                  })()}
                  {loadingTicks ? (
                    <Typography color="text.secondary" sx={{ mb: 2 }}>Loading ticks…</Typography>
                  ) : (
                    <TableContainer component={Paper} variant="outlined" sx={{ mb: 2, userSelect: 'text', maxHeight: 400, overflow: 'auto' }}>
                      <Table size="small" stickyHeader>
                        <TableHead>
                          <TableRow>
                            <TableCell>publish_time</TableCell>
                            <TableCell align="right">H Back Odds</TableCell>
                            <TableCell align="right">H Back Size</TableCell>
                            <TableCell align="right">A Back Odds</TableCell>
                            <TableCell align="right">A Back Size</TableCell>
                            <TableCell align="right">D Back Odds</TableCell>
                            <TableCell align="right">D Back Size</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {ticks.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={7} align="center">
                                <Typography color="text.secondary">No ticks found in this bucket</Typography>
                              </TableCell>
                            </TableRow>
                          ) : (
                            ticks.map((tick, i) => (
                              <TableRow key={i}>
                                <TableCell>{tick.publish_time ? formatTime(tick.publish_time, useUtc) : '—'}</TableCell>
                                <TableCell align="right">{formatOdds(tick.home_back_odds).text}</TableCell>
                                <TableCell align="right">{num(tick.home_back_size ?? null)}</TableCell>
                                <TableCell align="right">{formatOdds(tick.away_back_odds).text}</TableCell>
                                <TableCell align="right">{num(tick.away_back_size ?? null)}</TableCell>
                                <TableCell align="right">{formatOdds(tick.draw_back_odds).text}</TableCell>
                                <TableCell align="right">{num(tick.draw_back_size ?? null)}</TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </>
              )}

            </>
          )}

          <Box sx={{ mt: 2 }}>
            <Button size="small" onClick={() => setApiDebugOpen((o) => !o)} sx={{ mb: 0.5 }}>
              {apiDebugOpen ? 'Hide' : 'Show'} API debug
            </Button>
            {apiDebugOpen && (
              <Paper variant="outlined" sx={{ p: 1.5, mb: 2, fontFamily: 'monospace', fontSize: '0.75rem' }}>
                <Typography variant="caption" color="text.secondary" display="block">API base</Typography>
                <Typography component="code">{getApiBase()}</Typography>
                {lastRequestInfo.timeseries && (
                  <>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>Timeseries</Typography>
                    <Typography component="code">GET {getApiBase()}/events/{marketId}/timeseries?from_ts={lastRequestInfo.timeseries.from_ts}&to_ts={lastRequestInfo.timeseries.to_ts}&interval_minutes=15</Typography>
                  </>
                )}
                {lastRequestInfo.ticks && (
                  <>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>Ticks</Typography>
                    <Typography component="code">GET {getApiBase()}/markets/{marketId}/ticks?from_ts={lastRequestInfo.ticks.from_ts}&to_ts={lastRequestInfo.ticks.to_ts}</Typography>
                  </>
                )}
              </Paper>
            )}
          </Box>

          <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Typography variant="caption" color="text.secondary" display="block">Data notes</Typography>
            <Typography variant="body2">
              Bucket interval: 15 minutes UTC. Medians are time-weighted over the bucket duration using carry-forward logic.
              Tick audit view shows all raw ticks (level=0, side='B') within the selected bucket.
            </Typography>
            {meta?.has_raw_stream === false && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                Stream source: full raw snapshots are not stored; tick data is retained per retention policy. “No raw snapshot” here is not data loss.
              </Typography>
            )}
            {selectedBucketData && timeseries.length > 0 && (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                Selected bucket: {formatBucketTime(selectedBucket)}.
                {selectedBucketData.depth_limit != null && ` depth_limit: ${selectedBucketData.depth_limit}.`}
                {selectedBucketData.calculation_version && ` calculation_version: ${selectedBucketData.calculation_version}.`}
              </Typography>
            )}
          </Paper>
        </>
      ) : (
        <Typography color="error">Event not found.</Typography>
      )}
    </Box>
  )
}
