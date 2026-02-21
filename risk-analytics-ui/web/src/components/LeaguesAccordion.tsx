import { useState, useEffect, useCallback, useMemo } from 'react'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import { fetchEventsByDateSnapshots, fetchDataHorizon } from '../api'
import type { EventItem } from '../api'

/** Today's date in UTC as YYYY-MM-DD (for default and date input). */
function getTodayUTC(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Add N days to a YYYY-MM-DD string, return YYYY-MM-DD. */
function addDays(dateStr: string, n: number): string {
  const d = new Date(dateStr + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Allowed = (date >= minDate) AND (no days list yet OR day is in allowedDays with ladder_rows > 0). */
function isDateAllowed(
  date: string,
  minDate: string,
  allowedDays: Set<string> | null
): boolean {
  if (date < minDate) return false
  if (!allowedDays || allowedDays.size === 0) return true
  return allowedDays.has(date)
}

/** Nearest allowed date: largest allowed date <= date, or earliest allowed if date is before all. */
function nearestPreviousAllowedDate(
  date: string,
  allowedDaysAsc: string[],
  minDate: string
): string {
  if (allowedDaysAsc.length === 0) return date >= minDate ? date : minDate
  let best = allowedDaysAsc[0]
  for (const d of allowedDaysAsc) {
    if (d > date) break
    best = d
  }
  return best
}

/** Group events by competition, competitions sorted by count desc, events by volume desc. */
function CompetitionAccordion({
  events,
  selectedDate,
  onSelectEvent,
}: {
  events: EventItem[]
  selectedDate: string
  onSelectEvent: (e: EventItem) => void
}) {
  const grouped = useMemo(() => {
    const byComp = new Map<string, EventItem[]>()
    for (const e of events) {
      const key = e.competition_name || 'Unknown'
      if (!byComp.has(key)) byComp.set(key, [])
      byComp.get(key)!.push(e)
    }
    for (const arr of byComp.values()) {
      arr.sort((a, b) => {
        const va = a.total_volume ?? -Infinity
        const vb = b.total_volume ?? -Infinity
        return vb - va
      })
    }
    return [...byComp.entries()]
      .map(([name, evs]) => ({ name, events: evs }))
      .sort((a, b) => b.events.length - a.events.length)
  }, [events])

  if (events.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No events for {selectedDate} (UTC) with streaming data.
      </Typography>
    )
  }

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Events for {selectedDate} (UTC), grouped by competition. Competitions by event count desc; events by volume desc.
      </Typography>
      {grouped.map(({ name, events: evs }, idx) => (
        <Accordion key={name} defaultExpanded={idx === 0}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>
              {name} ({evs.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <List dense disablePadding>
              {evs.map((e) => (
                <ListItem key={e.market_id} disablePadding>
                  <ListItemButton onClick={() => onSelectEvent(e)}>
                    <ListItemText
                      primary={e.event_name || e.market_id}
                      secondary={
                        e.total_volume != null
                          ? `Vol: ${Number(e.total_volume).toLocaleString()}`
                          : undefined
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  )
}

export function LeaguesAccordion({ 
  onSelectEvent, 
  onDateChange 
}: { 
  onSelectEvent: (e: EventItem) => void
  onDateChange?: (date: string) => void
}) {
  const [selectedDate, setSelectedDate] = useState<string>(() => getTodayUTC())
  const [events, setEvents] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dataHorizon, setDataHorizon] = useState<{
    minDate: string
    hint: string
    allowedDays: Set<string>
    allowedDaysAsc: string[]
  } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    console.log('[LeaguesAccordion] load called', { selectedDate })
    try {
      const data = await fetchEventsByDateSnapshots(selectedDate)
      console.log('[LeaguesAccordion] data received', { 
        isArray: Array.isArray(data), 
        length: Array.isArray(data) ? data.length : null,
        sample: Array.isArray(data) && data.length > 0 ? data[0] : null
      })
      const eventsArray = Array.isArray(data) ? data : []
      console.log('[LeaguesAccordion] setting events', { count: eventsArray.length })
      setEvents(eventsArray)
    } catch (e) {
      console.error('[LeaguesAccordion] load error', e)
      setError(e instanceof Error ? e.message : 'Failed to load events')
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [selectedDate])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    let cancelled = false
    fetchDataHorizon()
      .then((h) => {
        if (cancelled) return
        const oldestTick = h.oldest_tick
        const minDate = oldestTick ? oldestTick.slice(0, 10) : ''
        const daysWithData = (h.days ?? []).filter((d) => d.ladder_rows > 0).map((d) => d.day)
        const allowedDays = new Set(daysWithData)
        const allowedDaysAsc = [...daysWithData].sort()
        setDataHorizon({
          minDate,
          hint: minDate ? `Streaming data available from: ${minDate} (UTC)` : 'No streaming data yet',
          allowedDays,
          allowedDaysAsc,
        })
        setSelectedDate((prev) => {
          if (!minDate) return prev
          if (!isDateAllowed(prev, minDate, allowedDays.size > 0 ? allowedDays : null)) {
            return nearestPreviousAllowedDate(prev, allowedDaysAsc, minDate)
          }
          return prev
        })
      })
      .catch(() => {
        if (!cancelled) setDataHorizon(null)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (onDateChange) {
      onDateChange(selectedDate)
    }
  }, [selectedDate, onDateChange])

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Events by date (snapshot-driven)
      </Typography>

      {dataHorizon?.hint && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {dataHorizon.hint}
        </Typography>
      )}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', mb: 2 }}>
        <TextField
          type="date"
          label="Date (UTC)"
          value={selectedDate}
          onChange={(e) => {
            const value = e.target.value || getTodayUTC()
            if (!dataHorizon) {
              setSelectedDate(value)
              return
            }
            const allowed = dataHorizon.allowedDays.size > 0 ? dataHorizon.allowedDays : null
            if (isDateAllowed(value, dataHorizon.minDate, allowed)) {
              setSelectedDate(value)
              return
            }
            setSelectedDate(nearestPreviousAllowedDate(value, dataHorizon.allowedDaysAsc, dataHorizon.minDate))
          }}
          inputProps={
            dataHorizon?.minDate
              ? { min: dataHorizon.minDate }
              : undefined
          }
          InputLabelProps={{ shrink: true }}
          size="small"
          sx={{ width: 160 }}
        />
        <Button
          variant="outlined"
          size="small"
          onClick={() => {
            const d = addDays(selectedDate, -1)
            if (!dataHorizon) {
              setSelectedDate(d)
              return
            }
            const allowed = dataHorizon.allowedDays.size > 0 ? dataHorizon.allowedDays : null
            const clamped = isDateAllowed(d, dataHorizon.minDate, allowed)
              ? d
              : nearestPreviousAllowedDate(d, dataHorizon.allowedDaysAsc, dataHorizon.minDate)
            setSelectedDate(clamped)
          }}
        >
          Previous day
        </Button>
        <Button
          variant="outlined"
          size="small"
          onClick={() => {
            const d = addDays(selectedDate, 1)
            if (!dataHorizon) {
              setSelectedDate(d)
              return
            }
            const allowed = dataHorizon.allowedDays.size > 0 ? dataHorizon.allowedDays : null
            const clamped = isDateAllowed(d, dataHorizon.minDate, allowed)
              ? d
              : nearestPreviousAllowedDate(d, dataHorizon.allowedDaysAsc, dataHorizon.minDate)
            setSelectedDate(clamped)
          }}
        >
          Next day
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
        <CompetitionAccordion
          events={events}
          selectedDate={selectedDate}
          onSelectEvent={onSelectEvent}
        />
      )}
    </Box>
  )
}
