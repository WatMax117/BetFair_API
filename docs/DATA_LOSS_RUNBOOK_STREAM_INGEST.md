# Data loss runbook — stream ingest (severity-1)

**When to use:** Raw/tick data is **supposed** to be retained but is **missing** for recent/completed events (e.g. yesterday’s events have no rows in `stream_ingest.ladder_levels`).

Treat as **severity-1 data loss** until proven otherwise.

---

## 1. Confirm scope with DB queries

Run on the target DB (e.g. VPS):

```bash
# 1) Last successful ingest time (max received_time)
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT max(received_time) AS last_ingest_time, max(publish_time) AS last_publish_time
FROM stream_ingest.ladder_levels;"

# 2) First missing time: e.g. expect data for date YYYY-MM-DD but no rows
docker exec -i netbet-postgres psql -U netbet -d netbet -c "
SELECT (publish_time AT TIME ZONE 'utc')::date AS d, count(*) AS rows
FROM stream_ingest.ladder_levels
WHERE publish_time >= now() - interval '7 days'
GROUP BY 1 ORDER BY 1;"
```

- **Last successful ingest:** Use `max(received_time)` and `max(publish_time)` from (1).
- **First missing time:** Identify the first calendar day (UTC) with zero or unexpectedly low rows from (2), or the first hour/interval with no data after a known good time.

---

## 2. Failure mode checklist

| Failure mode | How to check | Mitigation |
|--------------|--------------|------------|
| **Client stopped** | Container not running: `docker ps \| grep streaming`; restarts: `docker inspect netbet-streaming-client` (RestartCount). Logs: `docker logs netbet-streaming-client --since 24h`. | Restart client; fix deploy/restart policy. |
| **Auth / rate limit** | Stream disconnects / 401/403 in client logs. Betfair login or token expiry. | Refresh credentials; check Betfair app key and rate limits. |
| **Schema error** | Sink flush failures in logs (e.g. column missing, constraint). `docker logs netbet-streaming-client 2>&1 \| grep -i "flush failed\|exception\|error"`. | Apply migrations; add missing columns (e.g. `ingest_source`, `client_version` via `scripts/add_stream_ingest_provenance.sql`). |
| **Cleanup job** | Accidental DELETE or TRUNCATE; cron/script that drops data. Check crontab, runbooks, and `purge_partitions.sql` (only affects **public** partitions, not `stream_ingest` if non-partitioned). | Disable/amend cleanup; restore from backup if available. |
| **Partition drop** | If `stream_ingest.ladder_levels` is partitioned, list partitions and check for dropped ranges: `scripts/confirm_stream_data_retention.sql` section 6. | Recreate partitions; restore from backup. |
| **Disk / DB full** | DB or volume full; inserts fail. Check disk: `df`; Postgres logs. | Free space; expand volume; restart client. |

---

## 3. Capture evidence

- **First missing time (UTC):** e.g. “2026-02-15 00:00:00 UTC” (first day with no ticks).
- **Last successful ingest (UTC):** from `max(received_time)` / `max(publish_time)`.
- **Failure mode:** one or more from the table above.
- **Relevant log excerpts** (client, Postgres) and **script/cron** that may have run.

---

## 4. Post-incident

- Document in incident report.
- If retention/cleanup was wrong: update `docs/RETENTION_MATRIX.md` and any purge scripts.
- If schema was missing: ensure `add_stream_ingest_provenance.sql` and sink version are deployed so future writes have provenance.
