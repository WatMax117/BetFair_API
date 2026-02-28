import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import Dialog from '@mui/material/Dialog'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessSharpIcon from '@mui/icons-material/ExpandLessSharp'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs'
import { DateCalendar } from '@mui/x-date-pickers/DateCalendar'
import { fetchEventsByDateSnapshots, fetchDataHorizon } from '../api'
import type { EventItem } from '../api'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import 'dayjs/locale/en-gb'

dayjs.extend(utc)

const ACCENT_GREEN = 'rgb(102, 204, 153)'

/** Sticky header: fixed height; corridor + 1px bottom border. */
const CORRIDOR_H = 42
const HEADER_H = CORRIDOR_H + 1 // 43 (42px corridor + 1px border)

const ARROW_SIZE = 42

/** Arrow buttons: strict 42×42 box, no padding. Override MUI defaults. */
const arrowBtnSx = {
  width: ARROW_SIZE,
  minWidth: ARROW_SIZE,
  height: ARROW_SIZE,
  minHeight: ARROW_SIZE,
  maxHeight: ARROW_SIZE,
  p: 0,
  borderRadius: 0,
  boxSizing: 'border-box' as const,
  border: 'none',
  bgcolor: 'transparent',
  boxShadow: 'none',
  color: ACCENT_GREEN,
  opacity: 0.7,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'opacity 160ms ease',
  '& svg': {
    transformOrigin: 'center',
    display: 'block',
  },
  '&:hover': {
    opacity: 1,
    color: ACCENT_GREEN,
    bgcolor: 'transparent',
  },
} as const

/** Arrow icon: 42×42; scale inner path so arrow reaches closer to edges. */
const arrowIconSx = {
  width: ARROW_SIZE,
  height: ARROW_SIZE,
  fontSize: ARROW_SIZE,
  display: 'block' as const,
  lineHeight: 1,
  '& path': {
    transformOrigin: 'center',
    transformBox: 'fill-box',
    transform: 'scale(1.18)',
  },
} as const

