# Timeseries impedanceInputs sample

To verify that the API returns `impedanceInputs` (including `backStake` and `layStake`) for the "Last 10 snapshots" table, run the following and share **one snapshot** from the response.

## Request

From your machine (replace `MARKET_ID`, and adjust `from_ts`/`to_ts` if needed):

```bash
# Get a market_id that has recent data, then:
curl -s "http://158.220.83.195/api/events/MARKET_ID/timeseries?from_ts=2026-02-01T00:00:00Z&to_ts=2026-02-13T00:00:00Z&interval_minutes=15&include_impedance=true&include_impedance_inputs=true" | jq '.[0]'
```

Or on the VPS:

```bash
MARKET_ID=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "SELECT market_id FROM public.market_derived_metrics WHERE snapshot_at > NOW() - INTERVAL '7 days' AND home_back_stake IS NOT NULL LIMIT 1;" | tr -d ' ')
curl -s "http://127.0.0.1:8000/events/${MARKET_ID}/timeseries?from_ts=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)&to_ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)&interval_minutes=15&include_impedance=true&include_impedance_inputs=true" | jq '.[0]'
```

## Expected shape (one snapshot)

The first element of the array should look like:

```json
{
  "snapshot_at": "2026-02-12T10:00:00",
  "home_best_back": 1.95,
  "away_best_back": 3.2,
  "draw_best_back": 4.1,
  "home_risk": 12.3,
  "away_risk": -5.2,
  "draw_risk": -7.1,
  "imbalance": { "home": 12.3, "away": -5.2, "draw": -7.1 },
  "total_volume": 50000,
  "impedance": { "home": -120.5, "away": 80.2, "draw": 40.3 },
  "impedanceInputs": {
    "home": {
      "backStake": 1500.5,
      "backOdds": 1.92,
      "backProfit": 1380.46,
      "layStake": 800.2,
      "layOdds": 2.1,
      "layLiability": 880.22
    },
    "away": { ... },
    "draw": { ... }
  }
}
```

- **backStake / layStake**: Aggregated stake from the top-N levels used in the impedance VWAP calculation for that snapshot/runner. If the API returns `null` for these, the row in `market_derived_metrics` likely has NULL (e.g. snapshots created before impedance inputs were written, or ingestion not writing them). Run the rest-client backfill or ensure the rest-client writes these columns for new snapshots.
- **backSize / home_back_size_sum_N**: Different metric (sum of back sizes at top N); may use the same N but is a separate field. Impedance inputs are the VWAP inputs (backStake, backOdds, layStake, layOdds) used to compute impedance.

## What to share

A single snapshot from the response: paste the JSON for `.[0]` (or the first point that has `impedanceInputs`). That confirms whether the API provides `backStake`/`layStake` and whether the UI mapping (H/A/D keys) is correct.
