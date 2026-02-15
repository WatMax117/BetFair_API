import { useState, useEffect, useCallback } from 'react'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import { SortedEventsList, loadSortState, type SortState } from './SortedEventsList'
import { fetchEventsByDateSnapshots } from '../api'
import type { EventItem } from '../api'

/** Today's date in UTC as YYYY-MM-DD (for default and date input). */
function getTodayUTC(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Yesterday in UTC as YYYY-MM-DD. */
function getYesterdayUTC(): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() - 1)
  return d.toISOString().slice(0, 10)
}

/** Tomorrow in UTC as YYYY-MM-DD. */
function getTomorrowUTC(): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}

export function LeaguesAccordion({ onSelectEvent }: { onSelectEvent: (e: EventItem) => void }) {
  const [selectedDate, setSelectedDate] = useState<string>(() => getTodayUTC())
  const [events, setEvents] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortState, setSortState] = useState<SortState>(loadSortState)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchEventsByDateSnapshots(selectedDate)
      setEvents(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load events')
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [selectedDate])

  useEffect(() => {
    load()
  }, [load])

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Events by date (snapshot-driven)
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', mb: 2 }}>
        <TextField
          type="date"
          label="Date (UTC)"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value || getTodayUTC())}
          InputLabelProps={{ shrink: true }}
          size="small"
          sx={{ width: 160 }}
        />
        <Button variant="outlined" size="small" onClick={() => setSelectedDate(getYesterdayUTC())}>
          Yesterday
        </Button>
        <Button variant="outlined" size="small" onClick={() => setSelectedDate(getTodayUTC())}>
          Today
        </Button>
        <Button variant="outlined" size="small" onClick={() => setSelectedDate(getTomorrowUTC())}>
          Tomorrow
        </Button>
      </Box>

      {error && (
        <Typography color="error" sx={{ mb: 1 }}>
          {error}
        </Typography>
      )}

      {loading ? (
        <Typography color="text.secondary">Loading…</Typography>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            All events for {selectedDate} (UTC) with at least one snapshot. Row count = backend count. Missing H/A/D shown as —. Sort: H / A / D / Volume / Event Open Date; tie-breakers: volume desc, open date asc, market_id asc.
          </Typography>
          <SortedEventsList
            events={events}
            sortState={sortState}
            onSortChange={setSortState}
            onSelectEvent={onSelectEvent}
            showCalendarColumns
          />
        </>
      )}
    </Box>
  )
}
