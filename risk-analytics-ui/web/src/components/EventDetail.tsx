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
import { fetchEventMeta, fetchEventTimeseries, fetchEventLatestRaw } from '../api'
import type { EventMeta, TimeseriesPoint } from '../api'

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

const STAKE_IMPEDANCE_TOOLTIP = 'VWAP/top-N (back+lay) modelled exposure; negative of modelled book P&L if the outcome wins.'
const SIZE_IMPEDANCE_L1_TOOLTIP = 'Best-level (L1) only; back side. Noisy baseline vs Stake Impedance (VWAP/top-N).'

/** Size Impedance Index (L1): L1_j = size_j*(odds_j-1), P1_j = Σ L1_k (k≠j), SizeImpedance_L1_j = L1_j − P1_j. Invalid odds/size → 0. Returns nulls when L1 sizes not in payload. */
function computeSizeImpedanceL1(p: TimeseriesPoint): { home: number | null; away: number | null; draw: number | null } {
  const sh = p.home_best_back_size_l1 ?? null
  const sa = p.away_best_back_size_l1 ?? null
  const sd = p.draw_best_back_size_l1 ?? null
  if (sh == null && sa == null && sd == null) return { home: null, away: null, draw: null }
  const o = (x: number | null) => (x != null && x > 1 ? x : 0)
  const s = (x: number | null) => (x != null && x > 0 ? x : 0)
  const oh = o(p.home_best_back)
  const oa = o(p.away_best_back)
  const od = o(p.draw_best_back)
  const L1h = s(sh) * (oh - 1)
  const L1a = s(sa) * (oa - 1)
  const L1d = s(sd) * (od - 1)
  return {
    home: L1h - (L1a + L1d),
    away: L1a - (L1h + L1d),
    draw: L1d - (L1h + L1a),
  }
}

/** Fixed width for H/A/D labels so letters align across all HadCell columns in the table */
const HAD_LABEL_WIDTH = '1.25em'

/** Renders H/A/D values vertically. H, A, D are alignment anchors (fixed-width); values align relative to the label. Order always H then A then D. */
function HadCell({ home, away, draw }: { home: number | null; away: number | null; draw: number | null }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, width: '100%' }}>
      <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'baseline' }}>
        <Typography variant="body2" component="span" sx={{ minWidth: HAD_LABEL_WIDTH, textAlign: 'right' }}>H</Typography>
        <Typography variant="body2" component="span" sx={{ ml: 0.5 }}>{num(home)}</Typography>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'baseline' }}>
        <Typography variant="body2" component="span" sx={{ minWidth: HAD_LABEL_WIDTH, textAlign: 'right' }}>A</Typography>
        <Typography variant="body2" component="span" sx={{ ml: 0.5 }}>{num(away)}</Typography>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'baseline' }}>
        <Typography variant="body2" component="span" sx={{ minWidth: HAD_LABEL_WIDTH, textAlign: 'right' }}>D</Typography>
        <Typography variant="body2" component="span" sx={{ ml: 0.5 }}>{num(draw)}</Typography>
      </Box>
    </Box>
  )
}

