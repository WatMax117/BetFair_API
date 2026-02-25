## Database architecture – NetBet

### Physical setup

- **Engine**: PostgreSQL 16 (`postgres:16-alpine`).
- **Container**: `netbet-postgres`.
- **Database**: `netbet`.
- **Storage**: named Docker volume `pgdata` (Docker-managed; typically mounted under `/var/lib/docker/volumes/netbet_pgdata/_data` on the VPS).
- **Ports**: `127.0.0.1:5432` on the VPS → `5432` in `netbet-postgres`.

Data survives container restarts and `docker compose down` (without `-v`) because it lives in the named volume, not in the container filesystem. Data is lost only if the volume is removed (e.g. `docker compose down -v` or `docker volume rm netbet_pgdata`).


## Logical structure – schemas and responsibilities

### Schemas

- **`rest_ingest`**
  - **Purpose**: tables, sequences, and other objects owned/written by the **Betfair REST ingestion** service (`betfair-rest-client`).
  - **Writer role**: `netbet_rest_writer`.

- **`stream_ingest`**
  - **Purpose**: tables, sequences, and other objects owned/written by the **streaming ingestion** service (`streaming-client` / Spring).
  - **Writer role**: `netbet_stream_writer`.

- **`analytics`**
  - **Purpose**: **read-only analytics layer** – views and/or materialized views over the ingestion schemas; exposed via `risk-analytics-ui-api`.
  - **Reader role**: `netbet_analytics_reader`.

- **`public`**
  - No application tables should live here going forward.
  - `PUBLIC` has **no CREATE privileges**; schema is reserved for extensions or internal use by the DB owner only.


## Roles and privileges

### Roles

- **`netbet`** (existing, DB owner)
  - Owns the `netbet` database and typically owns migration-created objects.
  - Full rights on all schemas.

- **`netbet_rest_writer`**
  - **Intended client**: `betfair-rest-client`.
  - **Privileges**:
    - `CONNECT` / `TEMPORARY` on database `netbet`.
    - `USAGE, CREATE` on schema `rest_ingest`.
    - DML on `rest_ingest` (tables/sequences):
      - Existing objects: `SELECT, INSERT, UPDATE, DELETE` on all tables; `USAGE, SELECT, UPDATE` on all sequences.
      - Future objects: default privileges ensure the same grants on new tables/sequences created by owner role `netbet`.
    - **No CREATE** on other schemas; no DML outside `rest_ingest`.
  - **search_path**:
    - Role-level: `ALTER ROLE netbet_rest_writer SET search_path = rest_ingest`.
    - Application-level: `PGOPTIONS=-c search_path=rest_ingest`.

- **`netbet_stream_writer`**
  - **Intended client**: `streaming-client` (Spring).
  - **Privileges**:
    - `CONNECT` / `TEMPORARY` on database `netbet`.
    - `USAGE, CREATE` on schema `stream_ingest`.
    - DML on `stream_ingest` (tables/sequences):
      - Existing objects: `SELECT, INSERT, UPDATE, DELETE` on all tables; `USAGE, SELECT, UPDATE` on all sequences.
      - Future objects: default privileges from owner `netbet` grant the same on new tables/sequences in `stream_ingest`.
    - **No CREATE** on other schemas; no DML outside `stream_ingest`.
  - **search_path**:
    - Role-level: `ALTER ROLE netbet_stream_writer SET search_path = stream_ingest`.
    - Application-level: JDBC `currentSchema=stream_ingest` in the connection URL.

- **`netbet_analytics_reader`**
  - **Intended client**: `risk-analytics-ui-api` (read-only REST API).
  - **Privileges**:
    - `CONNECT` / `TEMPORARY` on database `netbet`.
    - `USAGE` on schema `analytics`.
    - Read-only on `analytics`:
      - Existing objects: `SELECT` on all tables and sequences in `analytics`.
      - Future objects: default privileges from owner `netbet` grant `SELECT` on new tables/sequences in `analytics`.
    - **No INSERT/UPDATE/DELETE anywhere**; no CREATE on any schema.
    - By default, no access to `rest_ingest` or `stream_ingest` unless explicitly granted (prefer views in `analytics` instead).
  - **search_path**:
    - Role-level: `ALTER ROLE netbet_analytics_reader SET search_path = analytics`.
    - Application-level: `PGOPTIONS=-c search_path=analytics`.