/** Today's date in UTC as YYYY-MM-DD. Uses UTC date parts to avoid local↔UTC shift. */
function getTodayUTC(): string {
  const d = new Date()
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Add N days to a YYYY-MM-DD string, return YYYY-MM-DD. */
function addDays(dateStr: string, n: number): string {
  const d = new Date(dateStr + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Allowed = (date >= minDate) AND (today UTC is always allowed when >= minDate) AND (no days list yet OR day is in allowedDays). */
function isDateAllowed(
  date: string,
  minDate: string,
  allowedDays: Set<string> | null
): boolean {
  if (date < minDate) return false
  if (date === getTodayUTC() && date >= minDate) return true
  if (!allowedDays || allowedDays.size === 0) return true
  return allowedDays.has(date)
}

/** Nearest allowed date: largest allowed date <= date, or earliest allowed if date is before all. */
function nearestAllowedDate(
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

/** Format number; "—" for null/undefined/NaN. Valid 0 displays as "0.00". */
function num(v: number | null | undefined): string {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  return Number.isInteger(v) ? String(v) : Number(v).toFixed(2)
}

/** Picker theme: green primary (replaces default blue) for all calendar states. */
const pickerTheme = createTheme({
  palette: {
    primary: { main: '#66cc99' },
  },
  components: {
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
  },
})

/** Picker sx overrides: text color, remove blue from today/focus, year/month selection. */
const pickerThemeSx = {
  '& .MuiPickersCalendarHeader-root': { color: '#bababa' },
  '& .MuiPickersCalendarHeader-labelContainer': { color: '#bababa' },
  '& .MuiDayCalendar-weekDayLabel': { color: '#bababa' },
  '& .MuiPickersDay-root': {
    color: '#bababa',
    '&:hover': { backgroundColor: 'rgba(102, 204, 153, 0.15)' },
  },
  '& .MuiPickersDay-root.Mui-selected': {
    backgroundColor: '#66cc99',
    color: '#303844',
  },
  '& .MuiPickersDay-root.Mui-selected:hover': {
    backgroundColor: 'rgba(102, 204, 153, 0.9)',
  },
  '& .MuiPickersDay-today': {
    border: '2px solid #66cc99',
  },
  '& .MuiPickersDay-root.Mui-selected.MuiPickersDay-today': {
    border: '2px solid #66cc99',
    backgroundColor: '#66cc99',
  },
  '& .MuiPickersDay-root:focus, & .MuiPickersDay-root.Mui-focusVisible': {
    outline: 'none',
    backgroundColor: 'transparent',
  },
  '& .MuiPickersArrowSwitcher-button': {
    color: '#bababa',
    borderRadius: 6,
    '&:hover': { backgroundColor: 'rgba(102, 204, 153, 0.15)' },
  },
  '& .MuiPickersCalendarHeader-root .MuiIconButton-root': {
    color: '#bababa',
    borderRadius: 6,
    '&:hover': { backgroundColor: 'rgba(102, 204, 153, 0.15)' },
  },
  '& .MuiIconButton-root': { color: '#bababa' },
  '& .MuiPickersYear-yearButton': {
    color: '#bababa',
    '&:hover': { backgroundColor: 'rgba(102, 204, 153, 0.15)' },
  },
  '& .MuiPickersYear-yearButton.Mui-selected': {
    backgroundColor: '#66cc99',
    color: '#303844',
  },
  '& .MuiPickersYear-yearButton.Mui-selected:hover': {
    backgroundColor: 'rgba(102, 204, 153, 0.9)',
  },
  '& .MuiPickersMonth-monthButton': {
    color: '#bababa',
    '&:hover': { backgroundColor: 'rgba(102, 204, 153, 0.15)' },
  },
  '& .MuiPickersMonth-monthButton.Mui-selected': {
    backgroundColor: '#66cc99',
    color: '#303844',
  },
}

function DatePickerButton({
  selectedDate,
  dataHorizon,
  isDateAllowed,
  nearestAllowedDate,
}: {
  selectedDate: string
  dataHorizon: { minDate: string; allowedDays: Set<string>; allowedDaysAsc: string[] } | null
  isDateAllowed: (date: string, minDate: string, allowedDays: Set<string> | null) => boolean
  nearestAllowedDate: (date: string, allowedDaysAsc: string[], minDate: string) => string
}) {
  const [open, setOpen] = useState(false)
  const [displayMonth, setDisplayMonth] = useState(() => dayjs.utc(selectedDate))

  useEffect(() => {
    if (open) setDisplayMonth(dayjs.utc(selectedDate))
  }, [open, selectedDate])

  const handleMonthChange = useCallback((month: dayjs.Dayjs) => {
    setDisplayMonth(month)
  }, [])

  const handleDateChange = useCallback(
    (d: dayjs.Dayjs | null) => {
      if (!d) return
      const dateStr = d.utc().format('YYYY-MM-DD')
      const clamped = !dataHorizon
        ? dateStr
        : (() => {
            const allowed = dataHorizon.allowedDays.size > 0 ? dataHorizon.allowedDays : null
            return isDateAllowed(dateStr, dataHorizon.minDate, allowed)
              ? dateStr
              : nearestAllowedDate(dateStr, dataHorizon.allowedDaysAsc, dataHorizon.minDate)
          })()
      window.open(`/stream?date=${clamped}`, '_blank', 'noopener,noreferrer')
      setOpen(false)
    },
    [dataHorizon, isDateAllowed, nearestAllowedDate]
  )

  const minDate = dataHorizon?.minDate ? dayjs.utc(dataHorizon.minDate) : undefined

  const calBtnRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const btn = calBtnRef.current
    if (!btn) return

    const apply = () => {
      const styles = getComputedStyle(btn)
      const padTop = parseFloat(styles.paddingTop) || 0
      const padBot = parseFloat(styles.paddingBottom) || 0
      const H = btn.clientHeight - padTop - padBot

      const block = btn.querySelector<HTMLElement>('.calTextBlock')
      if (block) {
        const gapPx = parseFloat(getComputedStyle(block).gap) || 3
        const S = (H - gapPx) / 2
        block.style.fontSize = `${S}px`
        block.style.lineHeight = '1'
      }
    }

    apply()
    const ro = new ResizeObserver(apply)
    ro.observe(btn)
    return () => ro.disconnect()
  }, [selectedDate])

  return (
    <>
      <Box
        ref={calBtnRef}
        component="button"
        type="button"
        onClick={() => setOpen(true)}
        sx={{
          height: CORRIDOR_H,
          minHeight: CORRIDOR_H,
          p: 0,
          border: 'none',
          bgcolor: 'transparent',
          boxShadow: 'none',
          cursor: 'pointer',
          userSelect: 'none',
          display: 'flex',
          alignItems: 'stretch',
          justifyContent: 'center',
          fontFamily: '"DSEG7ModernMini", monospace',
          fontWeight: 700,
          fontStyle: 'italic',
          color: '#bababa',
        }}
      >
        <Box
          className="calTextBlock"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            justifyContent: 'flex-start',
            alignItems: 'flex-start',
            gap: 'var(--segStroke)',
            lineHeight: 1,
            p: 0,
            m: 0,
            font: 'inherit',
          }}
        >
          <Box component="span" className="calLine calLine1" sx={{ fontFamily: '"DSEG7ModernMini", monospace', fontWeight: 700, fontStyle: 'italic', lineHeight: 1, p: 0, m: 0 }}>
            {dayjs.utc(selectedDate).format('MM/DD')}
          </Box>
          <Box component="span" className="calLine calLine2" sx={{ fontFamily: '"DSEG7ModernMini", monospace', fontWeight: 700, fontStyle: 'italic', lineHeight: 1, p: 0, m: 0 }}>
            {dayjs.utc(selectedDate).format('YYYY')}
          </Box>
        </Box>
      </Box>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        disableEnforceFocus
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            bgcolor: '#303844',
            borderRadius: '8px',
            overflow: 'auto',
            m: 2,
            maxHeight: 'calc(100vh - 32px)',
          },
        }}
        slotProps={{
          backdrop: { sx: { bgcolor: 'rgba(0,0,0,0.6)' } },
        }}
      >
        <Box sx={{ p: { xs: 1.5, sm: 2 }, overflow: 'auto' }}>
          <ThemeProvider theme={pickerTheme}>
            <LocalizationProvider dateAdapter={AdapterDayjs} adapterLocale="en-gb">
              <DateCalendar
                value={dayjs.utc(selectedDate)}
                referenceDate={displayMonth}
                onMonthChange={handleMonthChange}
                onChange={handleDateChange}
                views={['day', 'month', 'year']}
                minDate={minDate}
                maxDate={dayjs.utc(getTodayUTC())}
                sx={[
                  pickerThemeSx,
                  {
                    minWidth: 280,
                    width: '100%',
                    boxSizing: 'border-box',
                    '& .MuiDayCalendar-header': {
                      width: '100%',
                      margin: 0,
                    },
                    '& .MuiDayCalendar-weekContainer': {
                      width: '100%',
                      margin: 0,
                    },
                    '& .MuiPickersSlideTransition-root': {
                      width: '100%',
                    },
                  },
                ]}
                slotProps={{
                  previousIconButton: { 'aria-label': 'Previous month' },
                  nextIconButton: { 'aria-label': 'Next month' },
                }}
              />
            </LocalizationProvider>
          </ThemeProvider>
        </Box>
      </Dialog>
    </>
  )
}

