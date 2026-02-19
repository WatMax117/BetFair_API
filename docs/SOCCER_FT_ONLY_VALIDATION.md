# Soccer Full-Time Only – Validation & Evidence

After deploying the REST (discovery only) + Stream (marketIds from DB, FT only) pipeline, use this checklist to provide evidence.

---

## 1. REST discovery (hourly, metadata only)

### Run on the hour

- **Cron (Linux):** `0 * * * * cd /opt/netbet && /path/to/python discovery_hourly.py` (or run from `betfair-rest-client` with env set).
- **Windows Task Scheduler:** Trigger at minute 0 of every hour.

### One hourly run – counts

After one run, capture:

- **Events discovered:** from log `events_discovered=…`
- **Events stored:** `events_stored=…`
- **Markets stored:** `markets_stored=…`
- **Skipped HT:** `skipped_ht=…` (must be ≥ 0; no HT persisted)

Example log line:

```
Discovery complete: events_discovered=… events_stored=… markets_stored=… skipped_ht=…
```

### DB verification (REST)

```sql
-- Distinct events from REST (rest_events)
SELECT count(*) AS rest_events_count FROM public.rest_events;

-- Markets stored per type (rest_markets)
SELECT market_type, count(*) AS cnt
FROM public.rest_markets
GROUP BY market_type
ORDER BY market_type;

-- Confirm zero HT in rest_markets
SELECT count(*) AS ht_count
FROM public.rest_markets
WHERE market_type LIKE '%HT%' OR market_type LIKE '%HALF_TIME%';
-- Expected: 0
```

---

## 2. Stream subscription (marketIds from DB, batched)

### Subscription payload evidence

- **Log line:** e.g. `Subscribing to N markets (M batches, FT only)`.
- **marketIds count:** N = total market IDs; M = number of batches (e.g. ceil(N/200)).
- **Sample payload:** From logs or code path: `SubscriptionManager.getInitialSubscriptionPayloads()` – confirm `marketFilter.marketIds` is an array of market IDs (no `eventTypeIds` / `marketTypeCodes` when using DB).

### DB verification (active_markets_to_stream)

```sql
-- Market IDs available for streaming (view populated by REST)
SELECT count(*) AS market_ids_to_stream FROM public.active_markets_to_stream;

-- Sample market IDs
SELECT market_id, event_id, market_type
FROM public.active_markets_to_stream
ORDER BY market_id
LIMIT 20;
```

---

## 3. DB verification – full pipeline

### Distinct events (from REST)

```sql
SELECT count(DISTINCT event_id) AS distinct_events FROM public.rest_events;
```

### Distinct markets by type (MATCH_ODDS, OVER_UNDER_* FT, NEXT_GOAL)

```sql
SELECT market_type, count(*) AS cnt
FROM public.rest_markets
WHERE market_type IN ('MATCH_ODDS_FT', 'OVER_UNDER_25_FT', 'NEXT_GOAL')
   OR (market_type LIKE 'OVER_UNDER_%' AND market_type NOT LIKE '%HT%')
GROUP BY market_type;
```

### Ladder / traded rows increasing (streaming writes)

Run twice (e.g. T and T+5 min) and compare:

```sql
-- Ladder rows (stream_ingest)
SELECT count(*) AS ladder_rows FROM stream_ingest.ladder_levels;

-- Traded volume rows
SELECT count(*) AS traded_rows FROM stream_ingest.traded_volume;
```

Confirm counts increase after the stream client has been running.

### Zero HT

```sql
-- No HT market types in rest_markets
SELECT count(*) FROM public.rest_markets
WHERE market_type LIKE '%HT%' OR market_type LIKE '%HALF%';
-- Expected: 0

-- No HT in stream_ingest (if we ever wrote by type, but we only subscribe to FT)
-- Optional: check public.markets if still used
SELECT count(*) FROM public.markets
WHERE market_type LIKE '%HT%' OR market_type LIKE '%HALF%';
-- Expected: 0 after FT-only migration (V8)
```

---

## 4. Summary checklist

| Check | Evidence |
|-------|----------|
| REST runs on the hour | Cron/task config or log timestamps |
| REST: events + markets stored, no snapshots | Log counts; no rows in market_book_snapshots from REST for discovery run |
| REST: zero HT persisted | `skipped_ht` in log; SQL on rest_markets HT = 0 |
| Stream subscribes by marketIds from DB | Log "Subscribing to N markets (M batches, FT only)"; payload has marketIds array |
| Stream: batched when > 200 | M > 1 when N > 200 |
| Distinct events/markets in DB | SQL counts above |
| Ladder/traded rows increase | Two snapshots of counts |
| Zero HT subscriptions / zero HT persisted | SQL and subscription payload (no HT market types) |

---

## 5. Optional: cron example for REST discovery

```bash
# Run at minute 0 of every hour (e.g. 13:00, 14:00)
0 * * * * cd /opt/netbet/betfair-rest-client && BF_USERNAME=... BF_PASSWORD=... BF_APP_KEY=... POSTGRES_PASSWORD=... python discovery_hourly.py >> /var/log/discovery_hourly.log 2>&1
```

Use the same env (cert paths, DB host, etc.) as the main REST client if needed.
