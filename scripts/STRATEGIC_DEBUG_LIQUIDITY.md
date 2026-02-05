# Strategic Debug: Liquidity Isolation & Force Rebuild

## Step 1: "Blood Sample" (Upstream Verification)

**Query run on VPS:**
```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT market_id, publish_time, total_matched, max_runner_ltp 
FROM market_liquidity_history 
ORDER BY publish_time DESC 
LIMIT 5;"
```

**Result:** All 5 rows had **total_matched = 0.00**; **max_runner_ltp** was non-zero (e.g. 2.86, 180, 980).

**Interpretation:** The issue is **Upstream**. Data arriving at the DB already has `total_matched = 0`, so either:
- The stream is not sending market-level `totalMatched` or runner-level volume, or
- The mapper/cache is not populating it (e.g. wrong field name in runner change).

If `total_matched` were > 0 in history but 0 in `markets`, the issue would be the UPDATE path.

---

## Step 2: Force Rebuild (No Cache)

**Commands run:**
```bash
cd /opt/netbet
docker compose build --no-cache netbet-streaming-client
docker compose up -d --force-recreate netbet-streaming-client
```

Rebuild and recreate completed successfully.

---

## Step 3: Log Audit (Post-Rebuild)

After 2 minutes:
```bash
docker logs netbet-streaming-client --tail 200 | grep -i "Liquidity trace"
```

**Result:** No lines (grep exit 1).

**Implications:**
- If the **VPS codebase** at `/opt/netbet` does not contain the latest `PostgresStreamEventSink` (with "Liquidity trace" and fallback), the new image still won’t log it. **Sync the repo from your local machine** (where the trace exists) to `/opt/netbet`, then run the build again.
- If the code is up to date, you need 100+ liquidity updates before the first "Liquidity trace" line (every 100th). Wait longer or confirm that snapshots are being processed.

---

## Subscription Check: EX_TRADED

**SubscriptionManager.java** already requests:
- `EX_TRADED`
- `EX_TRADED_VOL`
- `EX_LTP`
- `EX_MARKET_DEF`
- `EX_ALL_OFFERS`

No change needed for traded volume at subscription level.

---

## Upstream Fix: Runner-Level Volume

The cache reads runner total matched from **`rc.path("tv")`** in `MarketCache.CachedRunner.applyDelta()`. Betfair’s stream may use a different key (e.g. per-runner total). Options:

1. **Log raw runner change keys** (temporarily) to see what the API sends (e.g. `tv`, `ltv`, or something else).
2. **Fallback in cache:** If `tv` is missing, derive a runner-level total from the **`trd`** (traded) map, e.g. sum of sizes in `trd` as an approximation, and use that for the sink fallback.

After fixing upstream (correct field or fallback), sync to VPS, rebuild with `--no-cache`, and re-check the blood sample and "Liquidity trace" logs.
