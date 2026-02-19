#!/usr/bin/env node
/**
 * Validate /events/{market_id}/buckets response:
 * - Buckets in ASC order (oldest first)
 * - Latest snapshot is the last element
 * Usage: node validate_buckets_order.js <base_url> [market_id]
 * Example: node validate_buckets_order.js http://localhost:8000 1.253378204
 */
const baseUrl = process.argv[2] || process.env.BASE_URL || 'http://localhost:8000'
const marketId = process.argv[3] || '1.253378204'
const base = baseUrl.replace(/\/$/, '')
const url = base.includes('/stream') ? `${base}/events/${encodeURIComponent(marketId)}/buckets` : `${base}/stream/events/${encodeURIComponent(marketId)}/buckets`

async function main() {
  let res
  try {
    res = await fetch(url)
  } catch (e) {
    console.error('Fetch failed:', e.message)
    process.exit(2)
  }
  if (!res.ok) {
    console.error('HTTP', res.status, res.statusText)
    process.exit(2)
  }
  const data = await res.json()
  if (!Array.isArray(data)) {
    console.error('Response is not an array')
    process.exit(2)
  }
  if (data.length === 0) {
    console.log('OK (no buckets): array empty, order N/A')
    process.exit(0)
  }
  const starts = data.map((b) => b.bucket_start).filter(Boolean)
  if (starts.length === 0) {
    console.error('No bucket_start in response')
    process.exit(2)
  }
  for (let i = 1; i < starts.length; i++) {
    if (starts[i] <= starts[i - 1]) {
      console.error('Order violation: bucket_start at', i, '<= previous:', starts[i], '<=', starts[i - 1])
      process.exit(1)
    }
  }
  const first = starts[0]
  const last = starts[starts.length - 1]
  console.log('OK: buckets in ASC order (oldest first). Count:', data.length)
  console.log('  First (oldest):', first)
  console.log('  Last (latest):', last)
  process.exit(0)
}

main()
