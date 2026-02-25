# Streaming Client vs REST — Audit and 15-Minute Snapshot Evaluation

**Date:** 2026-02-15  
**Scope:** Analysis and validation only. No production logic or schema changes.

---

# Part 1 — Streaming Client Technical Audit

## 1.1 Architecture

| Aspect | Detail |
|--------|--------|
| **Implementation location** | `betfair-streaming-client/` — Java/Spring Boot application. |
| **Docker service** | Yes. In root `docker-compose.yml`: service `streaming-client`, container name `netbet-streaming-client`, image built from `./betfair-streaming-client`. |
| **Start** | `CommandLineRunner` (`StreamingRunner`) on boot: obtain session from auth-service → resolve priority market IDs (optional) → connect TCP/TLS to `stream-api.betfair.com:443` → authenticate → send market subscription → run single-threaded read loop. No cron; long-lived process with reconnect loop. |
| **Persistence** | **Dual:** (1) **In-memory:** `MarketCache` (ConcurrentHashMap per market, runner ladders). (2) **Postgres:** `PostgresStreamEventSink` writes to schema **`stream_ingest`** (not `public`): `ladder_levels`, `traded_volume`, `market_lifecycle_events`, `market_liquidity_history`, `markets`. Flush: ~500 ms or ~200 records; non-blocking queue + worker thread. |

**Critical:** Risk analytics UI and API read from **`public`** (`market_derived_metrics`, `market_event_metadata`). Those tables are populated by the **REST client** (Python). The streaming client writes only to **`stream_ingest`**. So today there is **no pipeline** from streaming → Book Risk L3 or 15-min snapshots used by the UI.

---

## 1.2 Data Coverage (MATCH_ODDS and other soccer types)

For MATCH_ODDS (and HALF_TIME, OVER_UNDER_25, etc.) the stream provides:

| Data | Source | Notes |
|------|--------|------|
| **Best back/lay (L1)** | Yes | From runner `atb` / `atl` (and `batb`/`batl`, `bdatb`/`bdatl`) in `rc`; cache builds full ladder, L1 = first level. |
| **Ladder depth L2–L8** | Yes | `ladderLevels: 8` in subscription; `MarketCache.CachedRunner` holds `backLadder` / `layLadder` (TreeMap price → size). |
| **Total matched** | Yes | `marketDefinition.totalMatched` or sum of runner `tv` / `trd`; persisted in `market_liquidity_history` and `markets.total_matched`. |
| **Market status** | Yes | `marketDefinition.status` (OPEN/SUSPENDED/CLOSED); `onMarketLifecycleEvent` → `market_lifecycle_events`. |
| **In-play flag** | Yes | `marketDefinition.inPlay`; same lifecycle event. |
| **Selection IDs (Home/Away/Draw)** | In stream: selection IDs only. Role mapping: via **Metadata hydrator** (listMarketCatalogue) → `MetadataCache` / `GET /metadata/{marketId}`. Not in raw stream payload. |

**Sample stream message (conceptual — op=mcm):**

```json
{
  "op": "mcm",
  "ct": "SUB_IMAGE",
  "clk": "...",
  "pt": 1739620800000,
  "mc": [{
    "id": "1.23456789",
    "marketDefinition": {
      "status": "OPEN",
      "inPlay": false,
      "totalMatched": 125000.5,
      "marketType": "MATCH_ODDS"
    },
    "rc": [
      { "id": 47972, "atb": [[2.5, 100], [2.48, 50]], "atl": [[2.52, 80]], "ltp": 2.5, "tv": 50000 },
      { "id": 47973, "atb": [[3.2, 200]], "atl": [[3.25, 90]], "ltp": 3.2, "tv": 40000 },
      { "id": 47974, "atb": [[2.9, 150]], "atl": [[2.92, 70]], "ltp": 2.9, "tv": 35000 }
    ]
  }]
}
```

**Mapped internal representation (after cache apply):**  
`MarketCache.CachedMarket` per market; `CachedRunner` per selection ID with `backLadder`, `layLadder`, `tradedVolume`, `lastTradedPrice`, `totalMatched`. `marketDefinition` holds status, inPlay, totalMatched. Home/Away/Draw assignment requires metadata (event name / runner names or explicit mapping from catalogue).

---

## 1.3 Lifecycle & Stability

| Item | Implementation |
|------|----------------|
| **Auto-reconnect** | Yes. `StreamingRunner`: on exception (or stream exit), `marketCache.clearAll()`, then `ReconnectPolicy.nextDelayMs()` (exponential backoff + jitter, 0.5s–30s), then `streamingClient.run(token)` again. |
| **Resubscribe after reconnect** | Yes. Same subscription payload from `SubscriptionManager`; if priority list is used, `PriorityMarketResolver.resolvePriorityMarketIds(token)` is called again before each connect. |
| **Initial full image on reconnect** | Yes. Cache is cleared on every full TCP reconnection (`attempts > 0` → `clearAll()`). New connection gets a new initial image (no RESUB_DELTA from old state). |
| **Out-of-order / sequence** | `clk` and `initialClk` are stored and can be sent on resubscribe for RESUB_DELTA; after full reconnect the code always requests fresh image (no delta replay). Ordering within a single connection is preserved by single-threaded read loop. |
| **clk / pt** | `SubscriptionManager.updateClocks(initialClk, clk)` from change messages; `pt` (publish time) used for latency logging and sink timestamps. |

