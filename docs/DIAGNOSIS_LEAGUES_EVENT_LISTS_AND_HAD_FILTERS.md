# Diagnosis: Missing Event Lists in Leagues View + H/A/D Index Filters

**Date:** 2026-02-15  
**Scope:** (A) Why event lists disappeared, (B) Live + Upcoming, (C) H/A/D Book Risk L3 filters.

---

## A) Root cause summary – missing event lists

### 1. Are the API calls happening?

- **Leagues:** `GET /api/leagues` is called when the user clicks **Search** (with or without a term). Params: `from_ts`, `to_ts`, `include_in_play`, `in_play_lookback_hours`, `limit`, `offset`, and optionally `q`.
- **Events:** `GET /api/leagues/{league_name}/events` is called **on expand** of a league (lazy load). Params: same `from_ts`, `to_ts`, `include_in_play`, `in_play_lookback_hours`, `limit`, `offset`.

**How to verify:** DevTools → Network. After clicking Search, expand a league. You should see one request to `/api/leagues/.../events` with the same window as the leagues request. If the request does not fire, the bug is in expand/state (e.g. `eventsByLeagueRef.current[league]` already set).

### 2. Are they returning empty?

- If the **events** request returns `200` with body `[]`, the UI correctly shows “No events in this league for the selected window.”
- If the request **fails** (4xx/5xx or network error), the UI previously **swallowed the error** and showed the same empty message with no way to retry.

**Fix applied:** Per-league fetch errors are now stored in `eventsErrorByLeague`. On failure we show the error message and a **Retry** button that clears cache and refetches. So empty due to **failure** is distinguishable from empty due to **no data**.

### 3. Is there a mismatch between “count” and “events list”?

- **No.** Both use the same source:
  - **Count:** `GET /api/leagues` uses `from_effective` and `to_dt` (and optional search). Same `from_ts` / `to_ts` / `include_in_play` / `in_play_lookback_hours` as in the UI’s `getFilterWindow(eventFilterMode)`.
  - **Events:** `GET /api/leagues/{league_name}/events` uses the **same** `from_ts`, `to_ts`, `include_in_play`, `in_play_lookback_hours` from the same `from`/`to`/`includeInPlay`/`inPlayLookbackHours` in the accordion (same `eventFilterMode`).
- So “Italian Serie A (5 events)” and the events list for that league use the same window. If the DB has 5 events in that window for that league, the events endpoint returns 5. If it returns 0, possible causes: **league name** (e.g. encoding or exact `competition_name` match), **timezone** (client `now` vs server `now`), or **data** (no rows in DB for that league in that window).

### 4. UI caching / state

- On **Events mode change** (Upcoming / Live + Upcoming / All), we clear `eventsByLeague` and `eventsErrorByLeague`, so expanding again refetches with the new window.
- We **do** cache empty results: if the API returns `[]`, we store `eventsByLeague[league] = []` and do not refetch on next expand. That is intentional; use **Retry** if you suspect a transient failure.
- Expand only triggers a fetch when `!eventsByLeagueRef.current[league]` (never loaded for that league). So first expand = fetch; subsequent expands = use cache.

**Conclusion (A):**  
- API calls **do** happen (leagues on Search, events on expand).  
- Empty list can be either **no data** or **fetch error**; errors are now surfaced with Retry.  
- **No** count vs events window mismatch; same params for both.  
- Caching is correct; clearing on mode change avoids stale lists.

---

## B) Live + Upcoming (“active” loading)

**Requirement:** Load active events (recently started or in-play). “Live + Upcoming” should broaden the window into the past.

**Implementation:**

- **Mode “Live + Upcoming”** uses `getFilterWindow('live_and_upcoming')`:
  - `from` = now − **2 hours** (configurable via `IN_PLAY_LOOKBACK_HOURS_DEFAULT` in `LeaguesAccordion.tsx`, currently 2).
  - `to` = now + 48 hours.
  - `includeInPlay` = true.
  - `inPlayLookbackHours` = 2.

- The UI sends:
  - `from_ts`, `to_ts` (ISO UTC),
  - `include_in_play=true`,
  - `in_play_lookback_hours=2`.

- The API (`main.py`) uses the same logic: when `include_in_play` is true, it sets `in_play_from = now - timedelta(hours=in_play_lookback_hours)` and `from_effective = min(from_dt, in_play_from)`, and filters with `event_open_date >= from_effective` and `event_open_date <= to_dt`. So events that started in the last 2 hours (or up to 48h for “All”) are included.

**If “active” events still don’t appear:** Increase `IN_PLAY_LOOKBACK_HOURS_DEFAULT` to **6** in `LeaguesAccordion.tsx` (single constant; used for both UI window and param), or add a small UI control for lookback hours.

**Deliverable B:**  
- “Live + Upcoming” sends `include_in_play=true`, `in_play_lookback_hours=2`, `from_ts` = now−2h, `to_ts` = now+48h.  
- API respects these and returns events with `event_open_date >= now - lookback`.  
- To get more in-play/recent events, increase the constant to 6h (or expose a control).

---

## C) H/A/D index filtering (Book Risk L3)

**Requirement:** Filter events by thresholds on Home / Away / Draw Book Risk L3 (absolute value).

**Implementation:**

- **UI:** Three numeric inputs (H, A, D) for minimum **absolute** value of `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`. Plus “Match all (vs any)” switch: **any** = event passes if at least one of |H|, |A|, |D| meets its minimum; **all** = all three must meet their minimums. Default: 0 = no filter; “any”.
- **Where applied:**
  - **League accordion:** Events for each league are filtered with the same H/A/D logic before being passed to `EventsTable`. So “(5 events)” is the raw count; the table may show fewer rows when H/A/D filters are set.
  - **Book Risk focus list:** `focusEventsFiltered` is further filtered by the same H/A/D logic and passed to `SortedEventsList`.
- **Data source:** `/api/leagues/{league}/events` and `/api/events/book-risk-focus` already return `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`. Filtering is **UI-side** only; no API change.
- Sorting and “Book Risk focus” mode are unchanged; filters are applied to the same lists before display.

**Deliverable C:**  
- Three threshold inputs + “Match all” added.  
- Filtering applied to league events and to the Book Risk sortable list.  
- Validation: set e.g. min H = 100; only events with |home_book_risk_l3| ≥ 100 (or meeting “any”/“all” rules) remain.

---

## Acceptance criteria (after changes)

1. **Expanding a league** loads the events list; if the request fails, an error message and **Retry** are shown instead of a silent empty list.
2. **“Live + Upcoming”** uses a 2h lookback (configurable) and correct API params so active/recently started events can appear; increase lookback to 6h if needed.
3. **H/A/D filters** (min |H|, |A|, |D| and any/all) apply to both the league events table and the Book Risk focus list, with results updating as thresholds change.

No existing behaviour was removed; only minimal, safe changes and the above validation steps (Network + sample responses) were added.
