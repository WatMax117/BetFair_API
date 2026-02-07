import { useState, useCallback, useEffect } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import Typography from '@mui/material/Typography'
import TextField from '@mui/material/TextField'
import Button from '@mui/material/Button'
import Box from '@mui/material/Box'
import FormControlLabel from '@mui/material/FormControlLabel'
import Switch from '@mui/material/Switch'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RefreshIcon from '@mui/icons-material/Refresh'
import { EventsTable } from './EventsTable'
import { fetchLeagues, fetchLeagueEvents } from '../api'
import type { LeagueItem, EventItem } from '../api'

const DEFAULT_WINDOW_HOURS = 24
const DEFAULT_EXTREME_INDEX_THRESHOLD = 500
const DEFAULT_IN_PLAY_LOOKBACK_HOURS = 6

function getWindowDates(hours: number): { from: Date; to: Date } {
  const now = new Date()
  const from = new Date(now)
  const to = new Date(now.getTime() + hours * 60 * 60 * 1000)
  return { from, to }
}

export function LeaguesAccordion({ onSelectEvent }: { onSelectEvent: (e: EventItem) => void }) {
  const [windowHours, setWindowHours] = useState(DEFAULT_WINDOW_HOURS)
  const [search, setSearch] = useState('')
  const [searchApplied, setSearchApplied] = useState('')
  const [includeInPlay, setIncludeInPlay] = useState(true)
  const [inPlayLookbackHours, setInPlayLookbackHours] = useState(DEFAULT_IN_PLAY_LOOKBACK_HOURS)
  const [extremeThreshold, setExtremeThreshold] = useState(DEFAULT_EXTREME_INDEX_THRESHOLD)
  const [leagues, setLeagues] = useState<LeagueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedLeague, setExpandedLeague] = useState<string | null>(null)
  const [eventsByLeague, setEventsByLeague] = useState<Record<string, EventItem[]>>({})
  const [loadingEvents, setLoadingEvents] = useState<Record<string, boolean>>({})
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const { from, to } = getWindowDates(windowHours)

  const loadLeagues = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchLeagues(
        from,
        to,
        searchApplied || undefined,
        includeInPlay,
        inPlayLookbackHours
      )
      setLeagues(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load leagues')
    } finally {
      setLoading(false)
    }
  }, [from.getTime(), to.getTime(), searchApplied, includeInPlay, inPlayLookbackHours, refreshTrigger])

  useEffect(() => {
    loadLeagues()
  }, [loadLeagues])

  const handleRefresh = () => {
    setSearchApplied(search)
    setRefreshTrigger((t) => t + 1)
  }

  const handleAccordionChange = useCallback(
    (league: string) => (_: React.SyntheticEvent, isExpanded: boolean) => {
      setExpandedLeague(isExpanded ? league : null)
      if (isExpanded && !eventsByLeague[league]) {
        setLoadingEvents((prev) => ({ ...prev, [league]: true }))
        fetchLeagueEvents(league, from, to, includeInPlay, inPlayLookbackHours)
          .then((events) => {
            setEventsByLeague((prev) => ({ ...prev, [league]: events }))
          })
          .catch(() => {})
          .finally(() => {
            setLoadingEvents((prev) => ({ ...prev, [league]: false }))
          })
      }
    },
    [from, to, includeInPlay, inPlayLookbackHours, eventsByLeague]
  )

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Risk Analytics — Leagues
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2, alignItems: 'center' }}>
        <TextField
          size="small"
          label="Time window (hours from now)"
          type="number"
          value={windowHours}
          onChange={(e) => setWindowHours(Number(e.target.value) || 24)}
          inputProps={{ min: 1, max: 168 }}
          sx={{ width: 180 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={includeInPlay}
              onChange={(e) => setIncludeInPlay(e.target.checked)}
              color="primary"
            />
          }
          label="Include in-play events"
        />
        {includeInPlay && (
          <TextField
            size="small"
            label="In-play lookback (hours)"
            type="number"
            value={inPlayLookbackHours}
            onChange={(e) => setInPlayLookbackHours(Number(e.target.value) || 0)}
            inputProps={{ min: 0, max: 168, step: 0.5 }}
            sx={{ width: 140 }}
          />
        )}
        <TextField
          size="small"
          label="Index highlight threshold"
          type="number"
          value={extremeThreshold}
          onChange={(e) => setExtremeThreshold(Number(e.target.value) || 0)}
          inputProps={{ min: 0, step: 50 }}
          sx={{ width: 160 }}
        />
        <TextField
          size="small"
          label="Search (team / event)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setSearchApplied(search)}
          sx={{ width: 220 }}
        />
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={handleRefresh}>
          Refresh
        </Button>
      </Box>

      {error && (
        <Typography color="error" sx={{ mb: 1 }}>
          {error}
        </Typography>
      )}

      {loading ? (
        <Typography color="text.secondary">Loading leagues…</Typography>
      ) : leagues.length === 0 ? (
        <Typography color="text.secondary">No leagues in the selected window.</Typography>
      ) : (
        leagues.map(({ league, event_count }) => (
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
                  extremeThreshold={extremeThreshold}
                />
              )}
            </AccordionDetails>
          </Accordion>
        ))
      )}
    </Box>
  )
}
