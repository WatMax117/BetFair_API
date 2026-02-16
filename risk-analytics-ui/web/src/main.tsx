import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material'
import App from './App'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1976d2' },
    secondary: { main: '#9c27b0' },
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
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <ApiBaseSync>
          <Routes>
            <Route path="/stream" element={<App />} />
            <Route path="/stream/*" element={<App />} />
            <Route path="*" element={<App />} />
          </Routes>
        </ApiBaseSync>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
)
