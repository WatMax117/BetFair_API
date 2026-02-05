# Liquidity Deep Dive Audit

Run these steps **on the VPS** (where Docker/containers run) to locate the liquidity "tap" and fix silent failures.

---

## Step 1: Database Pulse Check

Run the two critical queries to see where the data stops.

**On VPS:**

```bash
# Query A: Check market_liquidity_history population
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT count(*) AS rows, min(publish_time), max(publish_time) FROM market_liquidity_history;
"

# Query B: Check markets total_matched (volume)
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT count(*) FILTER (WHERE coalesce(total_matched,0) > 0) AS markets_with_volume,
       max(total_matched) AS max_total_matched
FROM markets;
"
```

**Interpretation:**
- **Query A:** If `rows = 0` or very small, liquidity rows are not being written (sink path or subscription issue). If rows > 0, check whether `total_matched` in those rows is 0 (field not present in stream).
- **Query B:** If `markets_with_volume = 0` and `max_total_matched` is NULL/0, the UPDATE from the sink never sees a positive totalMatched.

**Alternative (run script from repo on VPS):**

```bash
cd /opt/netbet  # or wherever the project is
docker exec -i netbet-postgres psql -U netbet -d netbet < scripts/liquidity_pulse_check.sql
```

---

## Step 2: Log Grep (Silent Failure Search)

Check if the liquidity batch or totalMatched path is crashing silently:

```bash
docker logs netbet-streaming-client --tail 1000 2>&1 | grep -Ei "liquidity|total_matched|market_liquidity_history|exception|error"
```

**Interpretation:**
- No matches: no explicit liquidity/exception logs (silent path).
- Exceptions/errors: inspect stack traces; fix and redeploy.

---

## Step 3: Subscription Filter (Root Cause)

**Location:** Subscription is built in `SubscriptionManager.java`, not `StreamingClient.java`. The client only sends the payload from `subscriptionManager.getInitialSubscriptionPayload()`.

**Current subscription fields** (`SubscriptionManager.java`):

```java
private static final String[] MARKET_DATA_FIELDS = {
    "EX_ALL_OFFERS", "EX_TRADED_VOL", "EX_TRADED", "EX_LTP", "EX_MARKET_DEF"
};
```

- **EX_MARKET_DEF** is present → market definition updates (including status, inPlay) are requested. Betfair may or may not include `totalMatched` in the stream’s market definition object.
- **EX_TRADED_VOL** / **EX_TRADED** → runner-level traded data; runner change includes **`tv`** (traded volume per runner), which the cache already reads in `MarketCache.CachedRunner.applyDelta()` via `rc.path("tv")`.

**Where totalMatched is used:**

1. **PostgresStreamEventSink.processSnapshot()**  
   - Reads `totalMatched` from **market definition**: `def.path("totalMatched").asDouble(0)`.  
   - If the stream never sends `totalMatched` in the market definition, this stays 0.

2. **Fallback (implemented):**  
   - If market-definition `totalMatched` is 0, the sink now **aggregates runner-level** `getTotalMatched()` (from stream field `tv`) so that liquidity history and `markets.total_matched` can still be populated from runner updates.

**Verification:**  
- Ensure `EX_MARKET_DEF` remains in `MARKET_DATA_FIELDS` so market definition (and totalMatched when present) is received.  
- After redeploy, run Step 1 again; if `market_liquidity_history.total_matched` and `markets.total_matched` still show 0, capture a raw mcm sample (with marketDefinition and rc) from the stream to confirm field names.

---

## Summary

| Step | Action | Run on |
|------|--------|--------|
| 1 | Query A + B (history + markets volume) | VPS: `docker exec netbet-postgres psql ...` |
| 2 | Grep streaming-client logs for liquidity/exception/error | VPS: `docker logs netbet-streaming-client ... \| grep -Ei ...` |
| 3 | Confirm EX_MARKET_DEF in subscription; use runner `tv` fallback for totalMatched | Code: done in `PostgresStreamEventSink` |

After changing the sink (runner fallback), rebuild and redeploy the streaming client, then re-run Step 1 and the golden audit to confirm `current_volume` populates.
