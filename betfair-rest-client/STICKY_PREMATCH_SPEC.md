# Sticky Pre-Match Collector – Spec and Deliverables

## 1. Maturity filter and parameters

**Rule (combined):**

- **Time window:** Kickoff must be in `[now + T_min_hours, now + T_max_hours]`.  
  Defaults: `T_min_hours=0`, `T_max_hours=24` (admit only if kickoff within next 24h).
- **Stability:** Market must appear in the catalogue in **N consecutive ticks** before admission. Default N=2; for markets with kickoff within 2 hours, N=1 (configurable via `BF_STICKY_NEAR_KICKOFF_HOURS` / `BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS`).
- **Optional volume gate:** `totalMatched >= V_min` (default `V_min=0`, i.e. not used at catalogue time; listMarketCatalogue does not return volume, so maturity uses consecutive ticks only unless we add a separate volume check after first poll).

**Justification:**

- **Time window:** Avoids admitting markets with kickoff far in the future (they would occupy capacity for a long time) and avoids admitting after kickoff.
- **N consecutive ticks:** Default 2 reduces churn from one-off catalogue noise. For near-kickoff (within 2h), requiring 1 consecutive tick helps reach 200 tracked markets when many matches start soon.
- **No eviction by rank:** Once admitted, a market stays in the tracked set until kickoff + buffer or invalid; catalogue rank changes do not remove it.

**Env (defaults):**

| Env | Default | Description |
|-----|---------|-------------|
| `BF_STICKY_K` | 200 | Max markets tracked (hard cap K). |
| `BF_KICKOFF_BUFFER_SECONDS` | 60 | Stop tracking at `event_start_utc + buffer`. |
| `BF_STICKY_V_MIN` | 0 | Min totalMatched to admit (0 = not used at admission). |
| `BF_STICKY_T_MIN_HOURS` | 0 | Min hours to kickoff for admission. |
| `BF_STICKY_T_MAX_HOURS` | 24 | Max hours to kickoff for admission. |
| `BF_STICKY_REQUIRE_CONSECUTIVE_TICKS` | 2 | Consecutive catalogue appearances before admit (default). |
| `BF_STICKY_NEAR_KICKOFF_HOURS` | 2 | When kickoff is within this many hours, use near-kickoff tick requirement. |
| `BF_STICKY_NEAR_KICKOFF_CONSECUTIVE_TICKS` | 1 | Consecutive ticks required when kickoff within `BF_STICKY_NEAR_KICKOFF_HOURS`. |
| `BF_STICKY_CATALOGUE_MAX` | 400 | listMarketCatalogue max_results (300–400 recommended to avoid candidate starvation). |
| `BF_MARKET_BOOK_BATCH_SIZE` | 50 | listMarketBook batch size (API weight limit). |

---

## 2. DB schema (persistent across restarts)

**`tracked_markets`**

| Column | Type | Description |
|--------|------|-------------|
| market_id | TEXT PK | Betfair market id. |
| event_id | TEXT | Event id. |
| event_start_time_utc | TIMESTAMPTZ | Kickoff. |
| admitted_at_utc | TIMESTAMPTZ | When admitted. |
| admission_score | DOUBLE PRECISION | Optional (e.g. volume). |
| state | TEXT | `TRACKING` \| `DROPPED`. |
| last_polled_at_utc | TIMESTAMPTZ | Last listMarketBook. |
| last_snapshot_at_utc | TIMESTAMPTZ | Last snapshot written. |
| created_at_utc, updated_at_utc | TIMESTAMPTZ | Audit. |

**`seen_markets`**

| Column | Type | Description |
|--------|------|-------------|
| market_id | TEXT PK | Market id. |
| tick_id_first | BIGINT | First tick seen. |
| tick_id_last | BIGINT | Last tick seen. |
| last_seen_at_utc | TIMESTAMPTZ | Last catalogue time. |

Created by `sticky_prematch.ensure_tables(conn)` or `scripts/create_tracked_markets.sql`.

---

## 3. Tick loop (A–D)

- **A. Expire at kickoff:** For each `tracked_markets` row with `state = TRACKING`, set `state = DROPPED` if `now_utc >= event_start_time_utc + kickoff_buffer_seconds`. This frees capacity.
- **B. Poll tracked only:** Call `listMarketBook` for all current `TRACKING` market_ids in batches of `MARKET_BOOK_BATCH_SIZE` (e.g. 50). Persist snapshots (existing 3-layer flow). Update `last_polled_at_utc` / `last_snapshot_at_utc`. Mark `DROPPED` any requested market not in the API response.
- **C. Discover candidates:** Call `listMarketCatalogue` (same filter as before, `max_results = STICKY_CATALOGUE_MAX`, sort `MAXIMUM_TRADED`). Filter: 3-runner only, not in `tracked_markets`, `maturity_filter(market) == True`. Rank by catalogue order (already by MAXIMUM_TRADED).
- **D. Fill capacity:** If `len(tracked) < K`, admit candidates in order until full. Upsert `market_event_metadata` for each newly admitted market. **Do not** remove any existing tracked market to make room.

