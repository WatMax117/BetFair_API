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
import { fetchEventMeta, fetchEventTimeseries, fetchEventLatestRaw, fetchMarketTicks } from '../api'
import type { EventMeta, TimeseriesPoint, TickRow } from '../api'

const TIME_RANGES = [
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '72h', hours: 72 },
] as const

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

function num(v: number | null): string {
  if (v == null) return '—'
  return Number.isInteger(v) ? String(v) : v.toFixed(2)
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
    console.log('[EventDetail] Loading timeseries', { marketId, from: from.toISOString(), to: to.toISOString() })
    setLoadingTs(true)
    fetchEventTimeseries(marketId, from, to, 15)
      .then((data: TimeseriesPoint[]) => {
        console.log('[EventDetail] Timeseries received', { 
          length: data.length, 
          first: data.length > 0 ? data[0] : null, 
          last: data.length > 0 ? data[data.length - 1] : null
        })
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
    setLoadingTicks(true)
    fetchMarketTicks(marketId, bucketStart, bucketEnd, 2000)
      .then((data: TickRow[]) => {
        console.log('[EventDetail] Ticks received', { 
          length: data.length, 
          first: data.length > 0 ? data[0] : null
        })
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
    time: p.snapshot_at ? new Date(p.snapshot_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '',
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
  
  // Format bucket time for display
  const formatBucketTime = (iso: string | null): string => {
    if (!iso) return '—'
    try {
      const d = new Date(iso)
      return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
    } catch {
      return iso
    }
  }

  const handleCopyMarketId = () => {
    navigator.clipboard.writeText(marketId)
  }
  const handleViewRaw = () => {
    setRawModalOpen(true)
    setRawLoading(true)
    setRawPayload(null)
    fetchEventLatestRaw(marketId)
      .then((r: { raw_payload: unknown }) => setRawPayload(r.raw_payload))
      .catch(() => setRawPayload(null))
      .finally(() => setRawLoading(false))
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
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="h6">{meta.event_name || marketId}</Typography>
            <Typography color="text.secondary">
              {meta.competition_name} · Start: {formatTime(meta.event_open_date)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              market_id: {marketId}
            </Typography>
            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <Button size="small" startIcon={<ContentCopyIcon />} onClick={handleCopyMarketId}>
                Copy market_id
              </Button>
              <Button size="small" startIcon={<CodeIcon />} onClick={handleViewRaw}>
                View latest raw snapshot (JSON)
              </Button>
            </Box>
            {selectedBucketData && (
              <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Best back</Typography>
                  <Typography>H {num(selectedBucketData.home_best_back)} / A {num(selectedBucketData.away_best_back)} / D {num(selectedBucketData.draw_best_back)}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Best lay</Typography>
                  <Typography>H {num(selectedBucketData.home_best_lay)} / A {num(selectedBucketData.away_best_lay)} / D {num(selectedBucketData.draw_best_lay)}</Typography>
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
            <DialogTitle>Latest raw snapshot — {marketId}</DialogTitle>
            <DialogContent>
              {rawLoading ? (
                <Typography color="text.secondary">Loading…</Typography>
              ) : rawPayload != null ? (
                <Box component="pre" sx={{ overflow: 'auto', fontSize: '0.75rem', p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
                  {JSON.stringify(rawPayload, null, 2)}
                </Box>
              ) : (
                <Typography color="text.secondary">No raw snapshot available.</Typography>
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
                      ? new Date(point.snapshot_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
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
                  <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Outcome</TableCell>
                          <TableCell align="right">Median Back Odds (15m)</TableCell>
                          <TableCell align="right">Median Back Size (15m)</TableCell>
                          <TableCell align="right">Book Risk (15m)</TableCell>
                          <TableCell align="right">Impedance Index (15m)</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        <TableRow>
                          <TableCell><strong>H</strong></TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_back_odds_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_back_size_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.home_book_risk_l3 ?? null)}</TableCell>
                          <TableCell align="right" rowSpan={4}>{num(selectedBucketData.impedance_index_15m ?? null)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell><strong>A</strong></TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_back_odds_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_back_size_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.away_book_risk_l3 ?? null)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell><strong>D</strong></TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_back_odds_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_back_size_median ?? null)}</TableCell>
                          <TableCell align="right">{num(selectedBucketData.draw_book_risk_l3 ?? null)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell colSpan={3} variant="footer" sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
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
                                <TableCell>{tick.publish_time ? formatTime(tick.publish_time) : '—'}</TableCell>
                                <TableCell align="right">{num(tick.home_back_odds ?? null)}</TableCell>
                                <TableCell align="right">{num(tick.home_back_size ?? null)}</TableCell>
                                <TableCell align="right">{num(tick.away_back_odds ?? null)}</TableCell>
                                <TableCell align="right">{num(tick.away_back_size ?? null)}</TableCell>
                                <TableCell align="right">{num(tick.draw_back_odds ?? null)}</TableCell>
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

          <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Typography variant="caption" color="text.secondary" display="block">Data notes</Typography>
            <Typography variant="body2">
              Bucket interval: 15 minutes UTC. Medians are time-weighted over the bucket duration using carry-forward logic.
              Tick audit view shows all raw ticks (level=0, side='B') within the selected bucket.
            </Typography>
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
