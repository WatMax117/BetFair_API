# Betfair Streaming Client (Reference Architecture)

Spring Boot application aligned with the [Betfair Exchange Stream API](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687396/Exchange+Stream+API) for high-frequency football data collection. **Status:** [Approved – Production Ready](PROJECT_STATUS.md). **VPS clean deploy:** [DEPLOYMENT.md](DEPLOYMENT.md).

## Architecture (1:1 semantic alignment)

- **SessionProvider**: Isolated session lifecycle; guarantees a valid token before any connection attempt (token from auth-service).
- **StreamingClient**: Dedicated TCP/TLS handler; single-threaded read loop with zero blocking (no I/O or DB in loop).
- **SubscriptionManager**: Idempotent subscription payloads; re-issues exact same filters on reconnect (soccer-only, 8-level depth).
- **MessageRouter & Handlers**: Centralized routing for `connection`, `status`, `heartbeat`, `mcm` (marketChange).
- **MarketCache**: Initial Image + Deltas state machine; atomic updates at market level; sequence (clk) stored; fresh image on reconnect.
- **StreamEventSink**: Data sink interface for market updates (decouples from future PostgreSQL).

## Data scope (soccer only)

- **Market types**: FT Match Odds, FT O/U 2.5, HT Match Odds, HT O/U 0.5, Next Goal.
- **Order book depth**: Top 8 levels Back/Lay (Price + Size).
- **Metadata**: marketDefinition (inPlay, marketTime, runner status), totalMatched, ltp.

## Resilience

- **Stream reconnection**: Exponential backoff + jitter (0.5s–30s) between TCP reconnection attempts; fresh image policy (cache cleared on reconnect).
- **Metadata hydrator – 2-step Adaptive Backoff**: On transient API errors (429/5xx, timeouts), the hydrator uses a 2-step backoff: **5s** after the first transient error, **10s** for consecutive transient errors. Backoff resets to `minIntervalMs` on the first successful batch. Configurable via `first-transient-backoff-ms` and `consecutive-transient-backoff-ms`.
- **Heartbeat**: Diagnostic; status/error messages drive re-auth and reconnect.

## Configuration (non-hardcoded)

All parameters loaded from environment. On VPS, use `/opt/netbet/auth-service/.env` (see `EnvConfig`).

