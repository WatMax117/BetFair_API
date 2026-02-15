import { useMemo } from 'react'
import Box from '@mui/material/Box'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import InputLabel from '@mui/material/InputLabel'
import Link from '@mui/material/Link'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Switch from '@mui/material/Switch'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import type { EventItem } from '../api'

const SORT_KEYS = [
  { id: 'book_risk_home', label: 'Book Risk L3 Home', getVal: (e: EventItem) => e.home_book_risk_l3 ?? null },
  { id: 'book_risk_away', label: 'Book Risk L3 Away', getVal: (e: EventItem) => e.away_book_risk_l3 ?? null },
  { id: 'book_risk_draw', label: 'Book Risk L3 Draw', getVal: (e: EventItem) => e.draw_book_risk_l3 ?? null },
  { id: 'volume', label: 'Volume', getVal: (e: EventItem) => e.total_volume ?? null },
] as const

export type SortField = (typeof SORT_KEYS)[number]['id']
export type SortState = {
  field: SortField
  desc: boolean
  signed: boolean
}

const STORAGE_KEY = 'ra_bookrisk_sort_state'
const DEFAULT_SORT: SortState = { field: 'book_risk_home', desc: true, signed: true }

function loadSortState(): SortState {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    if (s) {
      const parsed = JSON.parse(s) as Partial<SortState>
      const field = SORT_KEYS.some((k) => k.id === parsed.field) ? (parsed.field as SortField) : DEFAULT_SORT.field
      return {
        field,
        desc: parsed.desc ?? DEFAULT_SORT.desc,
        signed: parsed.signed ?? DEFAULT_SORT.signed,
      }
    }
  } catch {
    /* ignore */
  }
  return DEFAULT_SORT
}

function saveSortState(state: SortState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* ignore */
  }
}

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

/** NULL sorts always last (never as 0). */
function sortValue(v: number | null, signed: boolean, desc: boolean): number {
  if (v == null) return desc ? -Infinity : Infinity
  return signed ? v : Math.abs(v)
}

export function SortedEventsList({
  events,
  sortState,
  onSortChange,
  onSelectEvent,
  onlyActiveInPlay = true,
  onOnlyActiveChange,
  onlyMarketsWithBookRisk = true,
  onOnlyMarketsWithBookRiskChange,
}: {
  events: EventItem[]
  sortState: SortState
  onSortChange: (s: SortState) => void
  onSelectEvent: (e: EventItem) => void
  onlyActiveInPlay?: boolean
  onOnlyActiveChange?: (v: boolean) => void
  onlyMarketsWithBookRisk?: boolean
  onOnlyMarketsWithBookRiskChange?: (v: boolean) => void
}) {
  const sorted = useMemo(() => {
    const key = SORT_KEYS.find((k) => k.id === sortState.field)
    if (!key) return [...events]

    const getPrimary = (e: EventItem) => {
      const v = key.getVal(e)
      if (key.id === 'volume') return v ?? (sortState.desc ? -Infinity : Infinity)
      return sortValue(v, sortState.signed, sortState.desc)
    }

    return [...events].sort((a, b) => {
      const pa = getPrimary(a)
      const pb = getPrimary(b)
      let cmp = 0
      if (pa < pb) cmp = -1
      else if (pa > pb) cmp = 1
      else {
        const va = a.total_volume ?? 0
        const vb = b.total_volume ?? 0
        cmp = vb - va
        if (cmp === 0) {
          const da = a.event_open_date ?? ''
          const db = b.event_open_date ?? ''
          cmp = da.localeCompare(db)
          if (cmp === 0) cmp = (a.market_id ?? '').localeCompare(b.market_id ?? '')
        }
      }
      return sortState.desc ? -cmp : cmp
    })
  }, [events, sortState])

  const handleFieldChange = (field: SortField) => {
    const next: SortState = { ...sortState, field }
    saveSortState(next)
    onSortChange(next)
  }

  const handleDescToggle = () => {
    const next: SortState = { ...sortState, desc: !sortState.desc }
    saveSortState(next)
    onSortChange(next)
  }

  const handleSignedToggle = () => {
    const next: SortState = { ...sortState, signed: !sortState.signed }
    saveSortState(next)
    onSortChange(next)
  }

  const isBookRiskSort = sortState.field.startsWith('book_risk_')

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Sorted events list
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2, alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Sort by</InputLabel>
          <Select
            value={sortState.field}
            label="Sort by"
            onChange={(e) => handleFieldChange(e.target.value as SortField)}
          >
            {SORT_KEYS.map((k) => (
              <MenuItem key={k.id} value={k.id}>
                {k.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={sortState.desc}
              onChange={handleDescToggle}
              color="primary"
            />
          }
          label="Descending"
        />
        {isBookRiskSort && (
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={sortState.signed}
                onChange={handleSignedToggle}
                color="primary"
              />
            }
            label="Signed (vs Absolute)"
          />
        )}
        {onOnlyActiveChange != null && (
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={onlyActiveInPlay}
                onChange={(_, v) => onOnlyActiveChange(v)}
                color="primary"
              />
            }
            label="Only active/in-play"
          />
        )}
        {onOnlyMarketsWithBookRiskChange != null && (
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={onlyMarketsWithBookRisk}
                onChange={(_, v) => onOnlyMarketsWithBookRiskChange(v)}
                color="primary"
              />
            }
            label="Only markets with Book Risk"
          />
        )}
      </Box>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Event</TableCell>
              <TableCell>Market ID</TableCell>
              <TableCell align="right">Book Risk H</TableCell>
              <TableCell align="right">Book Risk A</TableCell>
              <TableCell align="right">Book Risk D</TableCell>
              <TableCell align="right">Volume</TableCell>
              <TableCell>Open date</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((e) => (
              <TableRow
                key={e.market_id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => onSelectEvent(e)}
              >
                <TableCell>{e.event_name || e.market_id}</TableCell>
                <TableCell>
                  <Link
                    component="button"
                    variant="body2"
                    onClick={(ev: React.MouseEvent) => {
                      ev.stopPropagation()
                      onSelectEvent(e)
                    }}
                  >
                    {e.market_id}
                  </Link>
                </TableCell>
                <TableCell align="right">{num(e.home_book_risk_l3 ?? null)}</TableCell>
                <TableCell align="right">{num(e.away_book_risk_l3 ?? null)}</TableCell>
                <TableCell align="right">{num(e.draw_book_risk_l3 ?? null)}</TableCell>
                <TableCell align="right">{num(e.total_volume ?? null)}</TableCell>
                <TableCell>{formatTime(e.event_open_date)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
        Secondary ordering: Volume desc, event_open_date asc, market_id. Click row or Market ID to open detail.
      </Typography>
    </Box>
  )
}

export { loadSortState, saveSortState, DEFAULT_SORT }
