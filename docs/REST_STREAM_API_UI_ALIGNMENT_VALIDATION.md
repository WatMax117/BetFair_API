# REST + Stream API/UI Alignment Validation

Validation of whether the API/UI layer is aligned with the new architecture:
- **REST** = discovery/metadata (primary source of events)
- **Stream** = prices/liquidity (enrichment only)

---

## 1. Source of truth for events in the API

### Current state: **MISALIGNED**

The `/api/stream/events/by-date-snapshots` endpoint does **NOT** use `rest_events` or `rest_markets` as the primary source. It uses `stream_ingest.ladder_levels` to determine which events exist.

#### Exact SQL flow (from `risk-analytics-ui/api/app/stream_data.py`)

**Step 1 – which markets exist (primary source):**
```sql
-- get_stream_markets_with_ladder_for_date() lines 316-327
SELECT DISTINCT market_id
FROM stream_ingest.ladder_levels
WHERE publish_time >= %s AND publish_time < %s
```
This defines the event universe: only markets that have at least one tick in the date range.

**Step 2 – metadata join:**
```sql
-- get_events_by_date_snapshots_stream() lines 352-361
SELECT m.market_id, m.event_id, m.event_name, m.event_open_date, m.competition_name,
       m.home_selection_id, m.away_selection_id, m.draw_selection_id
FROM market_event_metadata m
WHERE m.market_id = ANY(%s)   -- %s = stream_markets from Step 1
ORDER BY COALESCE(m.event_open_date, '1970-01-01'::timestamp) ASC, m.market_id
```

**Step 3 – staleness filter (line 357-358):**
```python
if last_pt < stale_cutoff:  # STALE_MINUTES = 120
    continue  # Exclude market
```

#### Count comparison queries

**REST source (should be primary):**
```sql
-- rest_events in current window (today UTC)
SELECT COUNT(*) AS rest_events_count
FROM rest_events
WHERE open_date >= CURRENT_DATE AT TIME ZONE 'UTC'
  AND open_date < (CURRENT_DATE + 1) AT TIME ZONE 'UTC';

-- rest_markets for same window
SELECT COUNT(*) AS rest_markets_count
FROM rest_markets rm
JOIN rest_events re ON rm.event_id = re.event_id
WHERE re.open_date >= CURRENT_DATE AT TIME ZONE 'UTC'
  AND re.open_date < (CURRENT_DATE + 1) AT TIME ZONE 'UTC';
```

**API source (current – ladder-driven):**
```sql
-- Markets that would appear in API for date=YYYY-MM-DD (replace with actual date)
SELECT COUNT(DISTINCT market_id) AS api_source_count
FROM stream_ingest.ladder_levels
WHERE publish_time >= 'YYYY-MM-DD'::timestamp AT TIME ZONE 'UTC'
  AND publish_time < ('YYYY-MM-DD'::date + 1)::timestamp AT TIME ZONE 'UTC'
  AND market_id IN (SELECT market_id FROM market_event_metadata);
```

These counts will often differ: REST can show more events (pre-kickoff, no ticks yet); API may show fewer (only markets with ticks and metadata).

### Required change

Use `rest_events` / `rest_markets` (or `active_markets_to_stream`) as the primary event universe, and join to `ladder_levels` only for price enrichment. Events without stream data should still appear (e.g. with null/placeholder prices) if they are in REST discovery.

---

## 2. Market type alignment

### rest_markets stores internal FT names

```sql
SELECT DISTINCT market_type FROM rest_markets;
```

Expected values: `MATCH_ODDS_FT`, `OVER_UNDER_25_FT`, `NEXT_GOAL` (and possibly other `OVER_UNDER_*` FT types).

### API/UI

The API does **not** filter by market type. It uses:

- `stream_ingest.ladder_levels` (market_id)
- `market_event_metadata` (no market_type column)

There are no references to `MATCH_ODDS_FT`, `OVER_UNDER_25_FT`, `MATCH_ODDS_HT`, or similar in the stream API code. The UI receives whatever the API returns; no market-type allowlist is applied there.

**Conclusion:** Market type filtering happens upstream (REST discovery, `active_markets_to_stream`, stream client subscription). The API shows all markets that pass the current (ladder-based) selection logic. Once the API is switched to REST as primary source, `rest_markets` / `active_markets_to_stream` will implicitly enforce the correct FT-only types.

---

## 3. NEXT_GOAL dynamic appearance test

### End-to-end flow

1. **Before kickoff + 117s:**
   ```sql
   SELECT * FROM rest_markets WHERE event_id = '<eventId>';
   ```
   Expected: MATCH_ODDS_FT, OVER_UNDER_25_FT; no NEXT_GOAL.

2. **After kickoff + 117s** (NEXT_GOAL follow-up run):
   - Discovery `run_next_goal_followups()` upserts NEXT_GOAL into `rest_markets`
   - Same market appears in `active_markets_to_stream` view
   - Java client loads `active_markets_to_stream` on next refresh and subscribes
   - Stream ingest writes rows to `stream_ingest.ladder_levels`
   - API includes it only if it passes current logic (ladder + staleness)

### Verification queries

