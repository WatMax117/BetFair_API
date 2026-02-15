#!/bin/bash
# Diagnose why some old or new events do not appear / timeseries returns empty.
# Run on VPS. Pass one or two market_ids as arguments, or use defaults.
#
# Usage:
#   bash scripts/diagnose_events_not_loading.sh
#   bash scripts/diagnose_events_not_loading.sh 1.234567890 1.987654321

set -e

OLD_MARKET="${1:-}"
NEW_MARKET="${2:-}"

echo "=========================================="
echo "Events not loading — diagnostic"
echo "=========================================="
echo ""

# If no market_ids provided, pick one recent and one older from DB
if [ -z "$OLD_MARKET" ] || [ -z "$NEW_MARKET" ]; then
  echo "No market_id(s) provided. Picking one old and one new from DB..."
  OLD_MARKET=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "
    SELECT market_id FROM public.market_derived_metrics
    WHERE snapshot_at < NOW() - INTERVAL '7 days'
    ORDER BY snapshot_at DESC LIMIT 1;
  " 2>/dev/null | tr -d ' ' || echo "")
  NEW_MARKET=$(docker exec netbet-postgres psql -U netbet -d netbet -t -c "
    SELECT market_id FROM public.market_derived_metrics
    WHERE snapshot_at > NOW() - INTERVAL '1 day'
    ORDER BY snapshot_at DESC LIMIT 1;
  " 2>/dev/null | tr -d ' ' || echo "")
fi

for LABEL in "Old/example" "New/example"; do
  if [ "$LABEL" = "Old/example" ]; then
    M="$OLD_MARKET"
  else
    M="$NEW_MARKET"
  fi
  if [ -z "$M" ]; then
    echo "Skip $LABEL: no market_id"
    continue
  fi
  echo "----------------------------------------"
  echo "Market: $LABEL (market_id=$M)"
  echo "----------------------------------------"

  echo ""
  echo "A) DB: snapshot count and latest snapshot time"
  docker exec netbet-postgres psql -U netbet -d netbet -c "
    SELECT
      COUNT(*) AS snapshot_count,
      MIN(snapshot_at) AS earliest,
      MAX(snapshot_at) AS latest
    FROM public.market_derived_metrics
    WHERE market_id = '$M';
  " 2>/dev/null || echo "Query failed"

  echo ""
  echo "B) DB: market/event metadata (league, event mapping)"
  docker exec netbet-postgres psql -U netbet -d netbet -c "
    SELECT e.event_id, e.event_name, e.competition_name, e.event_open_date
    FROM public.market_event_metadata e
    WHERE e.market_id = '$M';
  " 2>/dev/null || echo "No metadata row or query failed"

  echo ""
  echo "C) API: /timeseries (first 30 lines of JSON)"
  FROM_TS=$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-30d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
  TO_TS=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")
  RESP=$(curl -s -w "\n%{http_code}" "http://127.0.0.1:8000/events/${M}/timeseries?from_ts=${FROM_TS}&to_ts=${TO_TS}&interval_minutes=15&include_impedance=true&include_impedance_inputs=true")
  BODY=$(echo "$RESP" | head -n -1)
  CODE=$(echo "$RESP" | tail -n 1)
  echo "HTTP status: $CODE"
  echo "$BODY" | head -30
  echo ""

  echo "----------------------------------------"
done

echo ""
echo "=========================================="
echo "API filter reference"
echo "=========================================="
echo "/leagues:  event_open_date in [from_ts, to_ts]; optional in-play lookback."
echo "/events:   same time window; league name match."
echo "/timeseries: market_id + snapshot_at in [from_ts, to_ts]; 15-min buckets."
echo ""
echo "If DB has rows but API returns []: check from_ts/to_ts and timezone."
echo "If DB has no rows: ingestion or event mapping may be missing for that market."
echo ""
