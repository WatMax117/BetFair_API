# REST Discovery (Hourly) – Metadata Only

Soccer, **Full-Time markets only**. No Half-Time. No odds/snapshots.

## What it does

- Runs **at HH:00:17** (17 seconds past the hour) when invoked at HH:00:00 (script sleeps 17s).
- Calls Betfair **listMarketCatalogue** for Soccer with:
  - `MATCH_ODDS` (Full Time 1X2)
  - `OVER_UNDER_2_5` (2.5 goals)
  - `NEXT_GOAL`
- **Excludes** all Half-Time types (HALF_TIME, HALF_TIME_SCORE, MATCH_ODDS_HT, OVER_UNDER_05_HT, etc.).
- **Persists to DB:**
  - **rest_events** – eventId, eventName, openDate, competition, home/away team.
  - **rest_markets** – marketId, marketType, marketName, marketStartTime.
  - **runners** – selectionId + runnerName per market.
  - **market_event_metadata** – one row per market with home/away/draw selection IDs and names (for 3-way markets).
- **Does not** call listMarketBook. **Does not** write to market_book_snapshots or market_derived_metrics.

The stream client reads **active_markets_to_stream** (view over rest_markets, FT only) and subscribes by those market IDs.

### NEXT_GOAL follow-up

- For each discovered event where **NEXT_GOAL is not present at kickoff**, one additional REST check is run **117 seconds after kickoff**.
- That request queries **only** `NEXT_GOAL` for that `eventId`.
- If found, upserts into `rest_markets` + runners + metadata (same as main discovery), so it appears in `active_markets_to_stream`.
- Idempotent (no duplicate rows). Logs: eventId, kickoff time, follow-up time, found/not found, inserted marketId(s).
- **Kickoff postponed**: reschedules automatically (uses current `open_date` from rest_events; next run will use new kickoff).
- **Event cancelled/closed** before follow-up: API returns empty; logged as not found; no retry.

## Env (same as main REST client)

- `BF_USERNAME` / `BETFAIR_USERNAME`
- `BF_PASSWORD` / `BETFAIR_PASSWORD`
- `BF_APP_KEY` / `BETFAIR_APP_KEY`
- `BF_CERT_PATH`, `BF_KEY_PATH` (cert for login)
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

## Run

```bash
cd betfair-rest-client
python discovery_hourly.py
```

## Cron (hourly at HH:00:00; script runs at HH:00:17)

```bash
0 * * * * cd /opt/netbet/betfair-rest-client && . ../.env 2>/dev/null; python discovery_hourly.py >> /var/log/discovery_hourly.log 2>&1
```

The script sleeps 17 seconds at start so the main discovery and follow-up logic run at HH:00:17.

Adjust paths and env loading to your setup.

## Validation

See **docs/SOCCER_FT_ONLY_VALIDATION.md** for counts, SQL checks, and evidence.