**Log excerpt (to be run on VPS):**

```bash
docker logs -n 5000 netbet-streaming-client 2>&1 | grep -E "Reconnect attempt|Starting Betfair|Resubscribe payload|Session unavailable|Stream client failed|Stream connected"
```

Manual inspection: reconnect attempts with backoff (“Reconnect attempt N: waiting … ms”), “Stream connected. connectionId=…”, and any “Session unavailable” / “Stream client failed”. Reconnect count = number of “Reconnect attempt” lines in the window. (Cache clear is not logged; it runs before each reconnect in code.)

---

## 1.4 State Consistency

| Aspect | Detail |
|--------|--------|
| **Per-market state** | **In-memory:** `MarketCache` → `CachedMarket` → `CachedRunner` (ladders, ltp, tv). **Persisted:** Only what the sink flushes: ladder_levels (per publish_time), traded_volume, market_lifecycle_events, market_liquidity_history. No “current best back/lay” table; that would require a view or job over `ladder_levels`. |
| **On service restart** | In-memory state is lost. On next start: new connection → new initial image from Betfair. No rebuild from Postgres for cache. |
| **Full image** | Requested on every (re)connect; no delta-only recovery after disconnect. |

**5-market comparison (manual):**  
For 5 markets, compare (1) streaming-derived state from `GET /cache/{marketId}` (or from stream_ingest views if built) with (2) REST `listMarketBook` at the same time. Compare best back/lay L1, totalMatched, last update time. This requires either exposing streaming “current state” from cache or building a view from `stream_ingest.ladder_levels` + `market_liquidity_history` and comparing to `public.market_derived_metrics` + raw REST response. Not automated in codebase today.

---

## 1.5 Performance & Capacity

| Metric | Value / method |
|--------|----------------|
| **Subscribed markets** | Up to **200** when priority subscription is enabled (40 events × 5 market types). Otherwise subscription is by event type + market type codes (no explicit cap in code; Betfair may limit). |
| **CPU / memory** | Not measured in repo. Recommend: `docker stats netbet-streaming-client` over 24 h; log `postgres_sink_queue_size`, `postgres_sink_last_flush_duration_ms`. |
| **Message rate** | Not instrumented. Approximate: count `onMarketChange` calls per second or use sink `insertedRows` delta per minute. |

---

# Part 2 — 24-Hour Validation Experiment (Methodology)

**Objective:** Compare streaming-derived state vs REST `listMarketBook` every 15 minutes for 200–300 MATCH_ODDS markets.

**Prerequisites:**

1. **Streaming:** Ensure `netbet-streaming-client` is running and subscribing to the same market set (e.g. align with REST sticky list or a fixed list of 200–300 market IDs).
2. **REST:** Ensure REST client continues to poll the same (or overlapping) set every 15 minutes and write to `public.market_book_snapshots` + `market_derived_metrics`.
3. **Streaming “snapshot” source:** Either (a) add a job that every 15 min writes current cache state to a table (e.g. `stream_ingest.snapshot_15min`), or (b) derive from `stream_ingest.ladder_levels` + `market_liquidity_history` by taking latest row per (market_id, bucket_15min).

**Metrics to collect (over 24 h):**

1. **Coverage**  
   Per 15-min bucket: % of markets with valid state (non-null best back/lay or totalMatched) for (a) streaming, (b) REST.

2. **Freshness**  
   % of markets updated in the last 10 minutes (by snapshot_at or received_time).

3. **Fidelity**  
   For 20 sampled markets per bucket: compare best back/lay L1 and totalMatched (streaming vs REST). Report % deviation (e.g. price diff, volume diff).

4. **Stability**  
   Count of stream disconnects; longest gap (minutes) without any update per market.

**Runbook (optional):**

1. Align market set: ensure REST sticky list (or 15-min poll list) and streaming subscription overlap (e.g. same 200–300 MATCH_ODDS market IDs).
2. Start of 24 h: note `T0`; ensure both services running.
3. Every 15 min: record for each source (streaming-derived table or cache export vs `public.market_derived_metrics` / `market_book_snapshots`) per market: snapshot_at, best_back_l1, best_lay_l1, total_matched, status.
4. End of 24 h: compute coverage (count markets with non-null state per bucket), freshness (updated in last 10 min), fidelity (sample 20 markets per bucket; compare prices and totalMatched), stability (grep logs for “Reconnect attempt”, “Stream client failed”; compute max gap without updates per market).
5. Write `docs/STREAMING_VS_REST_24H_VALIDATION_REPORT.md` with tables and recommendation.

