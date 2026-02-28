# Settlement tables (V11): verify DB and deploy

**Goal:** Confirm settlement tables exist in the correct database and that the app uses that same DB/schema. Make V11 deterministic by having the migration tracked so Flyway applies it on every rebuild.

**Root cause we avoid:** V11 was not in the built JAR because the migration file was untracked. Rebuilds or new environments then had no settlement tables until someone applied V11 manually again.

---

## A. Confirm you are looking at the correct Postgres and database

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
docker exec -it netbet-postgres psql -U netbet -d postgres -c "\l"
```

Use the intended Postgres container name (e.g. `netbet-postgres`) and database (e.g. `netbet`), not `postgres` or another DB.

---

## B. Verify settlement tables exist (and where)

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT current_database() AS db, current_user AS db_user;
SHOW search_path;
"
```

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT
  to_regclass('stream_ingest.market_settlement') AS market_settlement,
  to_regclass('stream_ingest.market_runner_settlement') AS market_runner_settlement;
"
```

- Non-null = tables exist in this DB.
- Null = tables do not exist (or wrong schema).

List any settlement-like tables:

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT schemaname, tablename
FROM pg_catalog.pg_tables
WHERE tablename ILIKE '%settle%'
ORDER BY schemaname, tablename;
"
```

---

## C. If “fixed yesterday” but missing today

Often: different container, different volume, or different DB/schema.

```bash
docker inspect netbet-postgres --format '{{json .Mounts}}' | jq .
docker volume ls
```

If Postgres was recreated without the same volume, manually created tables are gone.

---

## D. Flyway status

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT to_regclass('stream_ingest.flyway_schema_history') AS flyway_history;
"
```

(Streaming client uses schema `stream_ingest`; if Flyway history is in `public`, adjust.)

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT version, description, script, installed_on, success
FROM stream_ingest.flyway_schema_history
WHERE script ILIKE '%V11%' OR script ILIKE '%settle%'
ORDER BY installed_on;
"
```

If your Flyway history table is in `public`:

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT version, description, script, installed_on, success
FROM public.flyway_schema_history
WHERE script ILIKE '%V11%' OR script ILIKE '%settle%'
ORDER BY installed_on;
"
```

- No V11 row → Flyway never applied it (e.g. migration was not in the JAR).
- V11 present but tables missing → wrong DB/schema or manual apply was elsewhere.

---

## E. Streaming client: same DB as the one you inspect

```bash
docker exec -it netbet-streaming-client sh -c 'env | grep -iE "jdbc|datasource|postgres|flyway|schema"'
```

Confirm host/port/db match the Postgres container and database you use in A–B.

---

## F. Settlement data (if tables exist)

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT COUNT(*) AS markets FROM stream_ingest.market_settlement;
SELECT COUNT(*) AS runner_rows FROM stream_ingest.market_runner_settlement;
"
```

Zero counts: either no closed markets yet, or writes go to another DB/schema, or REST fallback not running.

---

## G. Make V11 permanent (migration in repo)

V10 and V11 are now tracked so the JAR includes them:

- `betfair-streaming-client/src/main/resources/db/migration/V10__market_type_recovery.sql`
- `betfair-streaming-client/src/main/resources/db/migration/V11__market_settlement_tables.sql`

On VPS after pull, rebuild streaming client so Flyway runs with the new JAR:

```bash
cd /opt/netbet
git pull origin master
docker compose build --no-cache netbet-streaming-client
docker compose up -d --no-deps netbet-streaming-client
```

Check logs for Flyway applying V11 (or query `flyway_schema_history` as in D).

---

## H. Manual apply (only if needed)

Always target the same DB and schema:

```bash
docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 <<'SQL'
SET search_path TO stream_ingest;
-- paste V11__market_settlement_tables.sql here, or pipe from file
SQL
```

Verify:

```bash
docker exec -it netbet-postgres psql -U netbet -d netbet -c "
SELECT to_regclass('stream_ingest.market_settlement'),
       to_regclass('stream_ingest.market_runner_settlement');
"
```

---

## What to paste back when debugging

1. `docker ps` table output  
2. `to_regclass(...)` result for both settlement tables  
3. `SHOW search_path;`  
4. Streaming-client env grep (DB-related)  
5. Database list (`\l`) or the DB name in use  

That confirms whether the “yesterday fix” was on the same DB/schema/volume the services use today.