## Schema/role migration – SQL

The base isolation model is implemented by `db/migrations/001_db_isolation.sql`. It is idempotent and can be reapplied safely.

### What the migration does

- Creates schemas (if missing): `rest_ingest`, `stream_ingest`, `analytics`.
- Creates roles (if missing): `netbet_rest_writer`, `netbet_stream_writer`, `netbet_analytics_reader`.
- Grants:
  - `CONNECT`/`TEMPORARY` on DB `netbet` to all three roles.
  - Appropriate `USAGE` / `CREATE` / DML permissions scoped to each schema.
  - No CREATE on `public` for `PUBLIC` or the writer/reader roles.
  - No DML permissions for `netbet_analytics_reader`.
- Sets role-level `search_path` for each role.
- Configures default privileges for owner `netbet` so future tables/sequences get the correct grants automatically.

### Passwords / secrets

Passwords are **not hardcoded** in the migration. Set them explicitly, using a secrets mechanism, for example:

```sql
-- Example (run as superuser or owner role):
ALTER ROLE netbet_rest_writer      WITH PASSWORD '<strong-secret-from-vault>';
ALTER ROLE netbet_stream_writer    WITH PASSWORD '<strong-secret-from-vault>';
ALTER ROLE netbet_analytics_reader WITH PASSWORD '<strong-secret-from-vault>';
```

On the VPS, pass these as environment variables in the `docker-compose` environment (see below) rather than committing them into the repo.


## Application / compose wiring

All services still connect to the same physical DB (`netbet` on `netbet-postgres`), but each uses its **own role and schema**.

### betfair-rest-client (REST ingestion)

- **Compose** (`docker-compose.yml`):

```44:95:C:\Users\WatMax\NetBet\docker-compose.yml
  betfair-rest-client:
    ...
    environment:
      ...
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=${POSTGRES_DB:-netbet}
      - POSTGRES_USER=${POSTGRES_REST_WRITER_USER:-netbet_rest_writer}
      - POSTGRES_PASSWORD=${POSTGRES_REST_WRITER_PASSWORD}
      - PGOPTIONS=-c search_path=rest_ingest
```

- **Usage**:
  - Define `POSTGRES_REST_WRITER_USER` / `POSTGRES_REST_WRITER_PASSWORD` in the VPS environment (e.g. `/opt/netbet/.env`).
  - `PGOPTIONS` ensures `search_path=rest_ingest` at connection time.

### streaming-client (streaming ingestion)

- **Compose** (`docker-compose.yml`):

```44:63:C:\Users\WatMax\NetBet\docker-compose.yml
  streaming-client:
    ...
    environment:
      ...
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/${POSTGRES_DB:-netbet}?currentSchema=stream_ingest
      - SPRING_DATASOURCE_USERNAME=${POSTGRES_STREAM_WRITER_USER:-netbet_stream_writer}
      - SPRING_DATASOURCE_PASSWORD=${POSTGRES_STREAM_WRITER_PASSWORD}
```

- **Usage**:
  - Define `POSTGRES_STREAM_WRITER_USER` / `POSTGRES_STREAM_WRITER_PASSWORD` in the VPS environment.
  - `currentSchema=stream_ingest` sets the JDBC search path to `stream_ingest`.

### risk-analytics-ui-api (read-only analytics API)

- **Compose – main stack** (`docker-compose.yml`):

```112:126:C:\Users\WatMax\NetBet\docker-compose.yml
  risk-analytics-ui-api:
    ...
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: ${POSTGRES_DB:-netbet}
      POSTGRES_USER: ${POSTGRES_ANALYTICS_READER_USER:-netbet_analytics_reader}
      POSTGRES_PASSWORD: ${POSTGRES_ANALYTICS_READER_PASSWORD}
      PGOPTIONS: -c search_path=analytics
```

- **Compose – standalone** (`risk-analytics-ui/docker-compose.yml`):

