import { useState } from 'react'
import Box from '@mui/material/Box'
import { LeaguesAccordion } from './components/LeaguesAccordion'

export default function App() {
  const [, setSelectedDate] = useState<string | null>(null)

  return (
    <Box sx={{ p: 2, maxWidth: 1400, mx: 'auto', minHeight: '100vh', bgcolor: '#303844', colorScheme: 'dark' }}>
      <LeaguesAccordion onDateChange={setSelectedDate} />
    </Box>
  )
}