After building candidates and admitting, call `record_seen` for every market in this tick’s catalogue so the next tick can enforce “2 consecutive ticks”.

---

## 4. Batching for listMarketBook

- **Batch size:** `BF_MARKET_BOOK_BATCH_SIZE` (default 50) to stay under Betfair’s ~200-point weight limit per request.
- **Loop:** For `i in range(0, len(market_ids), MARKET_BOOK_BATCH_SIZE)` call `listMarketBook(market_ids[i:i+batch])`, then persist and update `tracked_markets` for returned ids; optionally mark as DROPPED any requested id not in the response.

---

## 5. Unit tests

- **`tests/test_sticky_prematch.py`**
  - **Market stays tracked until kickoff:** Admit then expire at kickoff; only markets past kickoff+buffer are DROPPED.
  - **Market not evicted by higher-ranked candidate:** Admit one market, then admit a higher-scored one; both remain in tracked set.
  - **Capacity refill:** Admit up to K; tracked count ≤ K and new candidates fill empty slots.
  - **Kickoff expiry frees capacity:** After expiring past-kickoff markets, tracked count decreases and capacity is available for new admissions.

Tests require Postgres (set `POSTGRES_*` env or run in CI with test DB).

---

## 6. Metrics (logged each tick)

- **tracked_count** – `len(tracked_markets WHERE state = 'TRACKING')`.
- **admitted_per_tick** – Number newly admitted this tick.
- **expired** – Number dropped this tick due to kickoff+buffer.
- **requests_per_tick** – Number of listMarketBook calls this tick.
- **markets_polled** – Total number of books returned (snapshots persisted).

Example log line:

```
[Sticky] tick_id=42 duration_ms=3200 tracked_count=200 admitted_per_tick=0 expired=3 requests_per_tick=4 markets_polled=200
```

---

## 7. Enabling sticky pre-match

Set in environment (e.g. docker-compose or .env). For **200 MATCH_ODDS markets** see section 7a.

```bash
BF_STICKY_PREMATCH=1
BF_STICKY_K=200
BF_KICKOFF_BUFFER_SECONDS=60
BF_STICKY_CATALOGUE_MAX=400
BF_STICKY_REQUIRE_CONSECUTIVE_TICKS=2
```

Leave unset or `0` to keep the original “top-N each tick” behaviour.

---

## 7a. Runbook: How to run sticky pre-match at 200 markets

**Environment variables:**

| Variable | Value | Notes |
|----------|--------|--------|
| `BF_STICKY_PREMATCH` | `1` | Enable sticky pre-match mode. |
| `BF_STICKY_K` | `200` | Track up to 200 MATCH_ODDS markets. |
| `BF_STICKY_CATALOGUE_MAX` | `300`–`400` | Catalogue size; 400 recommended to avoid candidate starvation. |
| `BF_MARKET_BOOK_BATCH_SIZE` | `50` | Batch size for listMarketBook (unchanged). |
| `BF_INTERVAL_SECONDS` | `900` | Poll interval (15 min). |
| `BF_KICKOFF_BUFFER_SECONDS` | `60` (or `120`) | Stop polling at kickoff + this buffer. |

**Expected tick metrics:**

- **tracked_count** – Reaches **200** during normal match-density windows.
- **markets_polled** – ≈ 200 per tick (subject to pre-match availability).
- **expired** – Increases around kickoff times; triggers refill.
- **admitted_per_tick** – > 0 when `expired > 0` until capacity returns to ~200.
- **requests_per_tick** – `ceil(200 / 50) = 4` when full.

**Verification:** One tick log line showing full capacity:

```
[Sticky] tick_id=... duration_ms=... tracked_count=200 admitted_per_tick=0 expired=0 requests_per_tick=4 markets_polled=200
```

**Pre-match only:** Markets are dropped only at `kickoff + BF_KICKOFF_BUFFER_SECONDS` or when invalid/not found. No in-play polling in this mode.

---

## 8. Acceptance criteria

- No tracked market is removed before kickoff + buffer unless invalid/not found.
- Tracked set size never exceeds K.
- After a restart, tracked markets are rehydrated from DB (same tables).
- Catalogue rank changes do not cause churn of already tracked markets.
- Pre-match snapshots are collected consistently up to kickoff + buffer.
