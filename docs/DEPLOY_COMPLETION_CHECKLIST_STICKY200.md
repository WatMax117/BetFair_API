# Production Deploy Completion Checklist – Sticky200, No Impedance

After running the full deployment (see `FULL_PRODUCTION_DEPLOY_STICKY200_NO_IMPEDANCE.md` or `scripts/run_production_deploy_sticky200_no_impedance.sh`), confirm:

---

## 1. Migration executed successfully

- [ ] `risk-analytics-ui/sql/migrations/2026-02-15_drop_imbalance_impedance_columns.sql` ran without SQL errors.
- [ ] `\d market_derived_metrics` shows that these columns **no longer exist**:
  - `home_risk`, `away_risk`, `draw_risk`
  - `home_impedance`, `away_impedance`, `draw_impedance`
  - `home_impedance_norm`, `away_impedance_norm`, `draw_impedance_norm`
  - `home_back_stake`, `home_back_odds`, `home_lay_stake`, `home_lay_odds` (and away/draw equivalents).

---

## 2. All services running without schema/runtime errors

- [ ] `docker ps` shows `risk-analytics-ui-api`, `risk-analytics-ui-web`, `netbet-betfair-rest-client` (and postgres/auth/streaming as applicable) running.
- [ ] `docker logs risk-analytics-ui-api` – no missing-column or schema errors.
- [ ] `docker logs risk-analytics-ui-web` – no startup errors.
- [ ] `docker logs netbet-betfair-rest-client` – no missing-column or schema errors.

---

## 3. Sticky tracking stable at K=200

- [ ] REST client logs show `tracked_count` reaching **200** when enough pre-match markets exist.
- [ ] At full capacity, `requests_per_tick = 4`.
- [ ] `.env` has `BF_STICKY_PREMATCH=1`, `BF_STICKY_K=200` (and related vars as in runbook Phase 4.1).

---

## 4. No imbalance/impedance references in logs or responses

- [ ] No `[Imbalance]` or `[Impedance]` in `docker logs netbet-betfair-rest-client`.
- [ ] No `impedance`, `imbalance`, `home_risk`, `away_risk`, `draw_risk` (or related) in API response bodies (e.g. `/leagues`, `/events/book-risk-focus`, event timeseries).
- [ ] UI: no labels or columns for Imbalance/Impedance; browser console has no errors about missing fields or impedance/imbalance.

---

When all items are checked, the release can be marked **production-complete**.
