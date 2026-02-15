import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import Button from '@mui/material/Button'
import Box from '@mui/material/Box'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import Switch from '@mui/material/Switch'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import SearchIcon from '@mui/icons-material/Search'
import { EventsTable } from './EventsTable'
import { SortedEventsList, loadSortState, type SortState } from './SortedEventsList'
import { fetchLeagues, fetchLeagueEvents, fetchBookRiskFocusEvents } from '../api'
import type { LeagueItem, EventItem } from '../api'

/** Event filter mode: upcoming only, live + upcoming, or all (last 48h + next 48h). */
export type EventFilterMode = 'upcoming' | 'live_and_upcoming' | 'all'

function getFilterWindow(mode: EventFilterMode): { from: Date; to: Date; includeInPlay: boolean; inPlayLookbackHours: number } {
  const now = new Date()
  const h = 60 * 60 * 1000
  switch (mode) {
    case 'upcoming':
      return { from: now, to: new Date(now.getTime() + 48 * h), includeInPlay: false, inPlayLookbackHours: 0 }
    case 'live_and_upcoming':
      return { from: new Date(now.getTime() - 2 * h), to: new Date(now.getTime() + 48 * h), includeInPlay: true, inPlayLookbackHours: 2 }
    case 'all':
      return { from: new Date(now.getTime() - 48 * h), to: new Date(now.getTime() + 48 * h), includeInPlay: true, inPlayLookbackHours: 48 }
    default:
      return getFilterWindow('upcoming')
  }
}

const FILTER_MODE_LABELS: Record<EventFilterMode, string> = {
  upcoming: 'Upcoming',
  'live_and_upcoming': 'Live + Upcoming',
  all: 'All (last 48h + next 48h)',
}

const DEFAULT_LIMIT = 100

