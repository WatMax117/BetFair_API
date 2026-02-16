# Leagues page simplified — Top 200 current events (deliverable)

**Date:** 2026-02-15

---

## Summary

The main Leagues page has been replaced with a single, stable view:

- **One API call on load:** `GET /events/book-risk-focus` with `limit=200`, `from_ts=now`, `to_ts=now+48h`, `include_in_play=false`, `require_book_risk=true`.
- **One list:** Up to 200 current/upcoming events (no league accordion, no search, no extra filters/toggles).
- **Sorting:** Primary = Book Risk L3 H / A / D (and Volume), with Asc/Desc and Signed vs Absolute. Tie-breakers: volume desc, event_open_date asc, market_id asc.

---

## Before / after

| Before | After |
|--------|--------|
| League accordion (expand per league) | Removed |
| Events dropdown (Upcoming / Live+Upcoming / All) | Removed |
| Search + Search button + Refresh | Removed |
| H/A/D filter inputs + Match all | Removed |
| Book Risk focus toggle | Removed (page is always the focus list) |
| Only active in-play / Only markets with Book Risk toggles | Removed (not passed to list) |
| Multiple fetches (leagues, then per-league events) | Single fetch on load |

| After (current) |
|-----------------|
| Title: "Top 200 current events" |
| One fetch: `/events/book-risk-focus` with limit=200 |
| Single sortable table: Event name, Market ID, Open date, Book Risk H/A/D, Volume |
| Controls: Sort by (H/A/D/Volume), Descending, Signed vs Absolute |
| Tie-breakers: volume desc, event_open_date asc, market_id asc |

---

## Endpoint and 200 items

- **Endpoint:** `GET /api/events/book-risk-focus`
- **Query params used:** `from_ts`, `to_ts` (now → now+48h UTC), `include_in_play=false`, `in_play_lookback_hours=2`, `require_book_risk=true`, **`limit=200`**, `offset=0`.
- **Response:** Array of event objects with `event_name`, `market_id`, `event_open_date`, `total_volume`, `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`, plus odds/lay and metadata.
- **Cap:** The API accepts `limit` (1–1000); the client sends **limit=200**, so the list contains up to 200 items. No API change was required.

---

## Acceptance criteria

1. **Opening the main page** triggers one request to `/events/book-risk-focus` and shows a populated table (or "Loading…" then table).
2. **List** shows up to 200 current/upcoming events (event_open_date >= now, within now+48h).
3. **Sorting** by H / A / D (and Volume) works; Asc/Desc and Signed vs Absolute behave as before.
4. **Tie-breaker order** is stable: volume desc, event_open_date asc, market_id asc.
5. **No** league accordion or conflicting filters/toggles on the landing page.

---

## Files changed

- **`risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`** — Replaced with single-fetch + `SortedEventsList`. No other components or routes changed; `App.tsx` still uses `LeaguesAccordion`.
- **`risk-analytics-ui/web/src/components/SortedEventsList.tsx`** — Unchanged. Used without `onOnlyActiveChange` / `onOnlyMarketsWithBookRiskChange`, so the "Only active in-play" and "Only markets with Book Risk" toggles do not appear on this page.
- **API** — No changes; existing `limit` query param is used with 200.

Screenshot: take a capture of the new main page after deploy (title "Top 200 current events", single table, sort controls only).
