# Collector: API Selection + Limits

Documentation of what the collector does on the **first (catalogue) call** and how it decides which matches/markets to track. Exact parameters and current limits.

---

## 1. Initial catalogue request (`listMarketCatalogue`)

### 1.1 `marketFilter` (exact fields sent)

| Field | Value | Source / config |
|-------|--------|------------------|
| **eventTypeIds** | `[1]` | Hardcoded (1 = Soccer). |
| **marketTypeCodes** | `["MATCH_ODDS"]` | Hardcoded. |
| **marketStartTime** | time range (see below) | From `filters.time_range(from_=..., to=...)`. |

**Not sent:** `competitionIds`, `marketCountries`, `eventIds`, `inPlayOnly`, `turnInPlayEnabled`, `marketIds`, etc. Only the three above are used.

### 1.2 Time window (from / to)

- **from:** `now_utc - timedelta(minutes=LOOKBACK_MINUTES)`  
  Default: `LOOKBACK_MINUTES = 60` → from = now − 60 minutes.
- **to:** `now_utc + timedelta(hours=WINDOW_HOURS)`  
  Default: `WINDOW_HOURS = 24` → to = now + 24 hours.

So we request markets whose **market start time** is in `[now − 60 min, now + 24 h]`.

Config (env):

- `BF_LOOKBACK_MINUTES` (default `60`)
- `BF_WINDOW_HOURS` (default `24`)

### 1.3 `marketProjection`

Requested list (hardcoded):

- `RUNNER_DESCRIPTION`
- `MARKET_DESCRIPTION`
- `EVENT`
- `EVENT_TYPE`
- `MARKET_START_TIME`
- `COMPETITION`

### 1.4 `sort`

- **Value:** `"MAXIMUM_TRADED"` (hardcoded).  
  API returns markets ordered by traded volume (descending).

### 1.5 `maxResults`

- **Classic mode (non-sticky):** `max(200, MARKET_BOOK_TOP_N)`  
  Default: `MARKET_BOOK_TOP_N = 10` → **maxResults = 200**.
- **Sticky pre-match mode:** `max(STICKY_CATALOGUE_MAX, STICKY_K)`  
  Defaults: `STICKY_CATALOGUE_MAX = 200`, `STICKY_K = 50` → **maxResults = 200**.

Config (env):

- Classic: `BF_MARKET_BOOK_TOP_N` (default `10`) – only affects lower bound; effective cap is 200.
- Sticky: `BF_STICKY_CATALOGUE_MAX` (default `200`), `BF_STICKY_K` (default `50`).

### 1.6 Post-response filter: 3-runner Match Odds only

After the API returns, we **filter in code** to markets with **exactly 3 runners**:

- `runnerCount == 3` (or `len(runners) == 3` if no count).  
  This keeps only Match Odds–style markets (Home / Away / Draw).

Location: e.g. `catalogues = [c for c in catalogues if _runner_count(c) == 3]` in the tick path (classic and sticky).

We do **not** request multiple market types; we request only `marketTypeCodes=["MATCH_ODDS"]`, so each catalogue entry is one market (one per event in practice). The “3” is **3 runners (selections)** in that single market, not 3 markets per event.

---

## 2. How we rank/select what to track

### 2.1 Selecting **markets** (not events first)

- We work on **markets** returned by `listMarketCatalogue`.
- We do **not** group by event first; we do **not** compute an “event score” (e.g. aggregated across markets).  
  Ordering is the API’s: **sort = MAXIMUM_TRADED** (per market).

### 2.2 Metric used

- **Ranking:** We use the **API order** of the catalogue response (sort = `MAXIMUM_TRADED`).  
  We do not recompute a metric; we take the first N (or up to K in sticky) after the 3-runner filter.

### 2.3 Selection mode: per tick vs sticky

- **Classic mode (default):**  
  - Each tick: catalogue → filter 3-runner → take **first `MARKET_BOOK_TOP_N`** markets.  
  - That set is **replaced every tick** (“replace set”).  
  - No persistence of “tracked set” across ticks.

- **Sticky pre-match mode (`BF_STICKY_PREMATCH=1`):**  
  - Persistent **tracked set** (DB), max size **K** (`BF_STICKY_K`).  
  - **Admission** from catalogue (maturity + capacity), **no eviction by rank**.  
  - Removal only at **kickoff + buffer** or when market is invalid/not found.  
  - So selection is “sticky until kickoff” (per market), not “replace set”.

---

## 3. Match → markets (3 runners, not 3 markets per event)

- We request **one market type:** `marketTypeCodes=["MATCH_ODDS"]`.  
  So we get **one market per event** (the Match Odds market).
- That market has **3 runners** (Home / Away / Draw), not “3 markets per event”.
- We do **not** make a second `listMarketCatalogue` call filtered by `eventIds` + `marketTypeCodes`.  
  We use the single catalogue call and then:
  - filter to 3-runner,
  - take top N (classic) or admit into sticky set (sticky).

So:

- **marketTypeCodes** we track: **only `MATCH_ODDS`**.
- There are no “three markets per event” in the current design; it’s one market (Match Odds) with three selections per market.

---

## 4. Current hard limits (exact values)

### 4.1 Config (defaults and where used)

