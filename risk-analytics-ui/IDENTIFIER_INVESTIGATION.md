# Event vs Markets identifier investigation

This document explains how event/market identifiers flow from the UI to the markets lookup, why an id like `1.251575028` can return 404, and what (if anything) to change.

---

## 1. Where does the `event_id` used by the UI come from?

### Events list source

- **API:** `GET /api/leagues/{league}/events`
- **Backing table:** `market_event_metadata` joined with `market_derived_metrics` (latest snapshot per market).
- **Query:**  
  `FROM market_event_metadata e JOIN latest l ON l.market_id = e.market_id`  
  filtered by `competition_name`, `event_open_date` window, etc.

So the “events” list is **one row per market** (not one row per Betfair event). Each row has:

- **`market_id`** — from `market_event_metadata.market_id` (PK).
- **`event_id`** — from `market_event_metadata.event_id` (nullable, Betfair event id from catalogue).

The API returns both in the payload. The **Risk Debug View** (post-apache) stores both in data attributes (`data-market-id`, `data-event-id`) but **only uses `market_id`** when calling the markets endpoint (see below).

---

## 2. Which tables/columns does the markets lookup use?

- **Endpoint:** `GET /api/debug/events/{event_or_market_id}/markets`
- **Table:** `market_event_metadata` only.

Lookup order:

1. **By `event_id`:** `WHERE e.event_id = %s` → return all markets for that event.
2. **By `market_id`:** one row `WHERE market_id = %s`, then all rows with same `event_id`.
3. **Fallback:** if that market has no `event_id` (or no siblings), return that single market.
4. **404** only if there is no row for the given id as `event_id` and no row as `market_id`.

So both `event_id` and `market_id` are expected to exist in **`market_event_metadata`**. The events list is built from the same table (plus metrics). So any `market_id` that appears in the events list **should** exist in `market_event_metadata` and should be findable by the markets lookup — **as long as the list and the markets request hit the same DB and the row still exists**.

---

## 3. For IDs like `1.251575028`

### Format

- **Betfair market_id:** typically string like `"1.123456789"` (numeric with a dot).  
  So **`1.251575028` looks like a market_id**, not an event_id.
- **Betfair event_id:** typically an integer (e.g. `32512345`), from listMarketCatalogue `event.id`, stored as TEXT in `market_event_metadata.event_id`.

So `1.251575028` is almost certainly intended as a **market_id**.

### Why 404?

The endpoint returns 404 only when:

- There is **no** row in `market_event_metadata` with `event_id = '1.251575028'`, **and**
- There is **no** row with `market_id = '1.251575028'`.

So for this id, **neither** column has that value in the table. That implies one or more of:

1. **Market never ingested** — listMarketCatalogue / ingest never stored this market.
2. **Different DB / environment** — the events list (or the id) comes from another replica, schema, or env where this market exists; the markets request hits a DB where it does not.
3. **Row removed** — row was deleted after the events list was loaded (rare).
4. **Id from elsewhere** — the id was not taken from the Risk Debug View events list (e.g. manual URL, bookmark, or another UI that sends a different kind of id).

So this is a **data / model consistency** issue: the id the UI sends is not present in the table(s) the lookup uses, not a routing or deploy bug.

---

## 4. Canonical event identifier and consistency

### Betfair model

- **Event** (e.g. “Man Utd vs Liverpool”): id = **event_id** (integer).
- **Market** (e.g. “Match Odds”): id = **market_id** (string like `"1.123456"`).
- One event has many markets. `market_event_metadata` has one row per market and stores both `market_id` (PK) and `event_id` (nullable, from catalogue).

### How it’s used today

- **Events list:** One row per **market** from `market_event_metadata` (+ latest metrics). So the natural key for each list row is **market_id**. **event_id** is the canonical Betfair id that groups markets.
- **Markets lookup:** Accepts either **event_id** or **market_id**; both are resolved in **market_event_metadata** only. So:
  - If the UI sends **event_id**, we return all markets for that event.
  - If the UI sends **market_id**, we find that market and return all markets for the same event (or that single market as fallback).

So the **canonical event identifier** for “all markets for this event” is **event_id**. The **canonical row identifier** for the current list is **market_id**. The backend supports both.

### Risk Debug View behaviour

- Events list: `GET /api/leagues/{league}/events` → each item has `market_id` and `event_id`.
- On event click: **only `market_id`** is used:  
  `showEventDetail(eventEl.dataset.marketId, …)` → `loadMarkets(marketId)` →  
  `GET /api/debug/events/{marketId}/markets`.

So the Debug View always calls the markets endpoint with a **market_id** that came from the same API. In normal conditions (same backend, same DB, row present), that market_id **should** exist in `market_event_metadata` and the lookup should succeed. The 404 for `1.251575028` means that value is not in the table (for the DB the API uses).

---

## 5. Summary and options

### Summary

| Question | Answer |
|----------|--------|
| Where does event_id in the UI come from? | Same place as market_id: `market_event_metadata` via `GET /api/leagues/{league}/events`. Both columns are returned; the Debug View only uses **market_id** for the markets call. |
| Which table does the markets lookup use? | **market_event_metadata** only. It looks up by `event_id` first, then by `market_id`. |
| Why does `1.251575028` 404? | That value is not present as **event_id** or **market_id** in `market_event_metadata` (for the DB the API uses). It looks like a market_id; likely the market was never ingested, or the id comes from another env/source. |
| Canonical identifier? | **event_id** = Betfair event (groups markets). **market_id** = primary key for list rows and for “expand to all markets for this event”. Backend supports both. |

### Options (no code change in this doc)

1. **Align on one id in the UI (recommended)**  
   - Prefer **event_id** for the “Event → Markets” step when available: call  
     `GET /api/debug/events/{event_id}/markets`  
     so the backend can return all markets by event in one go and avoid depending on a single market row.  
   - If `event_id` is null for some rows (catalogue didn’t provide it), keep using **market_id** for those so the existing market_id path handles them.

2. **Verify data**  
   - On the DB used by the API, run:  
     `SELECT market_id, event_id FROM market_event_metadata WHERE market_id = '1.251575028' OR event_id = '1.251575028';`  
   - If no rows: that market was never ingested or is in another DB; fix ingest or point the UI at the correct backend.

3. **Debug-only fallback (optional)**  
   - If you need the drill-down to work even when `event_id` is missing or the id is ambiguous, you could add a **debug-only** fallback that resolves by (e.g.) `event_name` + `event_open_date` in `market_event_metadata` and returns those markets. That would be a separate, optional change and should be clearly scoped to the debug tool.

---

## 6. Quick reference

| Layer | Source | Identifier used for “event” row | Identifier for “all markets for this event” |
|-------|--------|-----------------------------------|---------------------------------------------|
| Events list | `market_event_metadata` + `market_derived_metrics` | `market_id` (PK) | `event_id` (nullable) |
| Markets lookup | `market_event_metadata` | Accepts `event_id` or `market_id` | Same table |
| Risk Debug View | Events from API above | Sends **market_id** to `/debug/events/{id}/markets` | Could send **event_id** instead when present |

So: **current IDs are aligned** (same table, same columns). The 404 for `1.251575028` means that value is simply not in `market_event_metadata` for the API’s DB. Next step is either fix data/ingest or, in the UI, prefer `event_id` when available for the markets call.