/** Group events by competition. Sort accordion sections: by event count desc, then competition name A–Z. Events within each: volume desc. */
export function CompetitionAccordion({
  events,
  selectedDate,
  openIds,
  onOpenIdsChange,
}: {
  events: EventItem[]
  selectedDate: string
  openIds: Set<string>
  onOpenIdsChange: (next: Set<string>) => void
}) {

  const handleHeaderClick = useCallback(
    (competitionId: string) => {
      onOpenIdsChange(
        (() => {
          const next = new Set(openIds)
          if (next.has(competitionId)) next.delete(competitionId)
          else next.add(competitionId)
          return next
        })()
      )
    },
    [openIds, onOpenIdsChange]
  )

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
    const comps = [...byComp.entries()].map(([name, evs]) => {
      const countryCode = evs[0]?.country_code ?? ''
      const competitionId = evs[0]?.competition_id ?? `${countryCode || 'x'}-${name}`
      return {
        name,
        competitionId,
        countryCode,
        events: evs,
        eventsCountToday: evs.length,
      }
    })
    comps.sort((a, b) => {
      // 1) By number of events (desc – most events first)
      if (b.eventsCountToday !== a.eventsCountToday) return b.eventsCountToday - a.eventsCountToday
      // 2) Then alphabetically by competition name
      return (a.name || '').localeCompare(b.name || '')
    })
    if (typeof window !== 'undefined' && import.meta.env?.DEV) {
      const sample = comps.slice(0, 10).map((c) => ({
        competitionName: c.name,
        competitionId: c.competitionId,
        eventsCountToday: c.eventsCountToday,
      }))
      console.log('[CompetitionAccordion] sort sample', sample)
    }
    return comps.map((c, i) => ({
      ...c,
      isFirstInCountry: i === 0 || comps[i - 1].countryCode !== c.countryCode,
    }))
  }, [events])

  if (events.length === 0) {
    return (
      <Typography variant="body2" sx={{ color: '#bababa' }}>
        No events for {selectedDate} (UTC) with streaming data.
      </Typography>
    )
  }

  const BASE = 4 // px: same-country 4px, different-country 8px, after-expanded 16px
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
      {grouped.map(({ name, competitionId, events: evs, isFirstInCountry }, index) => {
        const isOpen = openIds.has(competitionId)
        const prevExpanded = index > 0 && openIds.has(grouped[index - 1].competitionId)
        const mt: string | number =
          index === 0
            ? 0
            : prevExpanded
              ? `${BASE * 4}px`   // 16px after expanded
              : isFirstInCountry
                ? `${BASE * 2}px` // 8px different country
                : `${BASE}px`     // 4px same country
        return (
        <Accordion
          key={competitionId}
          expanded={isOpen}
          onChange={() => handleHeaderClick(competitionId)}
          disableGutters
          sx={{
            m: 0,
            mt,
            borderRadius: '6px',
            border: '1px solid rgba(255,255,255,0.04)',
            boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
            '&:before': { display: 'none' },
            '&.Mui-expanded': { m: 0, mt },
            overflow: 'hidden',
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon sx={{ color: '#bababa' }} />}
            sx={{
              bgcolor: '#454b56',
              color: '#bababa',
              minHeight: 40,
              '& .MuiAccordionSummary-content': { my: 1 },
              '&:hover': {
                bgcolor: '#4a515c',
              },
            }}
          >
            <Typography sx={{ color: '#bababa' }}>
              {name} ({evs.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0, bgcolor: '#454b56' }}>
            <Table size="small">
              <TableHead>
                <TableRow
                  sx={{
                    '& th': {
                      borderBottom: '3px solid #66cc99',
                    },
                  }}
                >
                  <TableCell sx={{ color: '#bababa' }}>Event</TableCell>
                  <TableCell align="right" sx={{ color: '#bababa' }}>H Book Risk (15m)</TableCell>
                  <TableCell align="right" sx={{ color: '#bababa' }}>A Book Risk (15m)</TableCell>
                  <TableCell align="right" sx={{ color: '#bababa' }}>D Book Risk (15m)</TableCell>
                  <TableCell align="right" sx={{ color: '#bababa' }}>Impedance (15m)</TableCell>
                  <TableCell align="right" sx={{ color: '#bababa' }}>Volume</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {evs.map((e) => (
                  <TableRow
                    key={e.market_id}
                    hover
                    sx={{ cursor: 'pointer', color: '#bababa' }}
                    onClick={(ev) => {
                      ev.preventDefault()
                      ev.stopPropagation()
                      window.open(`/stream/event/${e.market_id}?date=${selectedDate}`, '_blank', 'noopener,noreferrer')
                    }}
                  >
                    <TableCell sx={{ color: '#bababa' }}>{e.event_name || e.market_id}</TableCell>
                    <TableCell align="right" sx={{ color: '#bababa' }}>{num(e.home_book_risk_l3)}</TableCell>
                    <TableCell align="right" sx={{ color: '#bababa' }}>{num(e.away_book_risk_l3)}</TableCell>
                    <TableCell align="right" sx={{ color: '#bababa' }}>{num(e.draw_book_risk_l3)}</TableCell>
                    <TableCell align="right" sx={{ color: '#bababa' }}>{num(e.impedance_index_15m)}</TableCell>
                    <TableCell align="right" sx={{ color: '#bababa' }}>{num(e.total_volume)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </AccordionDetails>
        </Accordion>
      )})}
    </Box>
  )
}

export function LeaguesAccordion({ 
  onDateChange 
}: { 
  onDateChange?: (date: string) => void
}) {
  const [searchParams] = useSearchParams()
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const dateParam = searchParams.get('date')
    if (dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam)) return dateParam
    return getTodayUTC()
  })
  const [events, setEvents] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openIds, setOpenIds] = useState<Set<string>>(() => new Set())
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
    setOpenIds(new Set())
  }, [selectedDate])

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
          if (isDateAllowed(prev, minDate, allowedDays.size > 0 ? allowedDays : null)) return prev
          return nearestAllowedDate(prev, allowedDaysAsc, minDate)
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

  useEffect(() => {
    const t = setTimeout(() => {
      const header = document.querySelector('[data-testid="header-root"]') as HTMLElement | null
      const btn = document.querySelector('[data-testid="arrow-left"]') as HTMLElement | null
      if (!header || !btn) return

      const headerStyles = getComputedStyle(header)
      console.log('=== A/B. HEADER (root) ===')
      console.log('  offsetHeight:', header.offsetHeight, 'clientHeight:', header.clientHeight)
      console.log('  display:', headerStyles.display, 'alignItems:', headerStyles.alignItems)
      console.log('  height:', headerStyles.height, 'minHeight:', headerStyles.minHeight)
      console.log('  paddingTop:', headerStyles.paddingTop, 'paddingBottom:', headerStyles.paddingBottom)
      console.log('  overflow:', headerStyles.overflow)

      const btnStyles = getComputedStyle(btn)
      console.log('')
      console.log('=== A. ARROW BUTTON (MuiIconButton-root) ===')
      console.log('  width:', btnStyles.width, 'height:', btnStyles.height)
      console.log('  minWidth:', btnStyles.minWidth, 'minHeight:', btnStyles.minHeight)
      console.log('  padding:', btnStyles.padding, '| top:', btnStyles.paddingTop, 'right:', btnStyles.paddingRight, 'bottom:', btnStyles.paddingBottom, 'left:', btnStyles.paddingLeft)
      console.log('  boxSizing:', btnStyles.boxSizing)
      console.log('  lineHeight:', btnStyles.lineHeight)
      console.log('  display:', btnStyles.display, 'alignItems:', btnStyles.alignItems, 'justifyContent:', btnStyles.justifyContent)
      console.log('  position:', btnStyles.position, 'top:', btnStyles.top, 'left:', btnStyles.left)
      console.log('  overflow:', btnStyles.overflow)
      console.log('  offsetWidth:', btn.offsetWidth, 'offsetHeight:', btn.offsetHeight)
      console.log('  clientWidth:', btn.clientWidth, 'clientHeight:', btn.clientHeight)
      console.log('  className:', btn.className)

      const parent = btn.parentElement
      if (parent) {
        const parentStyles = getComputedStyle(parent)
        console.log('')
        console.log('=== B. PARENT (controls Box) ===')
        console.log('  display:', parentStyles.display, 'alignItems:', parentStyles.alignItems)
        console.log('  height:', parentStyles.height, 'minHeight:', parentStyles.minHeight)
        console.log('  overflow:', parentStyles.overflow)
      }
      const grandparent = parent?.parentElement
      if (grandparent) {
        const gpStyles = getComputedStyle(grandparent)
        console.log('')
        console.log('=== B. GRANDPARENT (header grid) ===')
        console.log('  display:', gpStyles.display, 'alignItems:', gpStyles.alignItems)
        console.log('  height:', gpStyles.height)
      }

      const svg = btn.querySelector('svg')
      if (svg) {
        const svgStyles = getComputedStyle(svg)
        const rect = svg.getBoundingClientRect()
        console.log('')
        console.log('=== C. SVG ICON (MuiSvgIcon-root) ===')
        console.log('  computed width:', svgStyles.width, 'height:', svgStyles.height)
        console.log('  fontSize:', svgStyles.fontSize)
        console.log('  transform:', svgStyles.transform)
        console.log('  transformOrigin:', svgStyles.transformOrigin)
        console.log('  getBoundingClientRect:', { width: rect.width, height: rect.height })
      }

      console.log('')
      console.log('=== devicePixelRatio ===', window.devicePixelRatio)
    }, 200)
    return () => clearTimeout(t)
  }, [])

  return (
    <Box>
      <Box
        data-testid="header-root"
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          bgcolor: '#303844',
          '--segStroke': '3px',
          height: 'auto',
          minHeight: HEADER_H,
          py: 1,
          mb: 2,
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'grid',
          alignItems: 'stretch',
          columnGap: { xs: 1.5, sm: 2.5 },
          rowGap: { xs: 1.5, sm: 0 },
          gridTemplateColumns: { xs: 'minmax(0,1fr) auto', sm: 'auto auto 1fr' },
          gridTemplateAreas: {
            xs: `"date logo" "controls controls"`,
            sm: `"date controls logo"`,
          },
        }}
      >
        <Box sx={{ gridArea: 'date', minWidth: 0, justifySelf: 'start', color: '#bababa', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: '"DSEG7ModernMini", monospace' }}>
          <DatePickerButton
            selectedDate={selectedDate}
            dataHorizon={dataHorizon}
            isDateAllowed={isDateAllowed}
            nearestAllowedDate={nearestAllowedDate}
          />
        </Box>
        <Box
          sx={{
            gridArea: 'controls',
            display: 'flex',
            gap: 1,
            alignItems: 'stretch',
            justifyContent: { xs: 'space-between', sm: 'flex-start' },
            minHeight: CORRIDOR_H,
          }}
        >
        <IconButton
          data-testid="arrow-left"
          aria-label="Previous day"
          onClick={() => {
            const d = addDays(selectedDate, -1)
            if (!dataHorizon) {
              setSelectedDate(d)
              return
            }
            const allowed = dataHorizon.allowedDays.size > 0 ? dataHorizon.allowedDays : null
            const clamped = isDateAllowed(d, dataHorizon.minDate, allowed)
              ? d
              : nearestAllowedDate(d, dataHorizon.allowedDaysAsc, dataHorizon.minDate)
            setSelectedDate(clamped)
          }}
          sx={arrowBtnSx}
        >
          <ExpandLessSharpIcon sx={{ ...arrowIconSx, transform: 'rotate(-90deg)' }} />
        </IconButton>
        <IconButton
          aria-label="Next day"
          onClick={() => {
            const d = addDays(selectedDate, 1)
            if (!dataHorizon) {
              setSelectedDate(d)
              return
            }
            const allowed = dataHorizon.allowedDays.size > 0 ? dataHorizon.allowedDays : null
            const clamped = isDateAllowed(d, dataHorizon.minDate, allowed)
              ? d
              : nearestAllowedDate(d, dataHorizon.allowedDaysAsc, dataHorizon.minDate)
            setSelectedDate(clamped)
          }}
          sx={arrowBtnSx}
        >
          <ExpandLessSharpIcon sx={{ ...arrowIconSx, transform: 'rotate(90deg)' }} />
        </IconButton>
        <Tooltip title="Volume: events for this day sorted by volume">
          <IconButton
            aria-label="Open Volume (events by volume) in new tab"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              window.open(`/stream/expanded?date=${selectedDate}`, '_blank', 'noopener,noreferrer')
            }}
            sx={arrowBtnSx}
          >
            <ExpandLessSharpIcon sx={{ ...arrowIconSx, transform: 'rotate(180deg)' }} />
          </IconButton>
        </Tooltip>
        <Tooltip title={openIds.size === 0 ? 'No sections to collapse' : 'Collapse all sections'}>
          <IconButton
            aria-label="Collapse all sections"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              if (openIds.size === 0) return
              setOpenIds(new Set())
            }}
            sx={arrowBtnSx}
          >
            <ExpandLessSharpIcon sx={arrowIconSx} />
          </IconButton>
        </Tooltip>
        </Box>
        <Box sx={{ gridArea: 'logo', justifySelf: 'end' }}>
          <Typography
            component="span"
            sx={{
              fontFamily: '"DSEG7ModernMini", monospace',
              fontWeight: 700,
              fontStyle: 'italic',
              color: '#C47A7A',
              fontSize: CORRIDOR_H,
              lineHeight: 1,
              height: CORRIDOR_H,
              p: 0,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            FHRH
          </Typography>
        </Box>
      </Box>

      {error && (
        <Typography sx={{ mb: 1, color: '#f44336' }}>
          {error}
        </Typography>
      )}

      {loading ? (
        <Typography sx={{ color: '#bababa' }}>Loading…</Typography>
      ) : (
        <CompetitionAccordion
          events={events}
          selectedDate={selectedDate}
          openIds={openIds}
          onOpenIdsChange={setOpenIds}
        />
      )}
    </Box>
  )
}
