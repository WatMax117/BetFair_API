# 24-Hour Validation: Streaming vs REST (15-Min Snapshots)

**Purpose:** Compare streaming-derived state vs REST `listMarketBook` over 24 hours for 200–300 MATCH_ODDS markets.  
**Methodology:** See `docs/STREAMING_VS_REST_AUDIT_15MIN_SNAPSHOT.md` Part 2.

---

## Experiment Setup

| Item | Value |
|------|--------|
| **T0 (start)** | _YYYY-MM-DD HH:MM UTC_ |
| **T1 (end)** | _YYYY-MM-DD HH:MM UTC_ |
| **Market set** | _e.g. 250 MATCH_ODDS market IDs, same for REST and streaming_ |
| **REST 15-min source** | `public.market_book_snapshots` + `public.market_derived_metrics` |
| **Streaming 15-min source** | _e.g. stream_ingest.ladder_levels + market_liquidity_history, last row per (market_id, bucket_15min)_ or _cache export / snapshot table_ |

---

## 1. Coverage

% of markets with valid state (non-null best back/lay or totalMatched) in each 15-min bucket.

| Bucket (UTC) | REST % | Streaming % | Notes |
|--------------|--------|--------------|-------|
| _e.g. 00:00_ | _%_ | _%_ | |
| _…_ | | | |
| **Average** | _%_ | _%_ | |

---

## 2. Freshness

% of markets updated within the last 10 minutes (by snapshot_at / received_time).

| Bucket (UTC) | REST % | Streaming % |
|--------------|--------|--------------|
| _…_ | _%_ | _%_ |
| **Average** | _%_ | _%_ |

---

## 3. Fidelity

For 20 sampled markets per bucket: compare best back L1, best lay L1, totalMatched (streaming vs REST). Report % deviation.

| Metric | Mean abs % deviation | Max abs % deviation | Sample size |
|--------|----------------------|----------------------|-------------|
| Best back L1 | _%_ | _%_ | _e.g. 20 × 96 buckets_ |
| Best lay L1 | _%_ | _%_ | |
| totalMatched | _%_ | _%_ | |

---

## 4. Stability

| Metric | Value |
|--------|--------|
| **Stream disconnects (24 h)** | _count_ |
| **Longest gap without updates (any market)** | _minutes_ |
| **Reconnect log excerpt** | _paste or attach_ |

---

## Conclusion

- **Coverage:** _REST vs Streaming summary_
- **Freshness:** _REST vs Streaming summary_
- **Fidelity:** _Acceptable deviation?_
- **Stability:** _Disconnects acceptable?_

**Recommendation:** _[ ] Continue REST  [ ] Hybrid  [ ] Full streaming-driven_ — _one sentence rationale._