**Deliverable:** Run the above on VPS, store results (e.g. CSV or SQL), and produce a short markdown report with tables and a conclusion (streaming vs REST coverage/freshness/fidelity/stability). This document does not run the experiment; it defines the procedure.

---

# Part 3 — 15-Minute Snapshot Aggregation Proposal (No Implementation)

## 3.1 Deterministic UTC bucket

- **Bucket time:**  
  `bucket_time = floor(snapshot_timestamp to 15 minutes UTC)`  
  e.g. in Postgres: `date_trunc('minute', snapshot_timestamp) - (EXTRACT(MINUTE FROM snapshot_timestamp)::int % 15) * interval '1 minute'`  
  or: `timestamp with time zone` at :00, :15, :30, :45.

- **Semantics:** Every event is assigned to exactly one bucket per market per 15-min UTC window. No overlap.

## 3.2 Aggregation strategy (choose one per metric)

| Metric | Options | Recommendation |
|--------|---------|----------------|
| **Best back/lay (L1)** | Last value in bucket, or value at bucket end | **Last state in bucket** (deterministic, aligns with “state at :00/:15/:30/:45”). |
| **L2/L3 depth** | Last state in bucket | Same as L1. |
| **Total matched** | Last value in bucket (monotonic) | **Last in bucket**; no average (totalMatched is cumulative). |
| **Book Risk L3 (H/A/D)** | Computed from last ladder state in bucket | Compute once from the chosen snapshot in the bucket (e.g. last). |
| **Exposure / max** | Max over bucket | Optional for “max exposure” views; not required for standard 15-min snapshot. |

**Proposal:** Use **last state in bucket** for all primary metrics (prices, sizes, totalMatched, derived Book Risk). Optional: store both “last” and “max totalMatched” in bucket if exposure analysis is needed.

## 3.3 When to stop snapshots per market

| Rule | Recommendation |
|------|----------------|
| **At event_open_date?** | No; many markets are still open and traded after scheduled start. |
| **At event_open_date + X?** | Yes. E.g. **event_open_date + 3 hours** (configurable). After that, no new 15-min snapshots. Avoids unbounded growth; covers in-play. |
| **When status != OPEN?** | Optional extra: stop when status is CLOSED (or SUSPENDED for > Y minutes). Can be combined with time window. |

**Proposal:** Stop writing 15-min snapshots for a market when **event_open_date + configurable window (e.g. 3 h)** has passed, and optionally when **status = CLOSED**. No snapshot for a bucket that falls entirely after that.

---

# Part 4 — Recommendation

| Option | Summary |
|--------|--------|
| **Continue REST** | Current setup. Single source of truth (public), 15-min tick, Book Risk L3, stable. No streaming integration. |
| **Hybrid (streaming + 15-min aggregate)** | Use streaming for real-time cache and for writing raw/aggregated data into a dedicated store (e.g. stream_ingest or a new 15-min snapshot table). Add a pipeline (view or ETL) to compute 15-min buckets and optionally Book Risk L3 from streaming data. Risk analytics can then read from either REST-derived or streaming-derived 15-min snapshots (or both with a defined priority). Requires: (1) 15-min aggregation from stream, (2) Home/Away/Draw mapping from metadata, (3) Book Risk L3 derivation from stream ladder data. |
| **Full streaming-driven** | Replace REST polling for the 200-market set with streaming as the only source; aggregate to 15-min buckets and write to a table consumed by the UI. REST only for catalogue/metadata or one-off backfills. |

**Suggested direction:**  
**Hybrid.** Keep REST as the current production source for 15-min snapshots and Book Risk L3 (no change to ingestion or UI). In parallel: (1) Run the 24-hour validation (Part 2) to quantify streaming vs REST coverage/freshness/fidelity and stability. (2) If results are good, design the streaming → 15-min aggregation pipeline (schema, job, and optional Book Risk L3 from ladder). (3) Only then consider switching or dual-writing. This keeps risk analytics reliable while validating whether streaming + 15-min normalization is technically superior before any production behavior change.

---

# Summary Table

| Question | Answer |
|----------|--------|
| Where is streaming implemented? | `betfair-streaming-client` (Java/Spring Boot), Docker service `netbet-streaming-client`. |
| Persistence? | In-memory (`MarketCache`) + Postgres **stream_ingest** (ladder_levels, traded_volume, market_lifecycle_events, market_liquidity_history, markets). |
| Does UI use streaming data? | No. UI reads **public** (REST-populated market_derived_metrics, market_event_metadata). |
| Reconnect / full image? | Yes. Exponential backoff; cache cleared; new initial image on each reconnect. |
| Selection ID → H/A/D? | Via metadata hydrator (listMarketCatalogue), not in stream payload. |
| 15-min bucket proposal? | `bucket_time = floor(ts to 15 min UTC)`; **last state in bucket**; stop at event_open_date + 3h (and optionally status=CLOSED). |
| Recommendation | **Hybrid:** keep REST as primary; run 24h validation; then add streaming → 15-min aggregation if metrics support it. |
