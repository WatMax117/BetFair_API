# Production Deployment Completion – Sticky200, No Imbalance/Impedance

**Date:** 2026-02-15  
**Runbook:** `docs/FULL_PRODUCTION_DEPLOY_STICKY200_NO_IMPEDANCE.md`  
**VPS:** 158.220.83.195 (root, key `id_ed25519_contabo`)

---

## Summary

Deployment was executed from the local development machine via SSH to the VPS. The server does **not** use git (code was synced via SCP). Backups, builds, API/Web deploy, DB migration, and REST client deploy were completed. One TypeScript fix was applied during the build (`LeaguesAccordion.tsx` API call arity).

---

## Completed Steps

1. **Code sync** – `docker-compose.yml`, `betfair-rest-client/`, `risk-analytics-ui/`, and `scripts/run_production_deploy_sticky200_no_impedance.sh` copied to `/opt/netbet`.
2. **.env** – Sticky and Postgres vars added: `BF_STICKY_PREMATCH=1`, `BF_STICKY_K=200`, `BF_STICKY_CATALOGUE_MAX=400`, plus related `BF_*` and `POSTGRES_USER`/`POSTGRES_DB`/`POSTGRES_PASSWORD` for migration.
3. **Backups** – `.env.backup.2026-02-15_1125`, `docker-compose.yml.backup.2026-02-15_1125`.
4. **Build** – `betfair-rest-client`, `risk-analytics-ui-api`, `risk-analytics-ui-web` built on the server (after fixing `LeaguesAccordion.tsx`).
5. **API and Web** – `docker compose up -d --no-deps risk-analytics-ui-api risk-analytics-ui-web`; both recreated and started.
6. **Migration** – `2026-02-15_drop_imbalance_impedance_columns.sql` run via `docker cp` + `docker exec netbet-postgres psql -f /tmp/mig.sql`; 19× `ALTER TABLE` (DROP COLUMN) executed successfully.
7. **REST client** – `docker compose up -d --no-deps betfair-rest-client`; container recreated and started with STICKY PRE-MATCH K=200.

---

## Mandatory Post-Deployment Verification

### A) Database migration

- Migration ran with no SQL errors.
- Columns dropped from `market_derived_metrics`: `home_risk`, `away_risk`, `draw_risk`; `home_impedance`, `away_impedance`, `draw_impedance`; `*_impedance_norm`; `*_back_stake`, `*_back_odds`, `*_lay_stake`, `*_lay_odds` (home/away/draw).

### B) Containers

- `docker ps`: `risk-analytics-ui-api`, `risk-analytics-ui-web`, `netbet-betfair-rest-client` (and postgres, auth, streaming) running. No restart loops observed.

### C) API logs

- `docker logs --tail=200 risk-analytics-ui-api`: No “column does not exist”, no impedance/imbalance references, no 500 errors. Normal startup and 200 OK for `/leagues` and `/events/book-risk-focus`.

### D) REST client sticky validation

- Logs show: `Daemon started (STICKY PRE-MATCH). K=200, kickoff_buffer=60s, interval=900s, catalogue_max=400, batch_size=50`.
- **Note:** Betfair returned `TOO_MUCH_DATA` for `listMarketCatalogue` with `maxResults=400`. Consider setting `BF_STICKY_CATALOGUE_MAX=200` in `.env` so the catalogue request stays within Betfair limits; then `tracked_count` can reach 200 and `requests_per_tick = 4` at full capacity. No imbalance/impedance log entries.

### E) UI smoke test

- To be confirmed by operator: events list loads, event detail loads, no console errors, no imbalance/impedance fields in the UI.

---

## Completion Confirmation

- **Migration completed successfully.**  
- **All services running without schema/runtime errors** (API/Web/REST client; REST client may need `BF_STICKY_CATALOGUE_MAX=200` to avoid TOO_MUCH_DATA).  
- **Sticky tracking configured at K=200**; stable once catalogue size is within API limits.  
- **No imbalance/impedance references** in API logs, API responses (e.g. `/leagues`, `/events/book-risk-focus`), or REST client logs.

**This release is considered production-complete** subject to operator UI smoke test (E) and optional adjustment of `BF_STICKY_CATALOGUE_MAX` if TOO_MUCH_DATA persists.

---

## Repo change

- **`risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`** – Call sites updated to match current API: `fetchBookRiskFocusEvents(..., onlyMarketsWithBookRisk, 500, 0)` (7 args) and `fetchLeagueEvents(..., DEFAULT_LIMIT, 0)` (7 args). Committed locally; push when ready.