export function EventDetail({
  marketId,
  eventName: _eventName,
  competitionName: _competitionName,
  eventOpenDate: _eventOpenDate,
  onBack,
}: {
  marketId: string
  eventName: string | null
  competitionName: string | null
  eventOpenDate: string | null
  onBack: () => void
}) {
  const [meta, setMeta] = useState<EventMeta | null>(null)
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([])
  const [loadingMeta, setLoadingMeta] = useState(true)
  const [loadingTs, setLoadingTs] = useState(true)
  const [timeRangeHours, setTimeRangeHours] = useState(24)
  const [rawModalOpen, setRawModalOpen] = useState(false)
  const [rawPayload, setRawPayload] = useState<unknown>(null)
  const [rawLoading, setRawLoading] = useState(false)
  /** Impedance is always loaded and shown (no toggle). */
  const includeImpedance = true

  const from = useMemo(() => new Date(Date.now() - timeRangeHours * 60 * 60 * 1000), [timeRangeHours])
  const to = useMemo(() => new Date(), [timeRangeHours])

  useEffect(() => {
    setLoadingMeta(true)
    fetchEventMeta(marketId)
      .then(setMeta)
      .catch(() => setMeta(null))
      .finally(() => setLoadingMeta(false))
  }, [marketId])

  const loadTimeseries = useCallback(() => {
    setLoadingTs(true)
    console.log('[EventDetail] Loading timeseries', { marketId, includeImpedance, from: from.toISOString(), to: to.toISOString() })
    fetchEventTimeseries(marketId, from, to, 15, includeImpedance)
      .then((data) => {
        console.log('[EventDetail] Timeseries loaded', { 
          count: data.length, 
          hasImpedance: data.some(p => p.impedance),
          sampleImpedance: data.find(p => p.impedance)?.impedance,
          hasImpedanceInputs: data.some(p => p.impedanceInputs),
          sampleImpedanceInputs: data.find(p => p.impedanceInputs)?.impedanceInputs
        })
        setTimeseries(data)
      })
      .catch((e) => {
        console.error('[EventDetail] Timeseries load error', e)
        setTimeseries([])
      })
      .finally(() => setLoadingTs(false))
  }, [marketId, from, to, includeImpedance])

  useEffect(() => {
    loadTimeseries()
  }, [loadTimeseries])

  const chartData = timeseries.map((p) => {
    const sizeL1 = computeSizeImpedanceL1(p)
    return {
      time: p.snapshot_at ? new Date(p.snapshot_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '',
      fullTime: p.snapshot_at,
      home_back: p.home_best_back ?? null,
      away_back: p.away_best_back ?? null,
      draw_back: p.draw_best_back ?? null,
      home_risk: p.home_risk ?? null,
      away_risk: p.away_risk ?? null,
      draw_risk: p.draw_risk ?? null,
      total_volume: p.total_volume ?? null,
      home_impedance_raw: p.impedance?.home ?? null,
      away_impedance_raw: p.impedance?.away ?? null,
      draw_impedance_raw: p.impedance?.draw ?? null,
      home_size_impedance_l1: sizeL1.home,
      away_size_impedance_l1: sizeL1.away,
      draw_size_impedance_l1: sizeL1.draw,
    }
  })
  const hasImpedance = timeseries.some((p) => p.impedance && (p.impedance.home != null || p.impedance.away != null || p.impedance.draw != null))
  const hasSizeImpedanceL1 = timeseries.some((p) => {
    const s = computeSizeImpedanceL1(p)
    return s.home != null || s.away != null || s.draw != null
  })
  useEffect(() => {
    console.log('[EventDetail] Render state', { 
      includeImpedance, 
      timeseriesLength: timeseries.length, 
      hasImpedance,
      samplePoint: timeseries.find(p => p.impedance) 
    })
  }, [includeImpedance, timeseries, hasImpedance])

  const latest = timeseries.length > 0 ? timeseries[timeseries.length - 1] : null
  const last10 = timeseries.slice(-10).reverse()
  const homeSpread = latest ? spread(latest.home_best_back, latest.home_best_lay) : null
  const awaySpread = latest ? spread(latest.away_best_back, latest.away_best_lay) : null
  const drawSpread = latest ? spread(latest.draw_best_back, latest.draw_best_lay) : null

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
            {latest && (
              <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Best back</Typography>
                  <Typography>H {num(latest.home_best_back)} / A {num(latest.away_best_back)} / D {num(latest.draw_best_back)}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Best lay</Typography>
                  <Typography>H {num(latest.home_best_lay)} / A {num(latest.away_best_lay)} / D {num(latest.draw_best_lay)}</Typography>
                </Box>
                <Tooltip title="Spread = best lay − best back (per selection)">
                  <Box>
                    <Typography variant="caption" color="text.secondary">Spreads (lay − back)</Typography>
                    <Typography>H {num(homeSpread)} / A {num(awaySpread)} / D {num(drawSpread)}</Typography>
                  </Box>
                </Tooltip>
                <Box>
                  <Typography variant="caption" color="text.secondary">Imbalance index (H / A / D)</Typography>
                  <Typography>H {num(latest.home_risk)} / A {num(latest.away_risk)} / D {num(latest.draw_risk)}</Typography>
                </Box>
                {includeImpedance && latest.impedance && (latest.impedance.home != null || latest.impedance.away != null || latest.impedance.draw != null) && (
                  <Tooltip title={STAKE_IMPEDANCE_TOOLTIP}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Stake Impedance Index (H / A / D)</Typography>
                      <Typography>H {num(latest.impedance.home)} / A {num(latest.impedance.away)} / D {num(latest.impedance.draw)}</Typography>
                    </Box>
                  </Tooltip>
                )}
                {includeImpedance && latest.impedanceInputs && (
                  <>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Back stake (H / A / D)</Typography>
                      <Typography>H {num(latest.impedanceInputs.home?.backStake)} / A {num(latest.impedanceInputs.away?.backStake)} / D {num(latest.impedanceInputs.draw?.backStake)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Back odds (H / A / D)</Typography>
                      <Typography>H {num(latest.impedanceInputs.home?.backOdds)} / A {num(latest.impedanceInputs.away?.backOdds)} / D {num(latest.impedanceInputs.draw?.backOdds)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Back profit (H / A / D)</Typography>
                      <Typography>H {num(latest.impedanceInputs.home?.backProfit)} / A {num(latest.impedanceInputs.away?.backProfit)} / D {num(latest.impedanceInputs.draw?.backProfit)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Lay stake (H / A / D)</Typography>
                      <Typography>H {num(latest.impedanceInputs.home?.layStake)} / A {num(latest.impedanceInputs.away?.layStake)} / D {num(latest.impedanceInputs.draw?.layStake)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Lay odds (H / A / D)</Typography>
                      <Typography>H {num(latest.impedanceInputs.home?.layOdds)} / A {num(latest.impedanceInputs.away?.layOdds)} / D {num(latest.impedanceInputs.draw?.layOdds)}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">Lay liability (H / A / D)</Typography>
                      <Typography>H {num(latest.impedanceInputs.home?.layLiability)} / A {num(latest.impedanceInputs.away?.layLiability)} / D {num(latest.impedanceInputs.draw?.layLiability)}</Typography>
                    </Box>
                    {(() => {
                      const totalBack = (latest.impedanceInputs.home?.backStake ?? 0) + (latest.impedanceInputs.away?.backStake ?? 0) + (latest.impedanceInputs.draw?.backStake ?? 0)
                      const totalLay = (latest.impedanceInputs.home?.layStake ?? 0) + (latest.impedanceInputs.away?.layStake ?? 0) + (latest.impedanceInputs.draw?.layStake ?? 0)
                      const scale = totalBack + totalLay
                      return (
                        <Box>
                          <Typography variant="caption" color="text.secondary">Total scale</Typography>
                          <Typography>back: {num(totalBack)} / lay: {num(totalLay)} / scale: {num(scale)}</Typography>
                        </Box>
                      )
                    })()}
                  </>
                )}
                <Box>
                  <Typography variant="caption" color="text.secondary">Total volume</Typography>
                  <Typography>{num(latest.total_volume)}</Typography>
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
              <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>Best back odds</Typography>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <RechartsTooltip />
                    <Legend />
                    <Line type="monotone" dataKey="home_back" name="Home" stroke="#1976d2" dot={false} />
                    <Line type="monotone" dataKey="away_back" name="Away" stroke="#9c27b0" dot={false} />
                    <Line type="monotone" dataKey="draw_back" name="Draw" stroke="#2e7d32" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Paper>

              <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>Liquidity Imbalance Index</Typography>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <RechartsTooltip />
                    <Legend />
                    <Line type="monotone" dataKey="home_risk" name="Home" stroke="#1976d2" dot={false} />
                    <Line type="monotone" dataKey="away_risk" name="Away" stroke="#9c27b0" dot={false} />
                    <Line type="monotone" dataKey="draw_risk" name="Draw" stroke="#2e7d32" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Paper>
              {includeImpedance && hasImpedance && (
                <>
                  <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                    <Box sx={{ px: 1 }}>
                      <Tooltip title={STAKE_IMPEDANCE_TOOLTIP}>
                        <Typography variant="caption" color="text.secondary" component="span">Stake Impedance Index (H / A / D)</Typography>
                      </Tooltip>
                    </Box>
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="time" />
                        <YAxis />
                        <RechartsTooltip />
                        <Legend />
                        <Line type="monotone" dataKey="home_impedance_raw" name="Home" stroke="#1976d2" dot={false} />
                        <Line type="monotone" dataKey="away_impedance_raw" name="Away" stroke="#9c27b0" dot={false} />
                        <Line type="monotone" dataKey="draw_impedance_raw" name="Draw" stroke="#2e7d32" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </Paper>
                  {hasSizeImpedanceL1 && (
                    <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                      <Box sx={{ px: 1 }}>
                        <Tooltip title={SIZE_IMPEDANCE_L1_TOOLTIP}>
                          <Typography variant="caption" color="text.secondary" component="span">Size Impedance Index (L1) (H / A / D)</Typography>
                        </Tooltip>
                      </Box>
                      <ResponsiveContainer width="100%" height={240}>
                        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="time" />
                          <YAxis />
                          <RechartsTooltip />
                          <Legend />
                          <Line type="monotone" dataKey="home_size_impedance_l1" name="Home" stroke="#1976d2" dot={false} />
                          <Line type="monotone" dataKey="away_size_impedance_l1" name="Away" stroke="#9c27b0" dot={false} />
                          <Line type="monotone" dataKey="draw_size_impedance_l1" name="Draw" stroke="#2e7d32" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </Paper>
                  )}
                  {/* Placeholder for future delta view */}
                  {/* <Paper sx={{ p: 1, mb: 2, height: 280 }}>
                    <Box sx={{ px: 1 }}>
                      <Typography variant="caption" color="text.secondary" component="span">Δ Stake Impedance vs previous snapshot</Typography>
                    </Box>
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="time" />
                        <YAxis />
                        <RechartsTooltip />
                        <Legend />
                        <Line type="monotone" dataKey="home_impedance_delta" name="Home Δ" stroke="#1976d2" dot={false} />
                        <Line type="monotone" dataKey="away_impedance_delta" name="Away Δ" stroke="#9c27b0" dot={false} />
                        <Line type="monotone" dataKey="draw_impedance_delta" name="Draw Δ" stroke="#2e7d32" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </Paper> */}
                </>
              )}

              <Paper sx={{ p: 1, mb: 2, height: 220 }}>
                <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>Total volume</Typography>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <RechartsTooltip />
                    <Line type="monotone" dataKey="total_volume" name="Total volume" stroke="#ed6c02" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Paper>

              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Last 10 snapshots (copy-friendly)</Typography>
              <TableContainer component={Paper} variant="outlined" sx={{ mb: 2, userSelect: 'text' }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>snapshot_at</TableCell>
                      <TableCell align="left" title="L1 best back odds">backOdds (L1)</TableCell>
                      <TableCell align="left" title="Best back size (L1 only)">backSize (L1)</TableCell>
                      <TableCell align="left" title="L2 best back odds">backOdds (L2)</TableCell>
                      <TableCell align="left" title="L2 best back size">backSize (L2)</TableCell>
                      <TableCell align="left" title="L3 best back odds">backOdds (L3)</TableCell>
                      <TableCell align="left" title="L3 best back size">backSize (L3)</TableCell>
                      <TableCell align="left" title="3-way book exposure at top 3 back levels. R[o]=W[o]-L[o]; &gt;0 = book loses if outcome wins.">Book Risk L3 (H/A/D)</TableCell>
                      <TableCell align="left">Imbalance</TableCell>
                      <TableCell align="left" title={SIZE_IMPEDANCE_L1_TOOLTIP}>Size Impedance Index (L1)</TableCell>
                      <TableCell align="left" title={STAKE_IMPEDANCE_TOOLTIP}>Stake Impedance Index</TableCell>
                      <TableCell align="right">total_volume</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {last10.map((p, i) => {
                      const sizeL1 = computeSizeImpedanceL1(p)
                      return (
                        <TableRow key={i}>
                          <TableCell>{p.snapshot_at ? formatTime(p.snapshot_at) : '—'}</TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_best_back}
                              away={p.away_best_back}
                              draw={p.draw_best_back}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_best_back_size_l1 ?? null}
                              away={p.away_best_back_size_l1 ?? null}
                              draw={p.draw_best_back_size_l1 ?? null}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_back_odds_l2 ?? null}
                              away={p.away_back_odds_l2 ?? null}
                              draw={p.draw_back_odds_l2 ?? null}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_back_size_l2 ?? null}
                              away={p.away_back_size_l2 ?? null}
                              draw={p.draw_back_size_l2 ?? null}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_back_odds_l3 ?? null}
                              away={p.away_back_odds_l3 ?? null}
                              draw={p.draw_back_odds_l3 ?? null}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_back_size_l3 ?? null}
                              away={p.away_back_size_l3 ?? null}
                              draw={p.draw_back_size_l3 ?? null}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.home_book_risk_l3 ?? null}
                              away={p.away_book_risk_l3 ?? null}
                              draw={p.draw_book_risk_l3 ?? null}
                            />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell home={p.home_risk} away={p.away_risk} draw={p.draw_risk} />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell home={sizeL1.home} away={sizeL1.away} draw={sizeL1.draw} />
                          </TableCell>
                          <TableCell align="left">
                            <HadCell
                              home={p.impedance?.home ?? null}
                              away={p.impedance?.away ?? null}
                              draw={p.impedance?.draw ?? null}
                            />
                          </TableCell>
                          <TableCell align="right">{num(p.total_volume)}</TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </TableContainer>

            </>
          )}

          <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Typography variant="caption" color="text.secondary" display="block">Data notes</Typography>
            <Typography variant="body2">
              Snapshot interval: 15 minutes. total_volume is market-level totalMatched; per-runner matched volume may be unavailable via REST.
              backOdds/backSize (L1/L2/L3) are best three back levels; Size Impedance Index (L1) is computed from L1 back sizes when provided.
            </Typography>
            {latest && timeseries.length > 0 && (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                Last snapshot: {formatTime(timeseries[timeseries.length - 1].snapshot_at)}.
                {latest.depth_limit != null && ` depth_limit: ${latest.depth_limit}.`}
                {latest.calculation_version && ` calculation_version: ${latest.calculation_version}.`}
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
