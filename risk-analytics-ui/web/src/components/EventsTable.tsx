import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import type { EventItem } from '../api'

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

function num(v: number | null): string {
  if (v == null) return '—'
  return Number.isInteger(v) ? String(v) : v.toFixed(2)
}

const ODDS_EXTREME = 1000
function formatOdds(odds: number | null | undefined): string {
  if (odds == null || odds <= 1.0) return '—'
  if (odds >= ODDS_EXTREME) return `≥${ODDS_EXTREME}`
  return Number.isInteger(odds) ? String(odds) : odds.toFixed(2)
}

export function EventsTable({
  events,
  onSelectEvent,
  showLimitNote = false,
}: {
  events: EventItem[]
  onSelectEvent: (e: EventItem) => void
  showLimitNote?: boolean
}) {
  const metaTooltip = (e: EventItem) =>
    `depth_limit: ${e.depth_limit ?? '—'}, calculation_version: ${e.calculation_version ?? '—'}`

  if (events.length === 0) {
    return (
      <Typography color="text.secondary">No events in this league for the selected window.</Typography>
    )
  }

  return (
    <>
    {showLimitNote && (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        Showing up to 100 events. Narrow your time range for more specific results.
      </Typography>
    )}
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Start time</TableCell>
            <TableCell>Event</TableCell>
            <TableCell align="right">Home</TableCell>
            <TableCell align="right">Away</TableCell>
            <TableCell align="right">Draw</TableCell>
            <TableCell align="right">Volume</TableCell>
            <TableCell>Last update</TableCell>
            <TableCell padding="none" width={40} />
          </TableRow>
        </TableHead>
        <TableBody>
          {events.map((e) => (
            <TableRow
              key={e.market_id}
              hover
              onClick={() => onSelectEvent(e)}
              sx={{
                cursor: 'pointer',
                '&:hover': { bgcolor: 'action.selected' },
              }}
            >
              <TableCell>{formatTime(e.event_open_date)}</TableCell>
              <TableCell>{e.event_name || e.market_id}</TableCell>
              <TableCell align="right">{formatOdds(e.home_best_back)}</TableCell>
              <TableCell align="right">{formatOdds(e.away_best_back)}</TableCell>
              <TableCell align="right">{formatOdds(e.draw_best_back)}</TableCell>
              <TableCell align="right">{num(e.total_volume)}</TableCell>
              <TableCell>{formatTime(e.latest_snapshot_at)}</TableCell>
              <TableCell padding="none" onClick={(ev) => ev.stopPropagation()}>
                <Tooltip title={metaTooltip(e)}>
                  <IconButton size="small" aria-label="depth_limit and calculation_version">
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
    </>
  )
}
