#!/bin/bash
# Diagnostic script for impedance inputs (backStake/layStake) NULL vs populated
# Usage: ./vps_diagnose_impedance_inputs.sh [market_id_with_nulls] [market_id_with_values]

MARKET_ID_NULL="${1:-}"
MARKET_ID_VALUES="${2:-}"

echo "=== Finding market_ids with NULL vs non-NULL impedance inputs ==="
echo ""

# Find a market_id with NULLs
if [ -z "$MARKET_ID_NULL" ]; then
  echo "Finding market_id with NULL impedance inputs..."
  MARKET_ID_NULL=$(docker exec -i netbet-postgres psql -U netbet -d netbet -t -c "
    SELECT DISTINCT market_id
    FROM market_derived_metrics
    WHERE (home_back_stake IS NULL OR home_lay_stake IS NULL)
      AND snapshot_at > NOW() - INTERVAL '7 days'
    ORDER BY snapshot_at DESC
    LIMIT 1;" | tr -d '[:space:]')
fi

# Find a market_id with values
if [ -z "$MARKET_ID_VALUES" ]; then
  echo "Finding market_id with populated impedance inputs..."
  MARKET_ID_VALUES=$(docker exec -i netbet-postgres psql -U netbet -d netbet -t -c "
    SELECT DISTINCT market_id
    FROM market_derived_metrics
    WHERE home_back_stake IS NOT NULL 
      AND home_lay_stake IS NOT NULL
      AND snapshot_at > NOW() - INTERVAL '7 days'
    ORDER BY snapshot_at DESC
    LIMIT 1;" | tr -d '[:space:]')
fi

if [ -z "$MARKET_ID_NULL" ] || [ "$MARKET_ID_NULL" = "" ]; then
  echo "ERROR: Could not find market_id with NULL impedance inputs"
  exit 1
fi

if [ -z "$MARKET_ID_VALUES" ] || [ "$MARKET_ID_VALUES" = "" ]; then
  echo "ERROR: Could not find market_id with populated impedance inputs"
  exit 1
fi

echo "Market with NULLs: $MARKET_ID_NULL"
echo "Market with values: $MARKET_ID_VALUES"
echo ""

# Function to run diagnostics for a market
run_diagnostics() {
  local MARKET_ID=$1
  local LABEL=$2
  
  echo "=========================================="
  echo "=== $LABEL: market_id=$MARKET_ID ==="
  echo "=========================================="
  echo ""
  
  echo "--- A) Latest 20 rows: NULL vs non-NULL ---"
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
    SELECT snapshot_at,
           home_back_stake, home_lay_stake,
           away_back_stake, away_lay_stake,
           draw_back_stake, draw_lay_stake
    FROM market_derived_metrics
    WHERE market_id = '$MARKET_ID'
    ORDER BY snapshot_at DESC
    LIMIT 20;"
  
  echo ""
  echo "--- B) Count NULLs vs total ---"
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
    SELECT
      COUNT(*) AS total_rows,
      SUM(CASE WHEN home_back_stake IS NULL THEN 1 ELSE 0 END) AS home_back_nulls,
      SUM(CASE WHEN home_lay_stake  IS NULL THEN 1 ELSE 0 END) AS home_lay_nulls,
      SUM(CASE WHEN away_back_stake IS NULL THEN 1 ELSE 0 END) AS away_back_nulls,
      SUM(CASE WHEN away_lay_stake  IS NULL THEN 1 ELSE 0 END) AS away_lay_nulls,
      SUM(CASE WHEN draw_back_stake IS NULL THEN 1 ELSE 0 END) AS draw_back_nulls,
      SUM(CASE WHEN draw_lay_stake  IS NULL THEN 1 ELSE 0 END) AS draw_lay_nulls
    FROM market_derived_metrics
    WHERE market_id = '$MARKET_ID';"
  
  echo ""
  echo "--- C) Latest snapshot age ---"
  docker exec -i netbet-postgres psql -U netbet -d netbet -c "
    SELECT
      MAX(snapshot_at) AS latest_snapshot_at,
      NOW() - MAX(snapshot_at) AS age
    FROM market_derived_metrics
    WHERE market_id = '$MARKET_ID';"
  
  echo ""
}

# Run diagnostics for both markets
run_diagnostics "$MARKET_ID_NULL" "MARKET WITH NULLS"
run_diagnostics "$MARKET_ID_VALUES" "MARKET WITH VALUES"

echo ""
echo "=== Summary ==="
echo "Market with NULLs: $MARKET_ID_NULL"
echo "Market with values: $MARKET_ID_VALUES"
echo ""
echo "Interpretation:"
echo "- If older rows are NULL but newest rows are filled → backfill needed for historical snapshots"
echo "- If both old and new rows are NULL → ingestion bug (rest-client not writing these columns)"
echo "- If values exist in DB but UI shows '—' → API mapping or UI field mapping issue"
