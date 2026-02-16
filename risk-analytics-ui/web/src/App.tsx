import { useState, useCallback } from 'react'
import Box from '@mui/material/Box'
import { LeaguesAccordion } from './components/LeaguesAccordion'
import { EventDetail } from './components/EventDetail'
import type { EventItem } from './api'

export default function App() {
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const handleSelectEvent = useCallback((event: EventItem | null, date?: string) => {
    setSelectedEvent(event)
    if (date) {
      setSelectedDate(date)
    }
  }, [])

  if (selectedEvent) {
    return (
      <Box sx={{ p: 2 }}>
        <EventDetail
          marketId={selectedEvent.market_id}
          eventName={selectedEvent.event_name}
          competitionName={selectedEvent.competition_name}
          eventOpenDate={selectedEvent.event_open_date}
          selectedDate={selectedDate}
          onBack={() => setSelectedEvent(null)}
        />
      </Box>
    )
  }

  return (
    <Box sx={{ p: 2, maxWidth: 1400, mx: 'auto' }}>
      <LeaguesAccordion onSelectEvent={(event) => handleSelectEvent(event)} onDateChange={setSelectedDate} />
    </Box>
  )
}
