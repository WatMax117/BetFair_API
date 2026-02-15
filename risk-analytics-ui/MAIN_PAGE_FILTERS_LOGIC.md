# Main Page Filters — Exact Logic

Reference for refactoring the Risk Analytics main page (Leagues) without changing risk logic. All behaviour is defined below.

---

## 1. Time window (hours back and forward from now)

### What it filters
**Event start time** (`event_open_date` in `market_event_metadata`). It does **not** filter on snapshot timestamps.

### Where implemented
- **Frontend:** `risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`
  - `getWindowDates(hours)` (lines 21–26): `from = now - hours`, `to = now + hours` (milliseconds).
  - `from` and `to` are passed to `fetchLeagues(from, to, ...)` and `fetchLeagueEvents(league, from, to, ...)` as `from_ts` / `to_ts`.
- **API:** `risk-analytics-ui/api/app/main.py`
  - `get_leagues()` (lines 245–302): uses `from_effective` and `to_dt` in SQL.
  - `get_league_events()` (lines 306–424): same.

### Back vs forward
- **Back:** `from = now - windowHours` (e.g. 24 → from = 24h ago).
- **Forward:** `to = now + windowHours` (e.g. 24 → to = 24h from now).

### Where filtering happens
**In SQL only.** No post-filter in memory.

- Leagues: `WHERE e.event_open_date >= %s AND e.event_open_date <= %s` with `(from_effective, to_dt)`.
- Events: same predicate for `event_open_date`.

### Time zone
- **UTC everywhere.** Frontend sends `Date.toISOString()` (UTC); API parses with `_parse_ts()` and uses `datetime.now(timezone.utc)` for defaults.

### Edge cases
- **Missing event_open_date:** rows with `event_open_date IS NULL` are excluded in both leagues and events queries (`e.event_open_date IS NOT NULL` in SQL).
- API defaults when query params are omitted: `from_ts` defaults to `now`, `to_ts` to `now + 24h`. The UI always sends explicit `from_ts`/`to_ts`.

---

## 2. Include in-play events (toggle)

### What “in-play” means here
**Events that have already started** (i.e. `event_open_date < now`). It is **not** based on:

- market status (OPEN/SUSPENDED/etc.),
- event status,
- or any snapshot `inplay` flag.

The API has no “in-play” flag in the leagues/events filters; it only uses `event_open_date` and the current time.

### Effect of the toggle
- **When enabled (true):** the **left** bound of the window is extended backward for the SQL filter:  
  `from_effective = min(from_dt, now - in_play_lookback_hours)`.  
  So events that started up to `in_play_lookback_hours` ago are still included even if they are outside the user’s “time window” on the left.
- **When disabled (false):** `from_effective = from_dt` (no extension). Events are included only if their start time is in `[from_dt, to_dt]`. Events that started “long ago” can still appear if they fall inside that range (e.g. 24h window includes events from 12h ago).

So “include in-play” = “when building the filter, extend the start of the range backward so recently-started events are not cut off.”

### Where implemented
- **Frontend:** `LeaguesAccordion.tsx` — `includeInPlay` state (default `true`) passed to `fetchLeagues` and `fetchLeagueEvents`.
- **API:** `main.py` in both `get_leagues()` and `get_league_events()`:

  ```python
  if include_in_play:
      in_play_from = now - timedelta(hours=in_play_lookback_hours)
      from_effective = min(from_dt, in_play_from)
  else:
      from_effective = from_dt
  ```

### Where filtering happens
**In SQL only.** The same `event_open_date >= from_effective AND event_open_date <= to_dt` is used. There is no client-side filtering of “in-play” vs not.

---

## 3. In-play lookback (hours)

### What it does
When “Include in-play events” is on, it defines how far **back from now** the left bound can be extended:  
`in_play_from = now - in_play_lookback_hours`, and `from_effective = min(from_dt, in_play_from)`.

So it **only affects the case when in-play is included**; it does not apply when the toggle is off.

### Relative to what
**Current time (now),** not market start time. “Look back 6 hours” = “include events that started as far back as 6 hours ago.”

