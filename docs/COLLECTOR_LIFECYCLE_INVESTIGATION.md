# Collector Lifecycle Failure – Investigation Checklist

## Problem Summary

- Snapshots stop around **~60 minutes** after kickoff.
- No markets reach **≥100 minutes**.
- No **CLOSED** status is ever written.

Goal: determine whether the collector stops requesting data, scheduler unsubscribes markets, requests fail silently, data is fetched but not persisted, or lifecycle state is lost after restart.

---

## Phase 1 – Do Requests Continue After 60 Minutes?

### Task 1.1 – HTTP request logs

The REST client does **not** log per-market request timestamps after 60′ in a way that identifies “still polling market X.” Each tick logs `tick_id`, `duration_ms`, `markets_count`, and `[Imbalance] Market: <id>`. To confirm whether requests are still sent for a given market after 60′:

- For 3–5 affected `market_id`s, search container logs for that `market_id` and timestamps after `event_start_time_utc + 60 min`.
- If **no** log lines for that market after 60′ → scheduler/tracking has effectively stopped including that market (see 1.2).

### Task 1.2 – Active market tracking (**root cause identified**)

**Finding: There is no persistent “active markets” list or per-market TTL.**

Relevant code: `betfair-rest-client/main.py`

- **Catalogue window (lines 159–161):**
  - `from_ts = now - timedelta(minutes=LOOKBACK_MINUTES)`  → **LOOKBACK_MINUTES = 60**
  - `to_ts = now + timedelta(hours=WINDOW_HOURS)`         → **WINDOW_HOURS = 24**
  - So the **catalogue** returns markets whose **start time** is in `[now − 60 min, now + 24 h]`.

- **No TTL / max_runtime / unsubscribe:**
  - No `max_runtime`, `ttl`, `cleanup`, `inactivity_timeout`, `stop_after_halftime`, or `max_age`.
  - No explicit “stop tracking” or “unsubscribe” for a market.

- **What actually happens each tick (every INTERVAL_SECONDS = 900 s ≈ 15 min):**
  1. Call **listMarketCatalogue** with the above time range, `sort="MAXIMUM_TRADED"`, `max_results=max(200, MARKET_BOOK_TOP_N)` (default **10**).
  2. Keep only 3-runner (Match Odds) markets; take the **top MARKET_BOOK_TOP_N (10)** by traded volume.
  3. **Upsert metadata** for those 10; then **listMarketBook** only for those 10 `market_id`s; **insert** snapshots.

So the “active” set is **recomputed every 15 minutes** from the current catalogue. A market is polled only while it is in the **current** top‑N by `MAXIMUM_TRADED`. Once it drops out (e.g. other matches trade more, or the catalogue window moves), it is **never requested again** → no more snapshots, and we never request it when it is CLOSED.

**Conclusion (Phase 1):** The collector does **not** “follow” a market for its full lifecycle. It effectively “unsubscribes” markets by **replacing** the active set every tick with the current top‑N. No hard-coded 60‑minute cutoff exists; the ~60‑minute cap is a **consequence of markets dropping out of top‑N** (and possibly catalogue window/volume sort), not a single TTL variable.

---

## Phase 2 – Data Fetched but Not Persisted?

### Task 2.1 – Requests vs DB inserts

- **Requests:** Only the current top‑N market IDs are requested each tick. If a market is not in that set, there are **0 requests** for it after it drops out.
- **Inserts:** Every successful listMarketBook response is persisted (see `_insert_raw_snapshot` and `_insert_derived_metrics`). There is no filter that drops snapshots after 60′.
- **Interpretation:** For markets that have dropped out of top‑N: **0 requests → 0 inserts** (scheduler/tracking, not persistence).

### Task 2.2 – Market status handling

**Finding: No filter on status.**

- `main.py` (e.g. ~803–807): `status = book.get("status")` (or equivalent); passed to `_insert_raw_snapshot(..., status=status, ...)`.
- All API statuses (OPEN, SUSPENDED, IN_PLAY, CLOSED, etc.) are persisted when a snapshot is written.
- There is **no** `if status != OPEN: skip` or logic that drops non-OPEN states.

So CLOSED would be stored **if** we ever called listMarketBook for that market when it was CLOSED. We do not, because we stop requesting the market once it leaves the top‑N.

---

## Phase 3 – Process stability

### Task 3.1 – Collector restarts

- Check container restarts (e.g. `docker inspect`, orchestrator logs), OOM kills, deployments.
- **State rehydration:** The daemon holds **no** in-memory “active markets” list across restarts. Each tick rebuilds the active set from the catalogue. So a restart does not “forget” to re-subscribe specific markets; the design is already “no persistent subscription list.”
- If restarts happen mid-match, the same behaviour applies after restart: only the current top‑N from the catalogue are polled.

