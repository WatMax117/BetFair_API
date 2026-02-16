# Go/No-Go Checklist Result: Dropped `stream_ingest.ladder_levels_old`

## 1. Pre-drop checks — PASSED

### A) API checks
- **`/health`:** `{"status":"ok","ladder_levels_partition_horizon_days":30.0}` — horizon ≈ 30, status not degraded ✓
- **`/metrics`:** `ladder_levels_partition_horizon_days 30.0` — not -1 ✓

### B) Database checks
- **max(publish_time):** `ladder_levels` = 2026-02-06 23:57:22.957+00; `ladder_levels_old` = same (static snapshot) ✓
- **Row counts:** both 713,282 (equal; _old static at migration time) ✓

## 2. Backup — DONE
- **Command:** `docker exec netbet-postgres pg_dump -U netbet -d netbet -F c -f /tmp/netbet_before_drop_old.dump`
- **Result:** File created, 25.6 MB (`ls -lh /tmp/netbet_before_drop_old.dump` inside container)

## 3. Drop — DONE
- **SQL:** `DROP TABLE stream_ingest.ladder_levels_old;` (no CASCADE)
- **Result:** `DROP TABLE` — no dependency errors

## 4. Post-drop verification — PASSED
- **to_regclass('stream_ingest.ladder_levels_old'):** NULL ✓
- **max(publish_time) FROM stream_ingest.ladder_levels:** 2026-02-06 23:57:22.957+00 ✓
- **ANALYZE stream_ingest.ladder_levels:** executed ✓

## 5. Deploy/restart
- Not required; no container restart performed.

---

## Final acceptance criteria — MET
- Ingestion continues writing to `stream_ingest.ladder_levels` (partitioned table).
- `ladder_levels_partition_horizon_days` remains 30.
- No dependency errors during DROP; CASCADE was not used.

**Note:** Backup is inside the container at `/tmp/netbet_before_drop_old.dump`. Copy to host if you want to keep it after container recreation:  
`docker cp netbet-postgres:/tmp/netbet_before_drop_old.dump /opt/netbet/backups/`