```sql
-- 1. NEXT_GOAL in rest_markets
SELECT * FROM rest_markets WHERE event_id = '<eventId>' AND market_type = 'NEXT_GOAL';

-- 2. NEXT_GOAL in active_markets_to_stream
SELECT * FROM active_markets_to_stream WHERE event_id = '<eventId>' AND market_type = 'NEXT_GOAL';

-- 3. Ladder data for that market
SELECT COUNT(*), MIN(publish_time), MAX(publish_time)
FROM stream_ingest.ladder_levels
WHERE market_id = '<next_goal_market_id>';
```

### Current API behaviour

The API will only show NEXT_GOAL after:

1. REST follow-up inserts it into `rest_markets`
2. Stream client subscribes (via `active_markets_to_stream`)
3. Stream ingest receives and persists ticks
4. `ladder_levels` has rows for that market in the requested date range
5. Staleness check passes (last tick within 120 minutes)

So NEXT_GOAL will appear later than its insertion into REST. With REST as primary source, it would appear as soon as it exists in `rest_markets`, with optional enrichment when stream data exists.

---

## 4. Staleness filtering

### Current logic

**Constant:** `STALE_MINUTES = 120` (in `stream_data.py` line 16)

**Usage:**

- **by-date-snapshots (lines 355–358):** If `last_pt < stale_cutoff` (where `stale_cutoff = latest_bucket - 120 minutes`), the market is excluded.
- **timeseries (lines 419–422):** Similar: if `last_pt < stale_cutoff_time` (now - 120 minutes), the bucket is skipped.
- **league events (lines 617–619):** Same staleness check.

So any market with no tick in the last 120 minutes is excluded from event lists and timeseries.

### Intended behaviour

If REST is the source of truth:

- Staleness should **not** determine whether an event exists.
- Staleness can still control when we show **enriched** data (prices, volume, etc.).
- Events without recent ticks should still appear (e.g. with null/placeholder prices) if they are in `rest_events`/`rest_markets`.

### Recommendation

1. Use `rest_events` / `rest_markets` (or `active_markets_to_stream`) to define the event universe.
2. Apply staleness only when deciding whether to show stream-enriched fields (prices, volume, risk metrics).
3. Either:
   - Remove staleness as a hard filter for inclusion in event lists, or
   - Keep it only for “hide events with no activity in last N minutes” as an explicit, configurable UI option.

---

## 5. Consistency check – SQL and interpretation

Run for the current time window (replace `YYYY-MM-DD` with the date used by the UI):

```sql
-- A. REST layer
SELECT COUNT(*) AS rest_events_count FROM rest_events;
SELECT COUNT(*) AS rest_markets_count FROM rest_markets;
SELECT COUNT(*) AS active_markets_count FROM active_markets_to_stream;

-- B. Stream ingest
SELECT COUNT(DISTINCT market_id) AS ladder_markets_count
FROM stream_ingest.ladder_levels;

-- C. Metadata (markets that can be shown if we have ladder data)
SELECT COUNT(*) AS metadata_count FROM market_event_metadata;

-- D. Markets with ladder data in today
SELECT COUNT(DISTINCT market_id) AS ladder_today_count
FROM stream_ingest.ladder_levels
WHERE publish_time >= CURRENT_DATE::timestamp AT TIME ZONE 'UTC'
  AND publish_time < (CURRENT_DATE + 1)::timestamp AT TIME ZONE 'UTC';
```

### Expected relationships

- `rest_events_count` ≤ `rest_markets_count` (many markets per event).
- `active_markets_count` ≤ `rest_markets_count` (view filters to FT types).
- `ladder_markets_count` ≤ `active_markets_count` (stream subscribes only to active markets; some may not have ticks yet).
- UI event count ≈ number of distinct `market_id` returned by the API for the chosen date.

### Typical discrepancies

1. **API returns fewer events than `rest_events`**  
   Because the API currently derives events from `ladder_levels`, not REST.

2. **API excludes events with no ticks in 120 minutes**  
   Because of the staleness filter.

3. **NEXT_GOAL appears later in the UI than in `rest_markets`**  
   Because it only shows after stream data exists and passes staleness.

---

## Summary and next steps

| Check | Status | Action |
|-------|--------|--------|
| 1. REST as primary source | ❌ Misaligned | Refactor API to use `rest_events` / `rest_markets` (or `active_markets_to_stream`) as primary; use `ladder_levels` for enrichment only |
| 2. Market type alignment | ⚠️ No API filter | API does not filter; types come from REST. No change needed once source is switched |
| 3. NEXT_GOAL dynamic appearance | ⚠️ Delayed in API | Works end-to-end; API shows it only after stream data. With REST as primary, it would appear when in REST |
| 4. Staleness filtering | ⚠️ Too aggressive | Do not use staleness to exclude events; apply only when deciding whether to show enriched data |
| 5. Consistency | Depends on 1 & 4 | Re-run consistency queries after refactor |

---

## Evidence collection commands

To gather evidence on a live system:

```bash
# 1. rest_markets distinct types
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT DISTINCT market_type FROM rest_markets;"

# 2. Counts
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 'rest_events' AS source, COUNT(*) FROM rest_events
UNION ALL SELECT 'rest_markets', COUNT(*) FROM rest_markets
UNION ALL SELECT 'active_markets_to_stream', COUNT(*) FROM active_markets_to_stream
UNION ALL SELECT 'ladder_levels_distinct_market', COUNT(DISTINCT market_id) FROM stream_ingest.ladder_levels;
"

# 3. API response count (replace date and host)
curl -s "http://localhost:8000/stream/events/by-date-snapshots?date=$(date -u +%Y-%m-%d)" | jq 'length'
```