```5:16:C:\Users\WatMax\NetBet\risk-analytics-ui\docker-compose.yml
  risk-analytics-ui-api:
    ...
    environment:
      POSTGRES_HOST: ${POSTGRES_HOST:-postgres}
      POSTGRES_PORT: ${POSTGRES_PORT:-5432}
      POSTGRES_DB: ${POSTGRES_DB:-netbet}
      POSTGRES_USER: ${POSTGRES_ANALYTICS_READER_USER:-netbet_analytics_reader}
      POSTGRES_PASSWORD: ${POSTGRES_ANALYTICS_READER_PASSWORD}
      PGOPTIONS: -c search_path=analytics
```

- **Usage**:
  - Define `POSTGRES_ANALYTICS_READER_USER` / `POSTGRES_ANALYTICS_READER_PASSWORD` in the environment.
  - `PGOPTIONS` ensures `search_path=analytics`, so the API reads from the analytics layer only.


## Data migration plan (from public)

Current state: application tables are in schema `public`. The goal is to move them into `rest_ingest`, `stream_ingest`, and `analytics` without breaking ingestion or analytics.

### 1. Inventory current objects in `public`

Run against the `netbet` DB:

```sql
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

SELECT schemaname, sequencename
FROM pg_sequences
WHERE schemaname = 'public'
ORDER BY sequencename;

SELECT n.nspname AS schema_name, c.relname AS view_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('v', 'm') AND n.nspname = 'public'
ORDER BY view_name;
```

Also inspect functions/procedures if any:

```sql
SELECT n.nspname AS schema_name, p.proname AS function_name
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
ORDER BY function_name;
```

### 2. Decide mapping

- **REST ingestion tables** (populated only by `betfair-rest-client`):
  - Move to `rest_ingest`.

- **Streaming ingestion tables** (populated only by `streaming-client`):
  - Move to `stream_ingest`.

- **Analytics views/materialized views** (read-only, used by UI/API):
  - Move to `analytics`.
  - Views should reference ingestion tables with **schema-qualified** names (e.g. `rest_ingest.market_event_metadata`).

Document your mapping (table → target schema) before applying changes.

### 3. Move tables and sequences

For each table:

```sql
-- Example: move REST ingestion table
ALTER TABLE public.market_event_metadata SET SCHEMA rest_ingest;

-- Example: move streaming ingestion table
ALTER TABLE public.some_stream_table SET SCHEMA stream_ingest;
```

For sequences owned by those tables:

```sql
ALTER SEQUENCE public.some_table_id_seq SET SCHEMA rest_ingest;
-- or stream_ingest as appropriate
```

Because default privileges and baseline grants in `001_db_isolation.sql` operate by schema, once objects are moved, the corresponding writer roles inherit the correct DML rights.

### 4. Move analytics views/materialized views

For each view/materialized view:

```sql
-- Move view definition to analytics schema
ALTER VIEW public.some_analytics_view SET SCHEMA analytics;

-- When recreating or refactoring views, reference ingestion objects explicitly:
CREATE OR REPLACE VIEW analytics.some_analytics_view AS
SELECT ...
FROM rest_ingest.market_event_metadata mem
JOIN stream_ingest.some_stream_table s
  ON ...
WHERE ...;
```

Ensure references are **schema-qualified** so that `search_path` does not affect correctness.

### 5. Validate ingestion and analytics

After moving objects:

- **Ingestion (REST + streaming)**:
  - Run both services against the DB.
  - Confirm they can still insert/update their target tables in `rest_ingest` / `stream_ingest`.
  - Verify that they cannot create/write in other schemas (attempts should fail).

- **Analytics API**:
  - Run `risk-analytics-ui-api` and hit its endpoints.
  - Confirm queries execute correctly against `analytics` views.
  - Verify that any write attempts from the API (if accidentally coded) fail with permission errors.

### 6. Decommission application use of `public`

Once all application tables/views have been moved:

- Confirm `public` contains only extensions or system objects.
- Keep `REVOKE CREATE ON SCHEMA public FROM PUBLIC;` in place to prevent regressions.


## Backups and restores

### Backups (VPS)

From `/opt/netbet` on the VPS, using the `netbet-postgres` container:

```bash
DATE=$(date +%Y%m%d_%H%M)
BACKUP_DIR=/opt/backups/netbet/$(date +%F)
mkdir -p "$BACKUP_DIR"

DB_NAME=${POSTGRES_DB:-netbet}
DB_USER=${POSTGRES_USER:-netbet}          # owner / admin user
PG_CONTAINER=netbet-postgres

# Logical backup of entire DB (schemas + roles’ objects)
docker exec -t "$PG_CONTAINER" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -F c \
  -f "/tmp/${DB_NAME}_${DATE}.dump"

docker cp "$PG_CONTAINER:/tmp/${DB_NAME}_${DATE}.dump" \
  "$BACKUP_DIR/"
```

