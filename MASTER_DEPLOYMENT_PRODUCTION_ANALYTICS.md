# Final Master Instruction for Cursor: Professional Deployment & Analytical Audit (v1.1)

**Goal:** Safely clean the environment, apply the V5 Analytical Schema, and verify data integrity without the risk of "mathematical inflation" or host-level resource loss.

---

## 1. Safe Environment Cleanup

**WARNING:** Execute these commands **ONLY** if the VPS is dedicated to this project.

**Selective stopping** (Safe/Quiet mode — no error if no containers match):

```bash
docker ps -a | grep netbet | awk '{print $1}' | xargs -r docker stop
docker ps -a | grep netbet | awk '{print $1}' | xargs -r docker rm
```

**Selective volume removal:**

```bash
docker volume rm netbet_pgdata || true
```

---

## 2. Sync and V5 Deployment

**Sync:** Upload the latest code (V5 migration, Java Sink fixes, scripts) to `/opt/netbet/`.

**Launch:**

```bash
cd /opt/netbet && docker compose up -d --build
```

**Schema verification:**

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT to_regclass('public.market_liquidity_history') as table_exists, to_regclass('public.v_golden_audit') as view_exists;"
```

Both values must be non-null.

---

## 3. Automated "Golden Audit" (Smoke Test)

Uses a dynamic UTC partition name and CTE to prevent data inflation. Naming aligned with `v_golden_audit`.

```bash
# Define today's partition name (UTC)
TODAY_PARTITION="ladder_levels_$(date -u +%Y%m%d)"
echo "Targeting partition: $TODAY_PARTITION"

# Execute audit with CTE logic (aligned naming with v_golden_audit)
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
WITH market_stats AS (
    SELECT
        market_id,
        COUNT(*) AS total_ladder_rows,
        COUNT(DISTINCT (publish_time, received_time)) AS total_distinct_snapshots
    FROM $TODAY_PARTITION
    GROUP BY market_id
)
SELECT
    e.event_name,
    m.segment,
    SUM(ms.total_ladder_rows) AS ladder_rows,
    SUM(ms.total_distinct_snapshots) AS distinct_snapshots,
    SUM(m.total_matched) AS current_volume
FROM events e
JOIN markets m ON e.event_id = m.event_id
JOIN market_stats ms ON m.market_id = ms.market_id
GROUP BY e.event_name, m.segment
ORDER BY current_volume DESC;"
```

If the partition does not exist yet, run `scripts/manage_partitions.sql` first.

---

## 4. Success Criteria (KPIs)

| KPI | Criterion |
|-----|-----------|
| **current_volume** | Must match the "Matched" sum on Betfair for the specific 5 markets. |
| **distinct_snapshots** | Must increase over time, showing the real update count. |
| **Monotonicity** | `current_volume` must never decrease (handled by GREATEST). |

---

## 5. Maintenance (Backfill)

Run the throttled script to populate segments for legacy markets:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/backfill_segments.sql
```

Repeat until `SELECT COUNT(*) FROM markets WHERE segment IS NULL OR segment = '';` returns 0.

---

## One-Page Command Summary (copy-paste)

```bash
# 1) Safe cleanup (NetBet only; xargs -r = no-op if empty)
docker ps -a | grep netbet | awk '{print $1}' | xargs -r docker stop
docker ps -a | grep netbet | awk '{print $1}' | xargs -r docker rm
docker volume rm netbet_pgdata || true

# 2) After syncing code to /opt/netbet
cd /opt/netbet && docker compose up -d --build

# 3) Schema verification (both non-null)
docker exec -i netbet-postgres psql -U netbet -d netbet -c "SELECT to_regclass('public.market_liquidity_history') as table_exists, to_regclass('public.v_golden_audit') as view_exists;"

# 4) Golden audit (dynamic UTC partition)
TODAY_PARTITION="ladder_levels_$(date -u +%Y%m%d)"
echo "Targeting partition: $TODAY_PARTITION"
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
WITH market_stats AS (
    SELECT market_id, COUNT(*) AS total_ladder_rows, COUNT(DISTINCT (publish_time, received_time)) AS total_distinct_snapshots
    FROM $TODAY_PARTITION
    GROUP BY market_id
)
SELECT e.event_name, m.segment, SUM(ms.total_ladder_rows) AS ladder_rows, SUM(ms.total_distinct_snapshots) AS distinct_snapshots, SUM(m.total_matched) AS current_volume
FROM events e JOIN markets m ON e.event_id = m.event_id JOIN market_stats ms ON m.market_id = ms.market_id
GROUP BY e.event_name, m.segment ORDER BY current_volume DESC;"

# 5) Optional: backfill segments
docker exec -i netbet-postgres psql -U netbet -d netbet -f /opt/netbet/scripts/backfill_segments.sql
```
