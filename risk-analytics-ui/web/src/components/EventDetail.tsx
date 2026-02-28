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
import { fetchEventMeta, fetchEventBuckets, fetchEventLatestRaw, fetchReplaySnapshot, fetchMarketTicks, getApiBase } from '../api'
import type { EventMeta, BucketItem, TickRow } from '../api'

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
  selectedDate: _selectedDate,
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
  const [buckets, setBuckets] = useState<BucketItem[]>([])
  const [ticks, setTicks] = useState<TickRow[]>([])
  const [loadingMeta, setLoadingMeta] = useState(true)
  const [loadingBuckets, setLoadingBuckets] = useState(true)
  const [loadingTicks, setLoadingTicks] = useState(false)
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null)
  const [rawModalOpen, setRawModalOpen] = useState(false)
  const [rawPayload, setRawPayload] = useState<unknown>(null)
  const [rawLoading, setRawLoading] = useState(false)
  const [isReplayView, setIsReplayView] = useState(false)
  const [useUtc, setUseUtc] = useState(true)
  const [apiDebugOpen, setApiDebugOpen] = useState(false)
  const [lastRequestInfo, setLastRequestInfo] = useState<{ buckets?: string; ticks?: { from_ts: string; to_ts: string } }>({})
  const [bucketListVisible, setBucketListVisible] = useState(50)

  // Reset state when marketId changes so we never show stale data from a previous event
  useEffect(() => {
    setMeta(null)
    setBuckets([])
    setSelectedBucket(null)
    setTicks([])
  }, [marketId])

  useEffect(() => {
    console.log('[EventDetail] fetch meta request', { marketId })
    setLoadingMeta(true)
    fetchEventMeta(marketId)
      .then((meta: EventMeta) => {
        console.log('[EventDetail] fetch meta response', { marketId, status: 'ok', eventName: meta.event_name })
        setMeta(meta)
      })
      .catch((e: unknown) => {
        console.error('[EventDetail] fetch meta error', { marketId, error: e })
        setMeta(null)
      })
      .finally(() => setLoadingMeta(false))
  }, [marketId])

  const loadBuckets = useCallback(() => {
    const apiBase = getApiBase()
    const bucketsUrl = `${apiBase}/events/${encodeURIComponent(marketId)}/buckets?event_aware=true`
    setLastRequestInfo((prev) => ({ ...prev, buckets: bucketsUrl }))
    console.log('[EventDetail] fetch buckets request', { marketId })
    setLoadingBuckets(true)
    fetchEventBuckets(marketId, undefined, undefined, true)
      .then((data: BucketItem[]) => {
        console.log('[EventDetail] fetch buckets response', { marketId, status: 'ok', count: data.length })
        setBuckets(data)
      })
      .catch((e: unknown) => {
        console.error('[EventDetail] fetch buckets error', { marketId, error: e })
        setBuckets([])
      })
      .finally(() => setLoadingBuckets(false))
  }, [marketId])

  useEffect(() => {
    loadBuckets()
  }, [loadBuckets])

  // Load ticks for selected bucket
  const loadTicks = useCallback(() => {
    if (!selectedBucket) {
      setTicks([])
      return
    }
    
    const bucketStart = new Date(selectedBucket)
    const bucketEnd = new Date(bucketStart.getTime() + 15 * 60 * 1000) // +15 minutes
    
    console.log('[EventDetail] fetch ticks request', { marketId, bucketStart: bucketStart.toISOString() })
    setLastRequestInfo((prev) => ({ ...prev, ticks: { from_ts: bucketStart.toISOString(), to_ts: bucketEnd.toISOString() } }))
    setLoadingTicks(true)
    fetchMarketTicks(marketId, bucketStart, bucketEnd, 2000)
      .then((data: TickRow[]) => {
        console.log('[EventDetail] fetch ticks response', { marketId, status: 'ok', count: data.length })
        setTicks(data)
      })
      .catch((e: unknown) => {
        console.error('[EventDetail] fetch ticks error', { marketId, error: e })
        setTicks([])
      })
      .finally(() => setLoadingTicks(false))
  }, [marketId, selectedBucket])

  useEffect(() => {
    loadTicks()
  }, [loadTicks])
  
  // Auto-select latest bucket when buckets load (buckets are oldest first; latest = last)
  useEffect(() => {
    if (buckets.length > 0 && !selectedBucket) {
      const latest = buckets[buckets.length - 1]
      if (latest.bucket_start) {
        setSelectedBucket(latest.bucket_start)
      }
    }
  }, [buckets, selectedBucket])

  const volumeValues = buckets.map((p) => p.total_volume ?? 0).filter((v) => v > 0)
  const volMin = volumeValues.length > 0 ? Math.min(...volumeValues) : 0
  const volMax = volumeValues.length > 0 ? Math.max(...volumeValues) : 1
  const volRange = volMax - volMin || 1

  const chartData = buckets.map((p) => {
    const vol = p.total_volume ?? null
    const volNorm = vol != null ? (vol - volMin) / volRange : null
    return {
      time: p.bucket_start
        ? (useUtc
            ? new Date(p.bucket_start).toLocaleTimeString('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' })
            : new Date(p.bucket_start).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
        : '',
      fullTime: p.bucket_start,
      home_back: p.home_best_back ?? null,
      away_back: p.away_best_back ?? null,
      draw_back: p.draw_best_back ?? null,
      total_volume: vol,
      volume_normalized: volNorm,
      home_book_risk_l3: p.home_book_risk_l3 ?? null,
      away_book_risk_l3: p.away_book_risk_l3 ?? null,
      draw_book_risk_l3: p.draw_book_risk_l3 ?? null,
    }
  })
  const hasBookRiskL3 = buckets.some((p) => p.home_book_risk_l3 != null || p.away_book_risk_l3 != null || p.draw_book_risk_l3 != null)

  // Find selected bucket data
  const selectedBucketData = selectedBucket
    ? buckets.find((p) => p.bucket_start === selectedBucket)
    : null

  /** One column per unique publish_time; API returns one row per (time, runner), so we merge into one row per time. */
  const ticksMergedByTime = useMemo(() => {
    const result: Array<{
      publish_time: string | null
      home_back_odds: number | null
      home_back_size: number | null
      away_back_odds: number | null
      away_back_size: number | null
      draw_back_odds: number | null
      draw_back_size: number | null
    }> = []
    let currentTime: string | null = null
    let current: (typeof result)[0] | null = null
    for (const t of ticks) {
      if (t.publish_time !== currentTime) {
        currentTime = t.publish_time
        current = {
          publish_time: t.publish_time,
          home_back_odds: t.home_back_odds ?? null,
          home_back_size: t.home_back_size ?? null,
          away_back_odds: t.away_back_odds ?? null,
          away_back_size: t.away_back_size ?? null,
          draw_back_odds: t.draw_back_odds ?? null,
          draw_back_size: t.draw_back_size ?? null,
        }
        result.push(current)
      } else if (current) {
        if (t.home_back_odds != null) current.home_back_odds = t.home_back_odds
        if (t.home_back_size != null) current.home_back_size = t.home_back_size
        if (t.away_back_odds != null) current.away_back_odds = t.away_back_odds
        if (t.away_back_size != null) current.away_back_size = t.away_back_size
        if (t.draw_back_odds != null) current.draw_back_odds = t.draw_back_odds
        if (t.draw_back_size != null) current.draw_back_size = t.draw_back_size
      }
    }
    return result
  }, [ticks])
  
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
            {(() => {
              const homeName = meta.home_runner_name?.trim() || null
              const awayName = meta.away_runner_name?.trim() || null
              const homeStatus = meta.home_runner_status ?? null
              const awayStatus = meta.away_runner_status ?? null
              const drawStatus = meta.draw_runner_status ?? null
              const isDraw = drawStatus === 'WINNER'
              const homeWinner = homeStatus === 'WINNER'
              const awayWinner = awayStatus === 'WINNER'
              const homeColor = isDraw ? 'rgba(244, 67, 54, 0.9)' : homeWinner ? 'rgba(76, 175, 80, 0.9)' : undefined
              const awayColor = isDraw ? 'rgba(244, 67, 54, 0.9)' : awayWinner ? 'rgba(76, 175, 80, 0.9)' : undefined
              if (homeName && awayName) {
                return (
                  <Typography variant="h6" component="div">
                    <span style={homeColor ? { color: homeColor } : undefined}>{homeName}</span>
                    {' vs '}
                    <span style={awayColor ? { color: awayColor } : undefined}>{awayName}</span>
                  </Typography>
                )
              }
              return <Typography variant="h6">{meta.event_name || marketId}</Typography>
            })()}
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

          {loadingBuckets ? (
            <Typography color="text.secondary">Loading buckets…</Typography>
          ) : buckets.length === 0 ? (
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              No 15-minute snapshots available for this market.
            </Typography>
          ) : (
            <>
              {/* Chart 1: Risk (Book Risk L3) */}
              {hasBookRiskL3 && (
                <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>Risk (Book Risk L3 H/A/D) + Volume (normalized)</Typography>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={chartData} margin={{ top: 5, right: 50, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis yAxisId="risk" />
                      <YAxis yAxisId="volume" orientation="right" domain={[0, 1]} hide />
                      <RechartsTooltip />
                      <Legend />
                      <Line type="monotone" dataKey="home_book_risk_l3" name="Home" stroke="#1976d2" dot={false} yAxisId="risk" />
                      <Line type="monotone" dataKey="away_book_risk_l3" name="Away" stroke="#9c27b0" dot={false} yAxisId="risk" />
                      <Line type="monotone" dataKey="draw_book_risk_l3" name="Draw" stroke="#2e7d32" dot={false} yAxisId="risk" />
                      <Line type="monotone" dataKey="volume_normalized" name="Volume (normalized)" stroke="#ed6c02" dot={false} yAxisId="volume" connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </Paper>
              )}

              {/* Bucket Selection */}
              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Select 15-minute bucket</Typography>
              <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
                {buckets.slice(0, bucketListVisible).map((point) => {
                  const hasData = (point.tick_count ?? 0) > 0
                  const isCarryForward =
                    (point.tick_count == null || point.tick_count === 0) &&
                    (point.home_back_odds_median != null || point.away_back_odds_median != null || point.draw_back_odds_median != null)
                  return (
                    <Button
                      key={point.bucket_start}
                      variant={selectedBucket === point.bucket_start ? 'contained' : 'outlined'}
                      size="small"
                      onClick={() => setSelectedBucket(point.bucket_start)}
                      sx={{
                        minWidth: 56,
                        width: 56,
                        ...(selectedBucket !== point.bucket_start && hasData && !isCarryForward && {
                          bgcolor: 'rgba(33, 150, 243, 0.12)',
                          '&:hover': { bgcolor: 'rgba(33, 150, 243, 0.2)' },
                        }),
                      }}
                    >
                      {point.bucket_start
                        ? (useUtc
                            ? new Date(point.bucket_start).toLocaleTimeString('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' })
                            : new Date(point.bucket_start).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
                        : '—'}
                    </Button>
                  )
                })}
                {buckets.length > bucketListVisible && (
                  <Button size="small" variant="outlined" onClick={() => setBucketListVisible((n) => n + 50)}>
                    Show more ({buckets.length - bucketListVisible} more)
                  </Button>
                )}
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
                    const tickCountDisplay = selectedBucketData?.tick_count ?? ticks.length
                    const firstTick = ticksMergedByTime.length > 0 ? ticksMergedByTime[0]?.publish_time ?? null : null
                    const lastTick = ticksMergedByTime.length > 0 ? ticksMergedByTime[ticksMergedByTime.length - 1]?.publish_time ?? null : null
                    const mediansNonNull = selectedBucketData && (
                      selectedBucketData.home_back_odds_median != null || selectedBucketData.away_back_odds_median != null || selectedBucketData.draw_back_odds_median != null
                    )
                    const carryForwardWarning = ticks.length === 0 && mediansNonNull
                    return (
                      <>
                        <Box sx={{ mb: 1, fontSize: '0.8rem', color: 'text.secondary' }}>
                          bucket_start: {formatTime(selectedBucket, useUtc)} · bucket_end: {formatTime(bucketEnd.toISOString(), useUtc)} · tick_count: {tickCountDisplay}
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
                            <TableCell sx={{ minWidth: 72 }}>Runner</TableCell>
                            {ticksMergedByTime.map((row, i) => (
                              <TableCell key={i} align="left" sx={{ minWidth: 90 }}>
                                {row.publish_time ? formatTime(row.publish_time, useUtc) : '—'}
                              </TableCell>
                            ))}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {ticksMergedByTime.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={2} align="center">
                                <Typography color="text.secondary">No ticks found in this bucket</Typography>
                              </TableCell>
                            </TableRow>
                          ) : (
                            <>
                              <TableRow>
                                <TableCell><strong>Home</strong></TableCell>
                                {ticksMergedByTime.map((row, i) => (
                                  <TableCell key={i} align="left">
                                    {formatOdds(row.home_back_odds).text} / {num(row.home_back_size ?? null)}
                                  </TableCell>
                                ))}
                              </TableRow>
                              <TableRow>
                                <TableCell><strong>Away</strong></TableCell>
                                {ticksMergedByTime.map((row, i) => (
                                  <TableCell key={i} align="left">
                                    {formatOdds(row.away_back_odds).text} / {num(row.away_back_size ?? null)}
                                  </TableCell>
                                ))}
                              </TableRow>
                              <TableRow>
                                <TableCell><strong>Draw</strong></TableCell>
                                {ticksMergedByTime.map((row, i) => (
                                  <TableCell key={i} align="left">
                                    {formatOdds(row.draw_back_odds).text} / {num(row.draw_back_size ?? null)}
                                  </TableCell>
                                ))}
                              </TableRow>
                            </>
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
                {lastRequestInfo.buckets && (
                  <>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>Buckets</Typography>
                    <Typography component="code">GET {lastRequestInfo.buckets}</Typography>
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
            {selectedBucketData && buckets.length > 0 && (
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