This captures all schemas (`rest_ingest`, `stream_ingest`, `analytics`, and remaining `public` objects).

### Restore (e.g. on a test container)

```bash
# Start a clean Postgres 16 test container
docker run --name netbet-restore-test -e POSTGRES_PASSWORD=testpass -d postgres:16-alpine

# Create DB + owner (netbet) and roles (then run 001_db_isolation.sql)
docker exec -it netbet-restore-test psql -U postgres -c "CREATE USER netbet WITH PASSWORD 'netbet';"
docker exec -it netbet-restore-test psql -U postgres -c "CREATE DATABASE netbet OWNER netbet;"

# (Optional) apply db/migrations/001_db_isolation.sql and set role passwords

# Copy dump into the container and restore
docker cp /path/to/netbet_YYYYMMDD_HHMM.dump netbet-restore-test:/tmp/netbet.dump
docker exec -it netbet-restore-test \
  pg_restore -U postgres -d netbet -c /tmp/netbet.dump
```

For production restore, follow a similar pattern but with downtime coordination and current secrets.


## Persistence behavior

- **`docker compose stop` / `docker stop`**:
  - Containers stop; the `pgdata` volume remains.
  - Data and privileges are preserved.

- **`docker compose up -d` (same project)**:
  - Containers restart and reattach to the existing `pgdata` volume.
  - Data and privileges remain intact.

- **`docker compose down` (without `-v`)**:
  - Containers are removed.
  - Volumes (including `pgdata`) remain.
  - A subsequent `docker compose up -d` reuses existing data.

- **`docker compose down -v` or `docker volume rm netbet_pgdata`**:
  - The `pgdata` volume and all DB data are deleted.
  - Next `docker compose up -d` starts with an empty DB.


## Operational notes

### Onboarding a new service

To onboard a new service that needs its own schema and role:

1. **Create schema and role** (pattern similar to `rest_ingest` / `netbet_rest_writer`).
2. **Grant privileges**:
   - `CONNECT`/`TEMPORARY` on DB.
   - `USAGE, CREATE` on the new schema.
   - DML rights as appropriate (and default privileges from owner role).
3. **Set search_path**:
   - `ALTER ROLE <role> SET search_path = <schema>;`
   - Also set via `PGOPTIONS`/`currentSchema` in the application configuration.
4. **Update compose / env**:
   - New `POSTGRES_*` username/password env vars for the service.

### Adding new tables safely

1. **Create tables via migrations** as the owner role `netbet` in the appropriate schema (`rest_ingest`, `stream_ingest`, or `analytics`).
2. **Rely on default privileges** (configured in `001_db_isolation.sql`) to grant:
   - DML to the corresponding writer role in ingestion schemas.
   - SELECT to `netbet_analytics_reader` in `analytics`.
3. **Avoid public**:
   - Always use explicit schema qualification in migrations (e.g. `CREATE TABLE rest_ingest.some_table (...);`).
4. **Verify permissions**:
   - For critical changes, connect as the writer/reader roles and confirm expected operations succeed or fail.


## Acceptance criteria mapping

- **rest client**:
  - Uses `netbet_rest_writer` with `search_path=rest_ingest`.
  - Cannot create/write outside `rest_ingest` due to schema-level REVOKEs and limited grants.

- **streaming client**:
  - Uses `netbet_stream_writer` with `currentSchema=stream_ingest`.
  - Cannot create/write outside `stream_ingest`.

- **analytics API**:
  - Uses `netbet_analytics_reader` with `search_path=analytics`.
  - Read-only by design; no INSERT/UPDATE/DELETE grants.
  - Prefers views/materialized views in `analytics` over direct access to ingestion tables.

- **No reliance on `public`**:
  - New application tables are created in `rest_ingest`, `stream_ingest`, or `analytics`.
  - `public` is locked down and not used for app tables.

- **Persistence**:
  - Data and privileges survive container restarts and redeploys while `pgdata` exists.
  - Backups/restores are documented using `pg_dump` / `pg_restore`.

