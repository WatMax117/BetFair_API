# Stream-Only Validation: Can We Drop REST for Soccer?

Validation of whether the Betfair Exchange Stream API can fully replace REST for Soccer (discovery + metadata + prices), and whether stream-only reduces system complexity.

---

## 1. Documentation Review

### 1.1 Stream API: Subscribe Without marketIds (marketFilter-based discovery)

**Source:** Betfair Exchange Stream API – MarketSubscriptionMessage / MarketFilter

- **ESASwaggerSchema** (https://github.com/betfair/stream-api-sample-code/blob/master/ESASwaggerSchema.json):

```json
"MarketFilter": {
  "properties": {
    "eventTypeIds": { "type": "array", "items": { "type": "string" } },
    "marketTypes":  { "type": "array", "items": { "type": "string" } },
    "marketIds":    { "type": "array", "items": { "type": "string" } },
    ...
  }
}
```

- **Conclusion:** You can subscribe using only `eventTypeIds` and `marketTypes` (or `marketIds` is optional). No explicit marketIds required. The stream will push markets matching the filter as they appear.

- **Support article:**  
  https://support.developer.betfair.com/hc/en-us/articles/360000402291  
  > "On subscribing to the Market Stream API you are sent an **initial image** of the market, including all the relevant market information, current prices etc"

- **Web search (Betfair developer docs):**  
  > "You can use **wildcards in your market filter** to subscribe to markets dynamically. This means you don't need to know specific market IDs in advance—the API will notify you as soon as matching markets appear."

### 1.2 Stream API: Market Metadata (marketDefinition)

**Source:** ESASwaggerSchema – MarketChange, MarketDefinition, RunnerDefinition

**MarketDefinition** (sent when `EX_MARKET_DEF` is in `fields`):

| Field | Type | Notes |
|-------|------|-------|
| `marketType` | string | e.g. MATCH_ODDS, OVER_UNDER_2_5 |
| `eventId` | string | Event linkage |
| `eventTypeId` | string | e.g. "1" for Soccer |
| `openDate` | date-time | Market open date |
| `marketTime` | date-time | Market start time |
| `runners` | array of RunnerDefinition | Selections |
| `status` | enum | INACTIVE, OPEN, SUSPENDED, CLOSED |
| `inPlay` | boolean | In-play flag |
| `timezone` | string | |
| `countryCode` | string | |

**RunnerDefinition** (per runner in `marketDefinition.runners`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | int64 | selectionId |
| `sortPriority` | int32 | Order (1=HOME, 2=AWAY, 3=DRAW for 3-way) |
| `hc` | double | Handicap (null if N/A) |
| `status` | enum | ACTIVE, WINNER, LOSER, REMOVED, etc. |
| `bsp` | double | BSP price (if applicable) |
| `removalDate` | date-time | |
| `adjustmentFactor` | double | |

**Critical:** The schema does **not** define `runnerName` or `name` in RunnerDefinition. REST `listMarketCatalogue` with `RUNNER_DESCRIPTION` returns runner names; the stream schema does not.

**Support article:**  
https://support.developer.betfair.com/hc/en-us/articles/6540502258077  

> "EX_MARKET_DEF – Send market definitions"  
> "To receive updates to any of the [MarketDefinitionFields](https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Exchange+Stream+API#ExchangeStreamAPI-MarketDefinitionFields)"

Runner names are not listed in the documented Market Definition fields. The stream provides selectionId + sortPriority for mapping, but not human-readable runner names (e.g. "Team A", "Team B", "Draw").

### 1.3 REST listMarketCatalogue: Purpose and Limits

**Source:** listMarketCatalogue – Betfair Exchange API Documentation

- **Max results:** maxResults &gt; 0 and ≤ 1000. TOO_MUCH_DATA can still occur below 1000 if request size/limits are exceeded.
- **Closed markets:** Does **not** return CLOSED markets. Only ACTIVE and SUSPENDED.
- **Use case:** Static metadata for published markets that change infrequently (event, competition, market type, runner names, etc.).

**Relevant links:**
- https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687517/listMarketCatalogue
- https://forum.developer.betfair.com/forum/sports-exchange-api/exchange-api/2343-how-to-use-listmarketcatalogue-to-get-more-than-1000-results

---

## 2. Minimal Live Test Plan (VM, 15–30 min)

### 2.1 Stream subscription for discovery

**How to run on VM:**

1. Temporarily set `betfair.subscribe-from-db: false` and leave `betfair.market-ids` empty so the stream client uses `eventTypeIds` + `marketTypes` (no marketIds).
2. Ensure `MARKET_DATA_FIELDS` includes `EX_MARKET_DEF` (already in SubscriptionManager).
3. Add temporary logging in `MarketChangeHandler` or `MarketCache.applyChange` to capture the first `marketDefinition` per marketId (especially `marketDefinition.runners`) to a file.
4. Run the stream client for 15–30 minutes; include at least one match that goes in-play if possible.
5. Or use the Betfair stream sample code (https://github.com/betfair/stream-api-sample-code) with the payload below and log raw `mcm` messages.

**Subscription payload (no marketIds):**

```json
{
  "op": "marketSubscription",
  "id": 2,
  "heartbeatMs": 5000,
  "conflateMs": 0,
  "marketFilter": {
    "eventTypeIds": ["1"],
    "marketTypes": ["MATCH_ODDS", "OVER_UNDER_2_5", "NEXT_GOAL"]
  },
  "marketDataFilter": {
    "ladderLevels": 8,
    "fields": ["EX_ALL_OFFERS", "EX_TRADED_VOL", "EX_TRADED", "EX_LTP", "EX_MARKET_DEF"]
  }
}
```

- Use `eventTypeIds` + `marketTypes` only; do **not** provide `marketIds`.
- Include `EX_MARKET_DEF` so market definitions are received.

### 2.2 What to log / measure

Over 15–30 minutes (ideally including at least one in-play match):

| Metric | How to measure |
|--------|----------------|
| Unique marketIds per marketType | Count distinct marketIds from `mc[].id` where `marketDefinition.marketType` = MATCH_ODDS, OVER_UNDER_2_5, NEXT_GOAL |
| marketDefinition contents | For each marketId: log presence of `marketType`, `marketName`, `eventId`, `openDate`, `runners` |
| Runners: selectionId + name | Check `marketDefinition.runners[].id` (selectionId). Check for `name` or `runnerName` (may be absent) |
| Event linkage | Log `eventId`, `openDate` from marketDefinition |
| NEXT_GOAL timing | If an event goes in-play: record kickoff time and first time NEXT_GOAL marketId appears in stream; compute delta |

### 2.3 Persisted outputs

**Output 1 – Metadata snapshot (JSON):**

```json
{
  "captured_at": "2026-02-18T14:00:00Z",
  "markets": [
    {
      "marketId": "1.234567890",
      "marketType": "MATCH_ODDS",
      "marketName": "...",
      "eventId": "32123456",
      "eventName": null,
      "openDate": "2026-02-18T15:00:00.000Z",
      "runners": [
        { "selectionId": 12345, "runnerName": "..." },
        ...
      ]
    }
  ]
}
```

If `runnerName` is missing from the stream, document that clearly.

**Output 2 – Streaming updates sample:**

- Per marketId: samples of `rc[]` with `batb`/`bdatb`, `batl`/`bdatl` (best back/lay and size).
- Per market: `tv` (total matched) if present in marketChange or RunnerChange.
- Timestamps: `pt` (publish time) and local receive time.

---

## 3. Decision: Do We Still Need REST?

### A) If the stream provides reliable discovery + sufficient metadata

**Assumption:** Stream supplies eventId, openDate, marketType, runners (selectionId + sortPriority), and ideally runner names.

**Recommendation:** **Stream-only (REST optional fallback)**.

**What we lose without REST:**
- Runner names (Team A / Team B / Draw) – schema suggests they are not in the stream.
- Optional catalogue fields: competition name, event name, country, etc.
- Any markets that are CLOSED at query time (REST never returns them).
- Ability to “discover before stream” for markets not yet in the filter window.

### B) If the stream does NOT provide enough metadata (e.g. runner names)

**Assumption:** RunnerDefinition has no `runnerName` (as in schema); event name / competition may be absent.

**Recommendation:** **Keep REST for metadata / discovery.**

- Use REST `listMarketCatalogue` for:
  - Event and market catalogue
  - Runner names (HOME/AWAY/DRAW or team names)
  - Competition, event name, etc.
- Use Stream for:
  - Odds and liquidity updates (best back/lay, size, traded volume)
  - Lifecycle (OPEN/SUSPENDED/CLOSED, inPlay)

---

## 4. Complexity Comparison

| Aspect | REST + Stream | Stream-only |
|--------|---------------|-------------|
| **Discovery** | REST listMarketCatalogue (hourly or on-demand) | Stream via eventTypeIds + marketTypes; markets pushed as they appear |
| **Metadata** | Full from REST (event, competition, runner names, etc.) | Limited from marketDefinition (eventId, openDate, marketType, runners with selectionId/sortPriority; likely no runner names) |
| **Odds/liquidity** | Stream only (REST optional for snapshots) | Stream only |
| **DB / join** | Join REST metadata with stream data (e.g. market_event_metadata + ladder_levels) | Single source; need to derive event linkage from marketDefinition |
| **Scheduling** | REST cron (e.g. hourly) + stream always-on | Stream always-on only |
| **Rate limits** | REST: listMarketCatalogue limits, TOO_MUCH_DATA | Stream: subscription limits, connection limits |
| **Reconnect / resubscribe** | Stream: resend same marketFilter (or stored marketIds) | Same; must handle initial image and delta |
| **New markets** | REST discovers on next run; stream subscribes by marketIds from DB | Stream discovers when market matches filter; no REST needed |
| **Runner names (HOME/AWAY/DRAW)** | From REST | **Uncertain** – not in RunnerDefinition schema; need live test |
| **NEXT_GOAL timing** | REST shows it when in catalogue | Stream shows it when it appears; good for post-kickoff discovery |

---

## 5. Recommendation

### Keep REST (at least for metadata/discovery)

**Reasons:**

1. **Runner names:** The official stream schema does not include runner names in RunnerDefinition. REST `listMarketCatalogue` with `RUNNER_DESCRIPTION` does. For risk/analytics we need HOME/AWAY/DRAW mapping; stream-only may require inferring from sortPriority only, or a separate REST call for names.
2. **Designed roles:** REST listMarketCatalogue is intended for “published markets that change rarely” (static metadata). The stream is intended for high-frequency price/liquidity updates. Using each for its purpose keeps the system simpler and more reliable.
3. **Event/competition context:** Event name, competition name, and related fields are standard in the catalogue and useful for UI and analytics. The stream’s marketDefinition provides eventId and dates but may not include full event/competition names.
4. **Validation:** Run the live test (Section 2) on the VM. If the stream **does** include runner names (e.g. in an undocumented field) and sufficient event context, stream-only becomes viable; until then, REST remains the safer choice for metadata.

### Optional: hybrid with stream-first discovery

- Use stream `eventTypeIds` + `marketTypes` for **discovery** (which marketIds exist).
- Use REST `listMarketCatalogue` only for **metadata enrichment** (runner names, event name, competition) for those marketIds.
- This keeps REST calls smaller and focused, while the stream drives which markets matter.

---

## 6. Deliverables Checklist

| Deliverable | Status |
|-------------|--------|
| Links/quotes to doc sections | ✅ Section 1 |
| VM test plan (15–30 min) | ✅ Section 2 |
| Logging and measurement spec | ✅ Section 2.2 |
| Persisted output format | ✅ Section 2.3 |
| Complexity comparison table | ✅ Section 4 |
| Recommendation with 2–3 concrete reasons | ✅ Section 5 |

**Next step:** Execute the VM test (Section 2), capture the outputs, and confirm whether `marketDefinition.runners` includes runner names in practice. If yes, stream-only is feasible; if no, keep REST for metadata.
