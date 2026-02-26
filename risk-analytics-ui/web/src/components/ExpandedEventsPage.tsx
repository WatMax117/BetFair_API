import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import { fetchEventsByDateVolume } from '../api'
import type { ByDateVolumeResponse, ByDateVolumeItem, ByDateVolumeMarket } from '../api'

/** Today UTC as YYYY-MM-DD */
function getTodayUTC(): string {
  const d = new Date()
  return d.toISOString().slice(0, 10)
}

function num(v: number | null | undefined): string {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  return Number.isInteger(v) ? String(v) : Number(v).toFixed(2)
}

/** Volume view: events for the selected day sorted by volume. Date from URL ?date=YYYY-MM-DD. */
export function ExpandedEventsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const dateParam = searchParams.get('date')
  const selectedDate = dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam) ? dateParam : getTodayUTC()

  const [data, setData] = useState<ByDateVolumeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchEventsByDateVolume(selectedDate, { limit: 200, sort: 'volume_desc' })
      .then((res: ByDateVolumeResponse) => {
        if (!cancelled) setData(res)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load volume data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [selectedDate])

  const backUrl = `/stream?date=${selectedDate}`

  if (error) {
    return (
      <Box sx={{ p: 2, minHeight: '100vh', bgcolor: '#303844', color: '#bababa' }}>
        <Button variant="outlined" onClick={() => navigate(backUrl)} sx={{ color: '#66cc99', borderColor: '#66cc99', mb: 2 }}>
          Back to stream
        </Button>
        <Typography sx={{ color: '#f44336' }}>{error}</Typography>
      </Box>
    )
  }

  if (loading) {
    return (
      <Box sx={{ p: 2, minHeight: '100vh', bgcolor: '#303844', color: '#bababa' }}>
        <Typography>Loading volume…</Typography>
      </Box>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <Box sx={{ p: 2, minHeight: '100vh', bgcolor: '#303844', color: '#bababa', maxWidth: 1400, mx: 'auto' }}>
        <Button variant="outlined" onClick={() => navigate(backUrl)} sx={{ color: '#66cc99', borderColor: '#66cc99', mb: 2 }}>
          Back to stream
        </Button>
        <Typography>No events for {selectedDate} (UTC) with volume data.</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 2, minHeight: '100vh', bgcolor: '#303844', color: '#bababa', maxWidth: 1400, mx: 'auto' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Button variant="outlined" onClick={() => navigate(backUrl)} sx={{ color: '#66cc99', borderColor: '#66cc99' }}>
          Back to stream
        </Button>
        <Typography variant="body2">
          Events for {selectedDate} (UTC), sorted by volume (highest first). Total: {data.paging.total}.
        </Typography>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow sx={{ '& th': { borderBottom: '3px solid #66cc99' } }}>
            <TableCell sx={{ color: '#bababa' }}>Event</TableCell>
            <TableCell sx={{ color: '#bababa' }}>Competition</TableCell>
            <TableCell align="right" sx={{ color: '#bababa' }}>Volume</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.items.map((item: ByDateVolumeItem) => {
            // Open the market with highest volume for this event (not the first in list, which may have 0 buckets)
            const markets = item.markets ?? []
            const best = markets.length
              ? markets.reduce((a: ByDateVolumeMarket, b: ByDateVolumeMarket) => {
                  const av = a?.volume != null ? Number(a.volume) : 0
                  const bv = b?.volume != null ? Number(b.volume) : 0
                  return bv > av ? b : a
                })
              : undefined
            const marketId = best?.market_id ?? markets[0]?.market_id
            return (
              <TableRow
                key={item.event_id}
                hover
                sx={{
                  cursor: marketId ? 'pointer' : 'default',
                  color: '#bababa',
                }}
                onClick={() => {
                  if (marketId) {
                    window.open(`/stream/event/${marketId}?date=${selectedDate}`, '_blank', 'noopener,noreferrer')
                  }
                }}
              >
                <TableCell sx={{ color: '#bababa' }}>{item.event_name || item.event_id}</TableCell>
                <TableCell sx={{ color: '#bababa' }}>{item.competition_name ?? '—'}</TableCell>
                <TableCell align="right" sx={{ color: '#bababa' }}>
                  {item.volume_total != null && item.volume_total > 0 ? num(item.volume_total) : 'N/A'}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </Box>
  )
}