### Order relative to time window
1. Compute `from_dt` and `to_dt` from the time-window control (and `from_ts`/`to_ts`).
2. If `include_in_play` is true, compute `in_play_from = now - in_play_lookback_hours` and set `from_effective = min(from_dt, in_play_from)`.
3. Use `from_effective` and `to_dt` in the SQL `event_open_date` filter.

So the lookback is applied when computing `from_effective` **before** the main time-window filter; it only widens the start of the range.

### Where implemented
- **Frontend:** `LeaguesAccordion.tsx` — `inPlayLookbackHours` state (default 6), only sent when the in-play toggle is on; passed to `fetchLeagues` and `fetchLeagueEvents`.
- **API:** `main.py` — `in_play_lookback_hours` query param (default 6, range 0–168), used in the `from_effective` logic above.

---

## 4. Index highlight threshold

### Which index
**Imbalance index** (H/A/D) — i.e. `home_risk`, `away_risk`, `draw_risk` in the API and UI. It does **not** apply to Book Risk L3 or Impedance.

### Absolute vs signed
**Absolute value.** A row is highlighted if **any** of the three satisfies `Math.abs(value) > threshold`.

### Per runner or per market
**Per runner (H/A/D).** If any of home, away, or draw exceeds the threshold in absolute value, the **whole event row** is highlighted.

### Where implemented
- **Frontend only:** `risk-analytics-ui/web/src/components/EventsTable.tsx`
  - `extremeThreshold` prop (from `LeaguesAccordion` state `extremeThreshold`, default 500).
  - `isExtreme(e)` (lines 41–44):
    - `(e.home_risk != null && Math.abs(e.home_risk) > extremeThreshold) ||`
    - `(e.away_risk != null && Math.abs(e.away_risk) > extremeThreshold) ||`
    - `(e.draw_risk != null && Math.abs(e.draw_risk) > extremeThreshold)`
  - Row styling (lines 81–85): `bgcolor: isExtreme(e) ? 'action.hover' : undefined`.

No backend logic; the API returns the same data regardless of threshold.

---

## 5. Search (team / event)

### Match type
**Substring match**, case-**in**sensitive (`ILIKE` in SQL).

### Fields searched
- `event_name`
- `home_runner_name`
- `away_runner_name`  

**Not** searched: market name, league (competition) name, or any other field.

### Where implemented
- **Frontend:** `LeaguesAccordion.tsx` — `search` state; on “Search” click, `searchApplied = search.trim() || ''` and `fetchLeagues(..., searchApplied ?? undefined, ...)`. Empty string is sent when the user clears and searches (no search term).
- **API:** `main.py` `get_leagues()`:
  - If `q` is provided: `search = f"%{q}%"` and SQL:
    - `WHERE ... AND (e.event_name ILIKE %s OR e.home_runner_name ILIKE %s OR e.away_runner_name ILIKE %s)` with `(search, search, search)`.
  - If `q` is absent/empty: no search condition; only the time-window (and in-play) filter.

### Where filtering happens
**In SQL only.** Leagues are filtered by the backend. Events are not search-filtered again; they are filtered by league and time window only (events endpoint has no `q` parameter).

### Edge cases
- **Empty search:** User can click Search with no term; `searchApplied` becomes `''`, and the API receives `q` as empty/absent, so no ILIKE filter is applied (all leagues in the window are returned, subject to limit).
- **Leagues only:** Search applies only to the leagues list. Once a league is expanded, its events are not filtered by the same search term.

---

## Summary table

| Control              | Filters / affects              | Where applied | Time / index details                    |
|----------------------|--------------------------------|---------------|----------------------------------------|
| Time window          | Event start (`event_open_date`) | SQL           | UTC; back = now − N h, forward = now + N h |
| Include in-play      | Left bound of window           | SQL           | Extends `from_effective` back by lookback when on |
| In-play lookback     | Same left bound                | SQL           | Relative to now; only when in-play on   |
| Index highlight      | Row highlight in events table   | Frontend      | Imbalance only; `abs(H/A/D) > threshold` |
| Search               | Leagues by event/runner names   | SQL           | ILIKE on event_name, home_runner_name, away_runner_name |

All timestamp logic uses **UTC**. No snapshot-time or market-status filters are used for the main leagues/events list; only `event_open_date` and the derived `from_effective` / `to_dt` are used.
