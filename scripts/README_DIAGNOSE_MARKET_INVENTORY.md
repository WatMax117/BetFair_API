# Market Inventory Diagnostics

Comprehensive diagnostic analysis of collected market parameters - pure inventory, no modeling.

## Purpose

Before designing cross-market or lag analysis, understand:
- Which market types are collected
- Event coverage
- Selections (runners)
- Data density (tick/update rate)
- Available ladder depth and traded data
- Field completeness (NULL patterns)

## Usage

### On VPS (Docker)

```bash
cd /opt/netbet
./scripts/run_diagnose_market_inventory_docker.sh 2026-02-16
```

### Manual Docker Command

```bash
docker run --rm --network netbet_default \
  -e POSTGRES_HOST=netbet-postgres \
  -e POSTGRES_DB=netbet \
  -e POSTGRES_USER=netbet \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -e PGOPTIONS="-c search_path=public,stream_ingest" \
  -v "$(pwd)/data_exports:/opt/netbet/data_exports" \
  -v "$(pwd)/scripts:/opt/netbet/scripts" \
  -w /opt/netbet \
  python:3.11-slim \
  bash -c "pip install psycopg2-binary pandas -q && python scripts/diagnose_market_inventory.py --date 2026-02-16 --output-dir /opt/netbet/data_exports/diagnostics"
```

## Output Files

All files written to `/opt/netbet/data_exports/diagnostics/`:

### A. Market Type Inventory
`market_type_inventory_YYYY_MM_DD.csv`

Columns:
- market_type
- count_distinct_market_id
- count_distinct_event_id
- total_tick_rows (ladder + traded)
- total_ladder_rows
- total_traded_rows
- average_rows_per_market
- average_update_rate_per_market (rows per second)
- average_number_of_runners
- in_play_ratio (percentage of time in_play = true)

### B. Event Market Mapping
`event_market_mapping_YYYY_MM_DD.csv`

Columns:
- event_id
- event_name
- market_types_list (comma-separated)
- total_markets
- total_rows
- earliest_publish_time
- latest_publish_time

### C. Ladder Depth Diagnostics
`ladder_depth_diagnostics_YYYY_MM_DD.csv`

Columns:
- market_type
- max_level
- min_level
- total_rows
- pct_level_0_only
- pct_level_ge_3
- pct_level_ge_7

### D. Traded Volume Diagnostics
`traded_volume_diagnostics_YYYY_MM_DD.csv`

Columns:
- market_type
- pct_rows_with_traded_volume
- avg_traded_volume_delta_per_second
- max_traded_volume_delta_observed

### E. Update Frequency Analysis
`market_update_frequency_YYYY_MM_DD.csv`

Columns:
- market_id
- market_type
- rows_per_second
- median_inter_update (seconds)
- p95_inter_update (seconds)

### F. Distinct Values
`distinct_values_YYYY_MM_DD.txt`

Lists all distinct values for:
- market_type
- market_status
- record_type
- NEXT_GOAL variations (if any)

### G. Summary Report
`diagnostics_report_YYYY_MM_DD.txt`

Includes:
- Total rows scanned
- Total markets
- Total events
- Runtime
- Market types found
- NEXT_GOAL check results

## Key Checks

1. **NEXT_GOAL Detection**: Checks for market types containing "NEXT", "GOAL", "SCORE" variations
2. **Ladder Depth**: Confirms actual depth recorded (0-3 vs 0-7)
3. **Traded Volume Reliability**: Percentage of rows with traded_volume data
4. **Update Frequency**: Identifies most liquid/fastest updating markets

## Acceptance Criteria

Diagnostics complete when:
- ✅ All diagnostic files generated
- ✅ Clear understanding of:
  - Which market types are present
  - Whether "Next Goal" exists in data
  - Which market is most liquid/fastest updating
  - Actual depth recorded (0-3 vs 0-7)
  - Whether traded_volume is reliable