| Parameter | Default | Env | Meaning |
|-----------|--------|-----|--------|
| **MARKET_BOOK_TOP_N** | 10 | `BF_MARKET_BOOK_TOP_N` | Classic: number of markets we take from catalogue (after 3-runner filter) and poll each tick. |
| **Catalogue maxResults (classic)** | 200 | — | `max(200, MARKET_BOOK_TOP_N)` → effectively **200**. |
| **Catalogue maxResults (sticky)** | 200 | `BF_STICKY_CATALOGUE_MAX` | `max(STICKY_CATALOGUE_MAX, STICKY_K)` → default **200**. |
| **STICKY_K** | 50 | `BF_STICKY_K` | Sticky: max number of markets in the tracked set. |
| **MARKET_BOOK_BATCH_SIZE** | 50 | `BF_MARKET_BOOK_BATCH_SIZE` | Max marketIds per `listMarketBook` call (batching). |
| **INTERVAL_SECONDS** | 900 | `BF_INTERVAL_SECONDS` | Tick interval (15 minutes). |
| **TICK_DEADLINE_SECONDS** | 600 | `BF_TICK_DEADLINE_SECONDS` | Per-tick wall-clock deadline (10 min). |
| **LOOKBACK_MINUTES** | 60 | `BF_LOOKBACK_MINUTES` | Catalogue time window start: now − 60 min. |
| **WINDOW_HOURS** | 24 | `BF_WINDOW_HOURS` | Catalogue time window end: now + 24 h. |

### 4.2 Limit expressed as N markets vs N events

- **Classic:** Limit is **N markets** (`MARKET_BOOK_TOP_N`, default 10).  
  Not “N events × 3”; we have one Match Odds market per event, so it’s effectively “up to 10 events” (10 markets).
- **Sticky:** Limit is **K markets** (`STICKY_K`, default 50).  
  Again one market per event in our request, so up to 50 events (50 markets).

There is no separate “max events” cap; the cap is on **markets** (and we only request MATCH_ODDS, so 1 market per event).

---

## 5. API request rate / budget per tick

### 5.1 `listMarketCatalogue`

- **1 call per tick** (same in classic and sticky).

### 5.2 `listMarketBook`

- **Classic:** 1 call per tick (with `market_ids = list of up to MARKET_BOOK_TOP_N` → at most 10 marketIds).
- **Sticky:**  
  - Tracked set size ≤ K (e.g. 50).  
  - We batch by `MARKET_BOOK_BATCH_SIZE` (default 50).  
  - **Number of calls per tick** = `ceil(len(tracked_market_ids) / MARKET_BOOK_BATCH_SIZE)`  
  - Example: 50 tracked → 1 call; 120 tracked → 3 calls.

### 5.3 Max marketIds per `listMarketBook` request

- We send at most **MARKET_BOOK_BATCH_SIZE** marketIds per request (default **50**).  
  This is chosen to stay under Betfair’s ~200-point weight limit per request; 50 is a safe default.

---

## 6. Example request shapes (conceptual)

### 6.1 `listMarketCatalogue` (equivalent JSON-style)

```json
{
  "filter": {
    "eventTypeIds": ["1"],
    "marketTypeCodes": ["MATCH_ODDS"],
    "marketStartTime": {
      "from": "<now_utc - 60m ISO-8601>",
      "to": "<now_utc + 24h ISO-8601>"
    }
  },
  "marketProjection": [
    "RUNNER_DESCRIPTION",
    "MARKET_DESCRIPTION",
    "EVENT",
    "EVENT_TYPE",
    "MARKET_START_TIME",
    "COMPETITION"
  ],
  "sort": "MAXIMUM_TRADED",
  "maxResults": 200
}
```

(Actual client uses betfairlightweight `filters.time_range` and `filters.market_filter`; the real Betfair API may use camelCase keys. The above reflects the logical payload.)

### 6.2 `listMarketBook` (equivalent)

```json
{
  "marketIds": ["1.123456", "1.234567", "..."],
  "priceProjection": {
    "priceData": ["EX_ALL_OFFERS"]
  }
}
```

- **marketIds:** From catalogue (classic: first MARKET_BOOK_TOP_N after 3-runner filter; sticky: current tracked set, in batches of MARKET_BOOK_BATCH_SIZE).
- **priceProjection:** `ex_all_offers=True` (EX_ALL_OFFERS) so we get ladder data for derived metrics.

---

## 7. Summary table

| Item | Classic | Sticky |
|------|--------|--------|
| Catalogue filter | eventTypeIds=1, marketTypeCodes=MATCH_ODDS, marketStartTime [now−60m, now+24h] | Same |
| Catalogue maxResults | 200 | max(200, 50) = 200 (defaults) |
| Post-filter | 3-runner only | 3-runner only |
| Selection | First MARKET_BOOK_TOP_N (default 10) | Admit up to K (default 50), maturity + no eviction by rank |
| listMarketBook calls/tick | 1 (≤10 marketIds) | ceil(tracked / 50) (≤50 marketIds per call) |
| Limit type | N markets (default 10) | K markets (default 50) |
| Market types tracked | MATCH_ODDS only | MATCH_ODDS only (1 market per event, 3 runners) |
