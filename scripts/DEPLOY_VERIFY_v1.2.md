# Liquidity Activation & Production Deployment (v1.2 / v1.2.1)

## Summary of improvements

- **Resilience:** Runner-level fallback when `marketDefinition.totalMatched` is 0 or null; volume is summed from all runners’ traded volume in cache.
- **Role consistency:** All JDBC and SQL use user `netbet` (`-U netbet`).
- **Traceability (v1.2.1):** Every 100th liquidity update logs: `Liquidity trace: Market ID | Stream: [X] | Fallback: [Y] | Final: [Z]` — so you see exactly whether Betfair sent volume (stream) or the fallback was used (final = fallback when stream = 0).
- **SQL precision (v1.2.1):** Pulse check uses `coalesce(total_matched, 0) > 0` so NULL is handled identically across diagnostics.

---

## 1. Code update (done)

- **PostgresStreamEventSink.java:** Explicit semantics: **stream** = marketDefinition.totalMatched (0 if missing), **fallback** = sum(runner.totalMatched) from cache, **final** = (stream > 0 ? stream : fallback). Log format: `Liquidity trace: Market ID | Stream: [X] | Fallback: [Y] | Final: [Z]`.
- **Config:** `application.yml` and `docker-compose.yml` use `SPRING_DATASOURCE_USERNAME: netbet`; Postgres container uses `POSTGRES_USER: netbet`.

---

## 2. Unified stack redeploy (run on VPS)

```bash
cd /opt/netbet
docker compose up -d --build netbet-streaming-client
```

---

## 3. Execution & live verification (VPS)

### Step A: Bulletproof pulse check (COALESCE)

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    (SELECT count(*) FROM market_liquidity_history) AS history_rows,
    (SELECT count(*) FROM markets WHERE coalesce(total_matched, 0) > 0) AS markets_with_vol,
    (SELECT max(total_matched) FROM markets) AS max_vol;"
```

Or using the script:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/pulse_check_v1.2.sql
```

### Step B: Golden audit (run after ~5 mins)

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/golden_audit.sql
```

---

## 4. Critical interpretation path

After running the pulse check, use this hierarchy:

| Result | Meaning | Immediate action |
|--------|--------|-------------------|
| **history_rows = 0** | Entire liquidity path is failing or not triggered. | `docker logs netbet-streaming-client \| grep -Ei "exception\|error"` |
| **history_rows > 0** but **markets_with_vol = 0** | History is written, but UPDATE to `markets` is failing. | Check sink UPDATE statement and DB permissions. |
| **Both > 0** but **current_volume = 0** in Golden Audit | History and markets have data; audit view may be wrong. | Check COALESCE / aggregation in `v_golden_audit` or `golden_audit.sql`. |

---

## 5. Success criteria (KPIs)

| KPI | Meaning |
|-----|--------|
| **history_rows > 0** | Pipeline to `market_liquidity_history` is active. |
| **markets_with_vol > 0** | UPDATE to `markets.total_matched` is working (COALESCE ensures NULL is treated as 0). |
| **current_volume > 0** | Golden audit shows real Euro values (e.g. 5420.50) for active markets. |

---

## 6. Optional: liquidity trace logs

```bash
docker logs netbet-streaming-client --tail 500 2>&1 | grep -i "Liquidity trace"
```

Example: `Liquidity trace: Market ID | Stream: [0] | Fallback: [5400] | Final: [5400]` → Betfair sent no definition volume; fallback is providing the value.

---

## Final deployment steps (v1.2.1)

1. Sync the code with the refined PostgresStreamEventSink logging.
2. Redeploy the streaming client: `docker compose up -d --build netbet-streaming-client`.
3. Run **Pulse Check** after 2 minutes.
4. Run **Golden Audit** after 5 minutes.