---

## Phase 4 – Rate limiting / backpressure

### Task 4.1 – Metrics

- No built-in metrics (requests/s, error rate, timeouts, retries, queue depth) were found in the codebase. Would need to be added (e.g. logging or metrics middleware).
- **TICK_DEADLINE_SECONDS = 600** (10 min): if a single tick exceeds this, that tick aborts; next tick still uses a fresh top‑N from the catalogue.

### Task 4.2 – Upstream errors

- Search logs for 429, 401/403, 5xx, timeouts. These can cause a tick to fail or back off but do not by themselves explain the systematic ~60‑minute stop; the main driver is the top‑N catalogue design.

---

## Phase 5 – Kickoff time

- `event_start_time_utc` comes from the catalogue (`event_open_date` / market start) and is stored in `market_event_metadata`. No separate “expiry” or “stop tracking at kickoff + X” logic was found.
- Incorrect kickoff would affect coverage analysis but is not the cause of “stop at ~60 min”; that is explained by markets leaving the top‑N.

---

## Phase 6 – CLOSED status in DB (global check)

Run on the DB (e.g. VPS):

```sql
SELECT status, COUNT(*) AS cnt
FROM market_book_snapshots
GROUP BY status
ORDER BY cnt DESC;

SELECT COUNT(*) AS closed_count
FROM market_book_snapshots
WHERE status = 'CLOSED';
```

- If **closed_count = 0** globally → CLOSED is never persisted, consistent with “we never request a market after it leaves top‑N,” so we never see it when CLOSED.
- If **closed_count > 0** → CLOSED is stored when we do request a market in that state; the issue would be time-window or which markets we request.

**Script:** `scripts/check_closed_status.sql` (run via `psql` or `docker exec netbet-postgres psql ...`).

**Result (VPS run):**
```text
status    | count
----------+-------
OPEN      | 12391
SUSPENDED | 222
```
No row for `CLOSED` → **closed_count = 0** globally. CLOSED is never persisted because we never request a market once it has left the top‑N (so we never see it when CLOSED).

---

## Phase 7 – Most likely root cause

| # | Cause | Evidence |
|---|--------|----------|
| 1 | **Scheduler replaces “active” set every tick with top‑N by MAXIMUM_TRADED** | No persistent active list; each tick uses listMarketCatalogue + top MARKET_BOOK_TOP_N; markets drop out and are never polled again. |
| 2 | Collector restarts without rehydrating “active” markets | N/A – there is no such list; each tick is stateless from catalogue. |
| 3 | Rate limiting causing silent drop of late-match polling | Possible but secondary; design already limits to top‑N per tick. |
| 4 | CLOSED not persisted | We never request markets after they leave top‑N, so we never receive or persist CLOSED for them. |

**Summary:** The ingestion lifecycle stops for a market when that market **drops out of the top‑N (by MAXIMUM_TRADED) on a catalogue refresh**. There is no “follow this market until CLOSED” behaviour. The ~60‑minute cap and absence of CLOSED are consistent with this design.

---

## Expected deliverables (engineering)

1. **Requests after 60′:** For a given market, requests stop when it is no longer in the top‑N for that tick (no explicit “stop after 60 min”).
2. **DB inserts after 60′:** Inserts stop for that market when requests stop (no insert filter by time or status).
3. **CLOSED in DB:** Run Phase 6 SQL; if 0 globally, confirm we never request markets when CLOSED because we stop requesting them once they leave top‑N.
4. **Restarts:** Confirm whether restarts occur; design does not rely on rehydration of active markets.
5. **TTL / max_age / stop conditions:** No per-market TTL; the only “stop” is **not being in the current top‑N** from the catalogue.

---

## Success criteria (for full lifecycle coverage)

We need at least some markets to have:

- `final_snapshot_t_from_kickoff_min >= 100`
- ≥1 snapshot in the 90–150 minute window
- ≥1 `market_status = 'CLOSED'`

To get there, the collector (or a dedicated “lifecycle” path) must **continue to request** selected markets until they are CLOSED (or a defined end window), e.g.:

- Persistent “active” set for in-play markets that is updated by kickoff/catalogue and only removed when status is CLOSED (or similar), or
- A separate process that subscribes to a fixed set of market IDs for the full match length,

in addition to (or instead of) the current “top‑N this tick only” behaviour.

---

*References: `betfair-rest-client/main.py` (catalogue window, top‑N, no status filter, status persisted as returned).*