| Env / Property | Description |
|---------------|-------------|
| BETFAIR_APP_KEY | Betfair application key (required) |
| BETFAIR_TOKEN_URL | Auth service token endpoint |
| BETFAIR_STREAM_HOST / betfair.stream-host | stream-api.betfair.com |
| BETFAIR_HEARTBEAT_MS | 500–5000 ms |
| BETFAIR_CONFLATE_MS | Conflation (0 or minimal for high volatility) |
| BETFAIR_LADDER_LEVELS | 8 (soccer depth) |
| BETFAIR_MARKET_ID / BETFAIR_MARKET_IDS | Optional specific market IDs (comma-separated) |
| BETFAIR_RECONNECT_ENABLED | true |
| BETFAIR_CSV_LOGGING | false (set true for CSV logging) |
| BETFAIR_METADATA_ADMIN_USER / BETFAIR_METADATA_ADMIN_PASSWORD | Basic Auth for /metadata/** (default admin/changeme) |
| BETFAIR_METADATA_FIRST_TRANSIENT_BACKOFF_MS | 5000 (first transient error backoff) |
| BETFAIR_METADATA_CONSECUTIVE_TRANSIENT_BACKOFF_MS | 10000 (consecutive transient backoff) |

## Run

The **Maven Wrapper** is the only supported build method (see [Operational Playbook](#operational-playbook-standard-procedures)) for environment consistency:

- **Linux / Mac:** `./mvnw spring-boot:run`
- **Windows:** `mvnw.cmd spring-boot:run`

The project includes `.mvn/wrapper/maven-wrapper.jar` for offline-capable builds.

With env from file (e.g. VPS):

```bash
# Ensure /opt/netbet/auth-service/.env exists or set env vars
export BETFAIR_APP_KEY=your_key
mvn spring-boot:run
```

## Security

- **`/metadata/**`** (including `/metadata/telemetry` and `/metadata/{marketId}`) is protected by **Spring Security** with **HTTP Basic Auth**. Default credentials: `admin` / `changeme`; override via `betfair.metadata-admin-user` and `betfair.metadata-admin-password`. Other paths (`/cache/**`, `/error`, `/actuator/**`, `/**`) are permitted. For production, consider restricting `/metadata/**` at the reverse proxy (e.g. Nginx) with IP allowlist or shared-secret header.

## Endpoints

- `GET /cache` – Summary of cached markets (unprotected)
- `GET /cache/{marketId}` – Market snapshot (runners, 8-level ladders, ltp, totalMatched) (unprotected)
- `GET /metadata/{marketId}` – Market metadata (teams, competition, kickoff); **Basic Auth required**
- `GET /metadata/telemetry` – Hydrator telemetry (total_calls, transient_errors, requeued_ids_total, etc.); **Basic Auth required**

## Telemetry (Metadata Hydrator)

Exposed at `GET /metadata/telemetry` (Basic Auth):

| Metric | Description |
|--------|-------------|
| `total_calls` | Total `listMarketCatalogue` API calls made |
| `transient_errors` | Calls that returned a transient error (429/5xx, timeouts); re-queued for retry |
| `requeued_ids_total` | Total market IDs re-queued due to transient errors (API pressure indicator) |
| `resolved_metadata` | Markets successfully resolved with full metadata |
| `resolved_missing` | Markets resolved as missing (not in catalogue) |
| `pending_queue_size` | Current queue size (on-demand `queue.size()`) |

Health check: `transient_errors` at 0 or low with backoff handling indicates healthy behaviour.

## Metadata (Home v Away)

Market metadata is enriched from **listMarketCatalogue**. The **eventName** string (Betfair soccer format, e.g. `"Arsenal v Liverpool"`) is parsed to set **homeTeam** and **awayTeam**: split on the literal `" v "`; text before is `homeTeam`, text after is `awayTeam`. Exposed in `GET /metadata/{marketId}` with runners and competition info.

## Latency & sink

- **Latency**: Delta between `publishTime` (Betfair) and `receivedTime` (local) is logged when lag > 200 ms.
- **StreamEventSink**: Implement and register a bean to receive market updates (e.g. for future PostgreSQL).

## PostgreSQL – traded_volume upsert (Last-Write-Wins)

`traded_volume` uses `ON CONFLICT (market_id, selection_id, price, publish_time) DO UPDATE SET size_traded = EXCLUDED.size_traded, received_time = EXCLUDED.received_time`, so the latest write wins. To verify that `received_time` advances on updates:

```sql
-- Pick an existing key (replace with real values from your DB)
-- Then after more stream activity, run again and confirm received_time increased.
SELECT market_id, selection_id, price, publish_time, size_traded, received_time
FROM traded_volume
WHERE market_id = '1.23456789' AND selection_id = 12345 AND price = 2.5
ORDER BY received_time DESC
LIMIT 1;
```

Re-run the same query after ingest; if the row was updated by the sink, `received_time` (and optionally `size_traded`) will be more recent.

## PostgreSQL – Pure Daily Partitioning

### Design rationale

The **pure daily partitioning** strategy was chosen to avoid PostgreSQL **range overlap errors** that occur when mixing monthly and daily partitions (e.g. a monthly partition and a daily partition both claiming the same day). Using only an **initial** segment plus **daily** segments (YYYYMMDD) keeps ranges disjoint and predictable.

### Architecture (textual)

- **ladder_levels_initial**  
  Historical catch-all: `[2020-01-01 00:00:00+00, start of current day UTC)`. Holds all data before today.

- **ladder_levels_YYYYMMDD**  
  Continuous daily segments from **the current day onwards** only; the system **strictly uses daily partitions (YYYYMMDD)** starting from the current day to avoid PostgreSQL range overlap errors. One partition per calendar day (UTC), e.g. `ladder_levels_20260204`.

### Integrity guarantee

**Zero gap, zero overlap** is ensured by `scripts/manage_partitions.sql`: it creates **today’s** and **tomorrow’s** partitions (UTC) so that the initial partition’s upper bound is exactly the start of today, and daily partitions form a contiguous sequence with no gaps and no overlapping ranges.

---

## Operational Playbook (standard procedures)

### Verification

After **any schema change or deployment** that touches partitioning or the `ladder_levels` table, run:

```bash
psql -U netbet -d netbet -f scripts/verify_partitions.sql
```

This lists the parent table and all partitions with their range bounds; use it to confirm no overlap and expected partition set.

### Maintenance (cron)

| Task | Schedule (UTC) | Script |
|------|----------------|--------|
| Create daily partitions | **00:05** | `scripts/manage_partitions.sql` |
| PostgreSQL backup | **01:00** | `scripts/backup_db.sh [output_dir]` |

Example crontab entries (adjust paths and DB vars):

```cron
5 0 * * *  cd /opt/netbet/betfair-streaming-client && psql -U netbet -d netbet -f scripts/manage_partitions.sql
0 1 * * *  /opt/netbet/scripts/backup_db.sh /opt/netbet/backups
```

### Build

The **Maven Wrapper** is the **only supported build method** for environment consistency and reproducible builds:

- **Linux / Mac:** `./mvnw clean package -DskipTests`
- **Windows:** `mvnw.cmd clean package -DskipTests`

Do not rely on a globally installed `mvn` for production builds; use the wrapper so that the same Maven version and settings are used everywhere.

---

## Operational Maintenance

Quick-reference commands for routine maintenance and resource monitoring (assumes Docker Compose with service name `netbet-postgres`).

### Check DB size

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "SELECT pg_size_pretty(pg_database_size('netbet'));"
```

### Table size breakdown (monitor ladder_levels growth)

```bash
docker exec netbet-postgres psql -U netbet -d netbet -c "
SELECT relname AS table_name, pg_size_pretty(pg_total_relation_size(relid)) AS size
FROM pg_catalog.pg_statio_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(relid) DESC;
"
```

### Clean-up (manage server resources)

```bash
# Stop and remove containers, networks, volumes for this project
docker compose down

# Remove unused images, containers, networks (optional; use with care)
docker system prune -f

# Full clean (containers + images + volumes) – use before a clean redeploy
docker compose down -v && docker system prune -a --volumes -f
```

---

## Telemetry contract

Metrics exposed at `GET /metadata/telemetry` (Basic Auth) are defined as follows so that high-frequency ingestion analysis is not misinterpreted.

### Postgres sink metrics

| Metric | Definition |
|--------|------------|
| **postgres_sink_inserted_rows** | **True record count** of rows written by the sink (ladder_levels, traded_volume, market_lifecycle_events). Defined as a mathematically accurate count: each JDBC `batchUpdate` result is interpreted so that **Spring's -2 (SUCCESS_NO_INFO)** is treated as **1 row**; any other negative value is counted as 1 row and logged as unexpected. Positive values are added as returned. This ensures the metric is a true record count and prevents misinformation during high-frequency ingestion analysis. |
| postgres_sink_write_failures | Number of flush failures (exceptions) since startup. |
| postgres_sink_queue_size | Current size of the sink queue (on-demand). |
| postgres_sink_last_flush_duration_ms | Duration in ms of the last successful flush. |
| postgres_sink_last_error_timestamp | Epoch ms of the last write failure (0 if none). |

Hydrator metrics (`total_calls`, `transient_errors`, `requeued_ids_total`, `resolved_metadata`, `resolved_missing`, `pending_queue_size`) are unchanged and documented in the Telemetry table above.

### Technical specification alignment

- **Pure daily partitioning**: The system strictly uses **daily** partitions (YYYYMMDD) starting from the current day; no monthly or other ranges. This avoids PostgreSQL range overlap errors.
- **Deterministic views**: The view `v_event_summary` uses **DISTINCT ON (event_id)** with a **multi-column ORDER BY** (event_id, market_start_time ASC NULLS LAST, market_id ASC) so that exactly one primary market per type per event is selected in a **stable, repeatable** way.
- **Telemetry accuracy**: The `postgres_sink_inserted_rows` metric is defined as a **true record count**, with Spring's -2 (SUCCESS_NO_INFO) batch result explicitly handled as one row per statement.

---

## Code freeze (baseline)

This version is the **Baseline**. The core infrastructure is considered production-stable. Further changes are **Feature Work**, not Stabilization. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the full code-freeze declaration.

## References

- [Exchange Stream API](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687396/Exchange+Stream+API)
- [Sample code (Java, C#, Node)](https://github.com/betfair/stream-api-sample-code)
