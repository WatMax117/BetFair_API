# Apply V11 settlement tables on VPS

When the event meta API returns "Result: — (settlement not recorded)" and you see `relation "stream_ingest.market_settlement" does not exist`, the settlement tables from migration **V11** are not present yet.

## Option A: Let Flyway apply V11 (recommended)

The streaming client runs Flyway at startup with schema `stream_ingest`. If the deployed JAR includes V11:

1. Ensure the VPS has the streaming client code that contains `V11__market_settlement_tables.sql` (e.g. in `betfair-streaming-client/src/main/resources/db/migration/`).
2. Rebuild and restart the streaming client so Flyway runs and applies pending migrations (including V11):
   ```bash
   cd /opt/netbet
   docker compose build netbet-streaming-client   # or the service name you use
   docker compose up -d --no-deps netbet-streaming-client
   ```
3. Check Flyway logs to confirm V11 was applied, then run the settlement date-range script to see from when you have data.

## Option B: Apply V11 manually with psql

If you cannot restart the streaming client or need the tables immediately:

1. Run the V11 migration SQL with `search_path` set so tables are created in `stream_ingest`:

   From your machine (pipe the migration file over SSH):

   ```powershell
   Get-Content -Raw "c:\Users\WatMax\NetBet\betfair-streaming-client\src\main\resources\db\migration\V11__market_settlement_tables.sql" | ssh netbet-vps "docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 -c \"SET search_path TO stream_ingest;\" -f -"
   ```

   Or on the VPS (after copying the file or cloning the repo):

   ```bash
   docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 <<'SQL'
   SET search_path TO stream_ingest;
   -- paste contents of V11__market_settlement_tables.sql here, or:
   \ir /path/on/host/to/V11__market_settlement_tables.sql
   SQL
   ```

   Simpler from repo root on VPS after `git pull`:

   ```bash
   (echo "SET search_path TO stream_ingest;"; cat betfair-streaming-client/src/main/resources/db/migration/V11__market_settlement_tables.sql) | docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 -f -
   ```

2. Verify:
   ```bash
   docker exec -i netbet-postgres psql -U netbet -d netbet -t -c "SELECT COUNT(*) FROM stream_ingest.market_settlement;"
   ```
   (Should return 0 until settlement data is written.)

## After V11 is applied

- The streaming client will write to `stream_ingest.market_settlement` and `stream_ingest.market_runner_settlement` when markets close (MATCH_ODDS_FT, CLOSED).
- Optional: run the REST settlement fallback script to backfill from listMarketBook for closed markets.
- Check settlement date range (from your machine or on VPS after `git pull`):
  ```powershell
  Get-Content -Raw "c:\Users\WatMax\NetBet\scripts\settlement_date_range.sql" | ssh netbet-vps "docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1 -f -"
  ```