export function LeaguesAccordion({ onSelectEvent }: { onSelectEvent: (e: EventItem) => void }) {
  const [eventFilterMode, setEventFilterMode] = useState<EventFilterMode>('upcoming')
  const [search, setSearch] = useState('')
  const [searchApplied, setSearchApplied] = useState<string | null>(null)
  const [leagues, setLeagues] = useState<LeagueItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedLeague, setExpandedLeague] = useState<string | null>(null)
  const [eventsByLeague, setEventsByLeague] = useState<Record<string, EventItem[]>>({})
  const [loadingEvents, setLoadingEvents] = useState<Record<string, boolean>>({})
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [bookRiskFocus, setBookRiskFocus] = useState(false)
  const [focusEvents, setFocusEvents] = useState<EventItem[]>([])
  const [loadingFocus, setLoadingFocus] = useState(false)
  const [sortState, setSortState] = useState<SortState>(loadSortState)
  const [onlyActiveInPlay, setOnlyActiveInPlay] = useState(true)
  const [onlyMarketsWithBookRisk, setOnlyMarketsWithBookRisk] = useState(true)

  const { from, to, includeInPlay, inPlayLookbackHours } = useMemo(() => getFilterWindow(eventFilterMode), [eventFilterMode])

  const loadLeaguesRequestIdRef = useRef(0)

  const loadLeagues = useCallback(async () => {
    const requestId = ++loadLeaguesRequestIdRef.current
    setLoading(true)
    setError(null)
    try {
      const data = await fetchLeagues(
        from,
        to,
        searchApplied ?? undefined,
        includeInPlay,
        inPlayLookbackHours,
        DEFAULT_LIMIT,
        0
      )
      if (requestId !== loadLeaguesRequestIdRef.current) {
        console.warn('[LeaguesAccordion] Ignoring stale leagues response', { requestId, current: loadLeaguesRequestIdRef.current })
        return
      }
      const list = Array.isArray(data) ? data : (data && Array.isArray((data as { items?: unknown }).items) ? (data as { items: LeagueItem[] }).items : [])
      if (!Array.isArray(data)) {
        console.warn('[LeaguesAccordion] API response was not an array; normalized to list', { data, list })
      }
      console.log('[LeaguesAccordion] setLeagues called', { count: list.length, sample: list.slice(0, 2) })
      setLeagues(list)
    } catch (e) {
      if (requestId === loadLeaguesRequestIdRef.current) {
        setError(e instanceof Error ? e.message : 'Failed to load leagues')
      }
    } finally {
      if (requestId === loadLeaguesRequestIdRef.current) {
        setLoading(false)
      }
    }
  }, [from.getTime(), to.getTime(), searchApplied, eventFilterMode, refreshTrigger])

  const handleSearch = useCallback(() => {
    setSearchApplied(search.trim() || '')
    setLeagues([])
    setEventsByLeague({})
  }, [search])

  const handleRefresh = useCallback(() => {
    if (searchApplied !== null) {
      setRefreshTrigger((t) => t + 1)
    }
  }, [searchApplied])

  useEffect(() => {
    if (searchApplied !== null) {
      loadLeagues()
    }
  }, [searchApplied, loadLeagues])

  useEffect(() => {
    console.log('[LeaguesAccordion] render state', {
      searchApplied,
      loading,
      leaguesLength: leagues.length,
      leaguesIsArray: Array.isArray(leagues),
      firstItem: leagues[0],
    })
  }, [searchApplied, loading, leagues])

  const eventsByLeagueRef = useRef(eventsByLeague)
  eventsByLeagueRef.current = eventsByLeague

  const loadFocusEvents = useCallback(async () => {
    setLoadingFocus(true)
    try {
      const data = await fetchBookRiskFocusEvents(
        from,
        to,
        includeInPlay,
        inPlayLookbackHours,
        onlyMarketsWithBookRisk,
        500,
        0
      )
      setFocusEvents(data)
    } catch {
      setFocusEvents([])
    } finally {
      setLoadingFocus(false)
    }
  }, [from.getTime(), to.getTime(), includeInPlay, inPlayLookbackHours, onlyMarketsWithBookRisk])

  useEffect(() => {
    if (bookRiskFocus) {
      loadFocusEvents()
    } else {
      setFocusEvents([])
    }
  }, [bookRiskFocus, loadFocusEvents])

  const focusEventsFiltered = useMemo(() => {
    if (!onlyActiveInPlay) return focusEvents
    const now = new Date().toISOString()
    return focusEvents.filter((e) => (e.event_open_date ?? '') < now)
  }, [focusEvents, onlyActiveInPlay])

  const handleAccordionChange = useCallback(
    (league: string) => (_: React.SyntheticEvent, isExpanded: boolean) => {
      setExpandedLeague(isExpanded ? league : null)
      if (isExpanded && !eventsByLeagueRef.current[league]) {
        setLoadingEvents((prev) => ({ ...prev, [league]: true }))
        fetchLeagueEvents(league, from, to, includeInPlay, inPlayLookbackHours, DEFAULT_LIMIT, 0)
          .then((events) => {
            setEventsByLeague((prev) => ({ ...prev, [league]: events }))
          })
          .catch(() => {})
          .finally(() => {
            setLoadingEvents((prev) => ({ ...prev, [league]: false }))
          })
      }
    },
    [from, to, includeInPlay, inPlayLookbackHours]
  )

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Risk Analytics — Leagues
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2, alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="event-filter-label">Events</InputLabel>
          <Select
            labelId="event-filter-label"
            id="event-filter-mode"
            value={eventFilterMode}
            label="Events"
            onChange={(e) => {
              setEventFilterMode(e.target.value as EventFilterMode)
              setEventsByLeague({})
            }}
          >
            <MenuItem value="upcoming">{FILTER_MODE_LABELS.upcoming}</MenuItem>
            <MenuItem value="live_and_upcoming">{FILTER_MODE_LABELS.live_and_upcoming}</MenuItem>
            <MenuItem value="all">{FILTER_MODE_LABELS.all}</MenuItem>
          </Select>
        </FormControl>
        <Typography variant="body2" color="text.secondary" sx={{ alignSelf: 'center' }}>
          {eventFilterMode === 'upcoming' && 'Showing upcoming events'}
          {eventFilterMode === 'live_and_upcoming' && 'Showing live + upcoming'}
          {eventFilterMode === 'all' && 'Showing last 48h + next 48h'}
        </Typography>
        <TextField
          size="small"
          label="Search (team / event)"
          placeholder="Enter term or leave blank"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          sx={{ width: 220 }}
        />
        <Button variant="contained" startIcon={<SearchIcon />} onClick={handleSearch}>
          Search
        </Button>
        {searchApplied !== null && (
          <Button variant="outlined" onClick={handleRefresh} disabled={loading}>
            Refresh
          </Button>
        )}
        <FormControlLabel
          control={
            <Switch
              checked={bookRiskFocus}
              onChange={(e) => setBookRiskFocus(e.target.checked)}
              color="primary"
            />
          }
          label="Book Risk focus (sortable list)"
        />
      </Box>

      {error && (
        <Typography color="error" sx={{ mb: 1 }}>
          {error}
        </Typography>
      )}

      {searchApplied === null ? (
        <Typography color="text.secondary" sx={{ py: 3 }}>
          Enter a search term (or leave blank) and click Search to load leagues. Data is lazy-loaded: events are fetched only when you expand a league. Max 100 results per request.
        </Typography>
      ) : loading ? (
        <Typography color="text.secondary">Loading leagues…</Typography>
      ) : !Array.isArray(leagues) || leagues.length === 0 ? (
        <Typography color="text.secondary" component="span" sx={{ display: 'block' }}>
          No leagues in the selected window. Queried {from.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })} – {to.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}. Try the All filter to include past events or a different search.
        </Typography>
      ) : (
        <>
        {leagues.length >= DEFAULT_LIMIT && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            Showing up to {DEFAULT_LIMIT} leagues. Narrow your search for more specific results.
          </Typography>
        )}
        {(Array.isArray(leagues) ? leagues : []).map((item) => {
          const league = item?.league ?? ''
          const event_count = item?.event_count ?? 0
          return (
          <Accordion
            key={league}
            expanded={expandedLeague === league}
            onChange={handleAccordionChange(league)}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography fontWeight="medium">{league}</Typography>
              <Typography sx={{ color: 'text.secondary', ml: 1 }}>
                ({event_count} event{event_count !== 1 ? 's' : ''})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              {loadingEvents[league] ? (
                <Typography color="text.secondary">Loading events…</Typography>
              ) : (
                <EventsTable
                  events={eventsByLeague[league] || []}
                  onSelectEvent={onSelectEvent}
                  showLimitNote={(eventsByLeague[league]?.length ?? 0) >= DEFAULT_LIMIT}
                />
              )}
            </AccordionDetails>
          </Accordion>
          )
        })}
        </>
      )}

      {bookRiskFocus && (
        <>
          {loadingFocus ? (
            <Typography color="text.secondary" sx={{ mt: 2 }}>Loading focus list…</Typography>
          ) : (
            <SortedEventsList
              events={focusEventsFiltered}
              sortState={sortState}
              onSortChange={setSortState}
              onSelectEvent={onSelectEvent}
              onlyActiveInPlay={onlyActiveInPlay}
              onOnlyActiveChange={setOnlyActiveInPlay}
              onlyMarketsWithBookRisk={onlyMarketsWithBookRisk}
              onOnlyMarketsWithBookRiskChange={setOnlyMarketsWithBookRisk}
            />
          )}
        </>
      )}
    </Box>
  )
}
