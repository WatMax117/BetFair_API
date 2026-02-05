# Final v1.2.1 Deployment & Precision Audit

**Goal:** Deploy the finalized liquidity fallback logic and run a multi-stage verification so **today's** data is accurately captured and reported.

---

## CRITICAL: Sync checklist (before every rebuild) — Single source of truth

**Standard:** Every `docker compose build` must be preceded by a **full sync** of the deployment context. Do not rely on local pipes for verification; always run SQL (and shell) scripts from the VPS path `/opt/netbet/scripts/`.

**1. Scripts (mandatory)** — entire `scripts/` directory:

- Sync **all** `scripts/*.sql`, `scripts/*.sh`, and `scripts/*.md` to `/opt/netbet/scripts/` on the VPS.
- Example: `scp -r scripts/* WatMax-api:/opt/netbet/scripts/` (from project root), or rsync `scripts/` → `/opt/netbet/scripts/`.

**2. Java (functionally linked)** — both of these:

- `src/main/java/com/netbet/streaming/cache/MarketCache.java` — trd fallback, runner totalMatched
- `src/main/java/com/netbet/streaming/sink/PostgresStreamEventSink.java` — liquidity history, markets UPDATE, Liquidity trace (every 100th)

Example:  
`scp .../MarketCache.java WatMax-api:/opt/netbet/src/main/java/com/netbet/streaming/cache/`  
`scp .../PostgresStreamEventSink.java WatMax-api:/opt/netbet/src/main/java/com/netbet/streaming/sink/`

---

## 1. Code deployment: the transparent fallback

**PostgresStreamEventSink.java** (already in place):

- **Logic:** `final_volume = (marketDefinition.totalMatched > 0) ? marketDefinition.totalMatched : sum(runner.totalMatched)`  
  (Stream when present; otherwise fallback from cache.)
- **Logging:** `Liquidity trace: Market ID | Stream: [X] | Fallback: [Y] | Final: [Z]`

**Deploy on VPS:**

```bash
cd /opt/netbet && docker compose up -d --build netbet-streaming-client
```

Sync all project files to `/opt/netbet/` before running the above (e.g. rsync, git pull, or your usual sync method).

---

## 2. Execution & interpretation path (troubleshooting tree)

After redeploying, use this diagnostic order:

| Stage | Condition | Action / interpretation |
|-------|-----------|-------------------------|
| **Stage 1** | `history_rows = 0` | **Pipeline blocked.** Check `docker logs netbet-streaming-client \| grep -Ei "exception\|error"`. |
| **Stage 2** | `history_rows > 0` but `markets_with_vol = 0` | **Sink update issue.** Data reaches history but `markets` is not updated. Check DB permissions for `-U netbet`. |
| **Stage 3** | Both > 0 but `current_volume = 0` in Golden Audit | **Partition / view issue.** Golden audit now targets **today’s partition** dynamically; confirm COALESCE/aggregation if still zero. |

---

## 3. Live verification commands (VPS)

### A. Pulse check (NULL-safe with COALESCE)

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT 
    (SELECT count(*) FROM market_liquidity_history) AS history_rows,
    (SELECT count(*) FROM markets WHERE coalesce(total_matched, 0) > 0) AS markets_with_vol,
    (SELECT max(total_matched) FROM markets) AS max_vol;"
```

### B. Live trace (monitor the fallback engine)

```bash
docker logs -f netbet-streaming-client | grep -i "Liquidity trace"
```

### C. Golden audit (today’s partition)

The script uses **today’s UTC date** automatically (parent table `ladder_levels` + date filter; partition pruning applies). Run from the VPS-hosted script only (no local pipes).

**Preferred production command** (scripts are mounted in the postgres container at `/scripts`):

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f /scripts/golden_audit.sql
```

On the VPS host, scripts live at `/opt/netbet/scripts/`; the postgres container mounts them read-only at `/scripts`.

Local piping of SQL files is for emergency/debug only; production verification must always be executed from the `/scripts` directory inside the container to ensure consistency with the deployed code.

---

## 4. Success criteria (KPIs)

| KPI | Check |
|-----|--------|
| **Trace logs** | `Final: [X]` with **X > 0** (fallback or stream is supplying volume). |
| **Pulse check** | `max_vol` in line with expected liquidity of active Betfair markets. |
| **Golden audit** | Rows with **current_volume > 0** and **distinct_snapshots** increasing over time (e.g. every minute). |

---

## 5. Engineering summary

- **Today’s partition:** Golden audit no longer uses a hardcoded partition name; it targets today (UTC) via the parent table and date filter, removing “ghost zeros” from the report.
- **Stream–Fallback–Final logging:** Makes the liquidity path explicit and easy to debug.
- **Production signal:** Once containers are up and the first **Liquidity trace** shows **non-zero** values (Stream and/or Fallback/Final), the system is in **production mode**.

---

## Quick reference: order of operations

1. Sync code to `/opt/netbet/`.
2. Redeploy: `cd /opt/netbet && docker compose up -d --build netbet-streaming-client`.
3. After ~2 min: run **Pulse check** (A).
4. Optionally run **Live trace** (B) to confirm non-zero Final.
5. After ~5 min: run **Golden audit** (C) and confirm `current_volume > 0` and growing `distinct_snapshots`.
