import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material'
import App from './App'
import Box from '@mui/material/Box'
import { EventDetail } from './components/EventDetail'
import { ExpandedEventsPage } from './components/ExpandedEventsPage'
import { useNavigate } from 'react-router-dom'

function EventDetailPage() {
  const { marketId } = useParams<{ marketId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const date = searchParams.get('date') ?? undefined

  if (!marketId) {
    navigate('/stream', { replace: true })
    return null
  }

  return (
    <ThemeProvider theme={baseTheme}>
      <CssBaseline />
      <Box sx={{ p: 2, minHeight: '100vh' }}>
        <EventDetail
        marketId={marketId}
        eventName={null}
        competitionName={null}
        eventOpenDate={null}
        selectedDate={date ?? null}
        onBack={() => navigate('/stream')}
        />
      </Box>
    </ThemeProvider>
  )
}

const baseTheme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1976d2' },
    secondary: { main: '#9c27b0' },
  },
})

const listPageTheme = createTheme({
  ...baseTheme,
  palette: {
    ...baseTheme.palette,
    mode: 'dark',
    background: { default: '#303844', paper: '#454b56' },
  },
  components: {
    MuiIconButton: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
  },
})

/** Sets window.__API_BASE__ from path: /stream -> /api/stream, else /api. Same App for both. */
function ApiBaseSync({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  if (typeof window !== 'undefined') {
    const win = window as { __API_BASE__?: string }
    if (location.pathname.startsWith('/stream')) {
      win.__API_BASE__ = '/api/stream'
    } else {
      delete win.__API_BASE__
    }
  }
  return <>{children}</>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={baseTheme}>
      <CssBaseline />
      <BrowserRouter>
        <ApiBaseSync>
          <Routes>
            <Route path="/stream" element={<ThemeProvider theme={listPageTheme}><CssBaseline /><App /></ThemeProvider>} />
            <Route path="/stream/event/:marketId" element={<EventDetailPage />} />
            <Route path="/stream/expanded" element={<ThemeProvider theme={listPageTheme}><CssBaseline /><ExpandedEventsPage /></ThemeProvider>} />
            <Route path="/stream/*" element={<ThemeProvider theme={listPageTheme}><CssBaseline /><App /></ThemeProvider>} />
            <Route path="*" element={<App />} />
          </Routes>
        </ApiBaseSync>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
)
