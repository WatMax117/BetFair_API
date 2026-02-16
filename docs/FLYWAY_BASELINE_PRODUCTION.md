# Flyway Baseline for Production stream_ingest Schema

## Context

The streaming client uses Flyway; the production `stream_ingest` schema already exists and was created/evolved outside Flyway (manual conversion to partitioned table, etc.). Flyway fails with:

```
Found non-empty schema(s) "stream_ingest" but no schema history table.
Use baseline() or set baselineOnMigrate to true to initialize the schema history table.
```

## Approach

- **Baseline on migrate:** `SPRING_FLYWAY_BASELINE_ON_MIGRATE=true` so Flyway creates `flyway_schema_history` and baselines the schema instead of failing.
- **Baseline version:** `SPRING_FLYWAY_BASELINE_VERSION=5` so all migrations V1–V5 are considered already applied. We do **not** run V2–V5 in production (V3 would rename/recreate `ladder_levels` and break the current partitioned setup).
- **Schema:** `SPRING_FLYWAY_SCHEMAS=stream_ingest`.

## Configuration

In code (defaults):

- `betfair-streaming-client/src/main/resources/application.yml`: `baseline-on-migrate`, `baseline-version`, `schemas` (with env overrides).
- `docker-compose.yml`: env vars for streaming-client with defaults above.

Optional in `/opt/netbet/.env` (overrides):

```bash
SPRING_FLYWAY_BASELINE_ON_MIGRATE=true
SPRING_FLYWAY_BASELINE_VERSION=5
SPRING_FLYWAY_SCHEMAS=stream_ingest
```

## Rebuild and Restart (VPS)

```bash
cd /opt/netbet
docker compose up -d --no-deps --build streaming-client
docker logs -f netbet-streaming-client
```

## Required: CREATE on schema for Flyway history table

The streaming client user must be able to create the Flyway history table in `stream_ingest`:

```sql
GRANT CREATE ON SCHEMA stream_ingest TO netbet_stream_writer;
```

Script: `scripts/grant_flyway_create_stream_ingest.sql` (or run the line above as `netbet`).

## Verification

- `stream_ingest.flyway_schema_history` exists and has a baseline row (version 5).
- No Flyway errors in logs; application starts.
- `PostgresStreamEventSink started` and `Started BetfairStreamingClientApplication` in logs.
- Today's data in `stream_ingest.ladder_levels` and UI updates as expected.

## Constraints

- Do **not** drop or recreate the schema.
- Do **not** run clean/migrate in production.
- Do **not** change existing tables; this is baseline alignment only.
