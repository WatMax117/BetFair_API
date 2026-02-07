import { useState, useEffect, useCallback } from 'react'
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

  const from = new Date(Date.now() - timeRangeHours * 60 * 60 * 1000)
  const to = new Date()

  useEffect(() => {
    setLoadingMeta(true)
    fetchEventMeta(marketId)
      .then(setMeta)
      .catch(() => setMeta(null))
      .finally(() => setLoadingMeta(false))
  }, [marketId])

  const loadTimeseries = useCallback(() => {
    setLoadingTs(true)
    fetchEventTimeseries(marketId, from, to, 15)
      .then(setTimeseries)
      .catch(() => setTimeseries([]))
      .finally(() => setLoadingTs(false))
  }, [marketId, from.getTime(), to.getTime()])

  useEffect(() => {
    loadTimeseries()
  }, [loadTimeseries])

  const chartData = timeseries.map((p) => ({
    time: p.snapshot_at ? new Date(p.snapshot_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '',
    fullTime: p.snapshot_at,
    home_back: p.home_best_back,
    away_back: p.away_best_back,
    draw_back: p.draw_best_back,
    home_risk: p.home_risk,
    away_risk: p.away_risk,
    draw_risk: p.draw_risk,
    total_volume: p.total_volume,
  }))

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
      .then((r) => setRawPayload(r.raw_payload))
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
            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
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
                  <Typography variant="caption" color="text.secondary">Index</Typography>
                  <Typography>H {num(latest.home_risk)} / A {num(latest.away_risk)} / D {num(latest.draw_risk)}</Typography>
                </Box>
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
                      <TableCell align="right">back H</TableCell>
                      <TableCell align="right">back A</TableCell>
                      <TableCell align="right">back D</TableCell>
                      <TableCell align="right">index H</TableCell>
                      <TableCell align="right">index A</TableCell>
                      <TableCell align="right">index D</TableCell>
                      <TableCell align="right">total_volume</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {last10.map((p, i) => (
                      <TableRow key={i}>
                        <TableCell>{p.snapshot_at ? formatTime(p.snapshot_at) : '—'}</TableCell>
                        <TableCell align="right">{num(p.home_best_back)}</TableCell>
                        <TableCell align="right">{num(p.away_best_back)}</TableCell>
                        <TableCell align="right">{num(p.draw_best_back)}</TableCell>
                        <TableCell align="right">{num(p.home_risk)}</TableCell>
                        <TableCell align="right">{num(p.away_risk)}</TableCell>
                        <TableCell align="right">{num(p.draw_risk)}</TableCell>
                        <TableCell align="right">{num(p.total_volume)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </>
          )}

          <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Typography variant="caption" color="text.secondary" display="block">Data notes</Typography>
            <Typography variant="body2">
              Snapshot interval: 15 minutes. total_volume is market-level totalMatched; per-runner matched volume may be unavailable via REST.
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
