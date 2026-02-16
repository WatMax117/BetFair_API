# Diagnosis: Missing L1/L2/L3 Data and Irregular Snapshot Intervals

**Date:** 2026-02-15  
**Scope:** Part 1 (missing L1/L2/L3 in UI), Part 2 (snapshot frequency), Part 3 (intended behaviour).  
**Status:** Diagnosis only; no behaviour changes.

---

## Part 1 – Missing L1/L2/L3 Data

### 1. What the REST client receives from Betfair

- **Source:** `getMarketBook` (and equivalent) with a price projection that includes ladder depth (e.g. `EX_ALL_OFFERS` or equivalent so that `ex.availableToBack` / `ex.availableToLay` are present).
- **Structure:** Per runner, `ex.availableToBack` is a list of levels. Each level is `[price, size]` or `{price, size}`. Index 0 = L1, 1 = L2, 2 = L3.
- **Betfair behaviour:** The API can return **only as many levels as exist in the order book**. In thin or illiquid markets (or at certain times) there may be only one or two back levels; L2/L3 are then **absent** in the response. Suspension or very low liquidity can also result in empty or single-level ladders.

So: **L2/L3 can legitimately be missing in the raw API response** when the book has fewer than three back levels.

### 2. How we extract L1/L2/L3

**Location:** `betfair-rest-client/main.py`

- **`_back_level_at(runner, level)`**  
  - Reads `ex.availableToBack` and uses index `level` (0=L1, 1=L2, 2=L3).  
  - If `level >= len(atb)` → returns `(0.0, 0.0)`.  
  - So we **explicitly** handle missing depth: no L2/L3 in payload → `(0.0, 0.0)`.

- **`_runner_best_prices()`**  
  - L2: `odds_l2, size_l2 = _back_level_at(r, 1)` then `out["..._back_odds_l2"] = odds_l2 if odds_l2 > 0 else None` (and same for size).  
  - L3: same with `_back_level_at(r, 2)`.  
  - So when Betfair sends only L1, we get `(0.0, 0.0)` for L2/L3 and we **store `None`** (we do not store 0).

- **L1 (best back/lay and sizes)**  
  - From `atb[0]`; we require `price > 1` and `size > 0`, otherwise we treat as invalid and use 0 / None where applicable.  
  - So we **do** check length and validity; we write NULL when depth is missing or invalid.

**Conclusion:** Extraction is consistent with “missing depth → NULL”. We are not overwriting with NULL due to a logic bug; we only set NULL when the ladder does not have that level or it is invalid.

### 3. DB storage

- **Schema:** `market_derived_metrics` has columns for L1 sizes (`*_best_back_size_l1`, `*_best_lay_size_l1`), L2 (`*_back_odds_l2`, `*_back_size_l2`), L3 (`*_back_odds_l3`, `*_back_size_l3`). All nullable.
- **Insert:** `_insert_derived_metrics()` passes through `metrics.get("...")`, so `None` is written as SQL NULL. No default or overwrite that would incorrectly clear values.
- **total_volume:** Comes from `totalMatched` (or sum of runner `totalMatched`), which is **independent** of ladder depth. So it is normal to have `total_volume` present while L2/L3 are NULL when the book has only one (or two) back levels.

**Suggested check on production (replace `<market_id>`):**

```sql
SELECT snapshot_at,
       home_back_odds_l2, home_back_odds_l3,
       home_back_size_l2, home_back_size_l3,
       total_volume
FROM market_derived_metrics
WHERE market_id = '<market_id>'
ORDER BY snapshot_at DESC
LIMIT 20;
```

- If L2/L3 columns are NULL in the DB for those rows, the cause is upstream (Betfair or our extraction), not the schema or a later overwrite.
- If L2/L3 are non-NULL in the DB but the UI shows "—", then the issue would be API or UI; from the code path above, the expected case is NULL in DB when depth is missing.

### 4. UI rendering

- **Source:** “Last 10 snapshots” uses `/debug/markets/{market_id}/snapshots`; each row includes `home_back_odds_l2`, `home_back_size_l2`, etc.
- **Display:** Values are passed to `HadCell`; nulls are rendered as "—" (e.g. via `num(v)` returning "—" when `v == null`). So **UI correctly shows "—" when the value is null**.

### Part 1 deliverable – Root cause of missing L1/L2/L3

| Option | Verdict |
|--------|--------|
| **A) Betfair not providing depth** | **Yes, primary cause.** Thin or illiquid books (or suspension) can return only L1 (or L1 and L2). We then correctly derive NULL for missing levels. |
| **B) Extraction logic** | **Correct.** We check `len(atb)` and level index; we return (0,0) when level is missing and store None for L2/L3 when value ≤ 0. No bug found. |
| **C) DB schema** | **Correct.** Columns exist and accept NULL; we do not overwrite with NULL elsewhere. |
| **D) UI rendering** | **Correct.** Nulls are shown as "—"; no misinterpretation of zero/empty. |

**Summary:** Missing L2/L3 (and sometimes L1) in the UI are due to **Betfair sometimes returning fewer than three back levels**. Our pipeline (extract → DB → API → UI) correctly represents that as NULL / "—". Optional next step: add temporary debug logging of `len(availableToBack)` (and optionally `availableToLay`) per runner when writing a snapshot to confirm in production.

---

## Part 2 – Snapshot Frequency (Why Not Fixed 15 Minutes?)

### 1. REST client interval configuration

- **Code:** `INTERVAL_SECONDS = int(os.environ.get("BF_INTERVAL_SECONDS", "900"))` (`main.py`).
- **Default:** 900 seconds = 15 minutes.
- **Compose:** `docker-compose.yml` passes `BF_INTERVAL_SECONDS=${BF_INTERVAL_SECONDS:-900}` into the REST client container.
- **Runtime value:** Must be confirmed on the VPS. If `BF_INTERVAL_SECONDS` is set to 60 or 120 in `.env` (or elsewhere), ticks will run every 1 or 2 minutes and snapshots will follow that cadence.

**Check on server:**

```bash
docker exec netbet-betfair-rest-client env | grep BF_INTERVAL
# and
docker logs --tail=500 netbet-betfair-rest-client | grep -E "interval=|tick_id"
```

Startup log line includes `interval=%ds` (e.g. `interval=900`). If you see `interval=60` or `interval=120`, that explains short gaps.

### 2. When we write a snapshot

- **Sticky pre-match path:** One **tick** runs every `INTERVAL_SECONDS`. Within a tick we:
  - Poll tracked markets in batches (e.g. 50 per batch),
  - Collect all returned books into `all_books`,
  - Then **persist one snapshot per market** using a **single** `snapshot_at = now_utc` (set once at the start of the persist loop).
- So for a **given market** we write **at most one snapshot per tick**. We do **not** write on every batch; we write once per market per tick after all batches for that tick are done.
- **Conclusion:** Snapshots are written **once per tick per market**, not on every poll. The only way to get multiple snapshots per market within a few minutes is to have **multiple ticks** in that window, i.e. **`BF_INTERVAL_SECONDS` &lt; 900** on the server (or another writer; see below).

### 3. Fixed 15-min vs “every poll tick”

- We do **not** “store every poll tick” in the sense of writing one row per API call. We write one row per market per **tick**, and each tick is intended to be every `INTERVAL_SECONDS`.
- We did **not** switch to “store every poll” for Sticky; the design is still “one snapshot per market per tick.” Sticky only changed which markets are tracked and how they are refreshed.
- So **by design**, snapshot times should align with the tick interval (e.g. 15 min if `BF_INTERVAL_SECONDS=900`). Irregular 1–3 minute gaps imply either a **shorter interval** (e.g. 60–180 s) or **another process** writing to the same tables.

### 4. Scheduler / daemon loop

- **Loop:** `while not _shutdown_requested: _sleep_event.wait(timeout=INTERVAL_SECONDS); tick_fn(...)`.
- So we **do** sleep for `INTERVAL_SECONDS` between ticks. There is no “run continuously and snapshot per batch” in the main loop; we wait, then run one full tick (catalogue + poll tracked + persist), then wait again.
- **Conclusion:** Effective polling interval is `INTERVAL_SECONDS`. If production shows snapshots every 1–3 minutes, the effective interval there is 1–3 minutes, which means either **`BF_INTERVAL_SECONDS` is set to 60–180 on the VPS** or another writer is inserting rows (e.g. another instance or a script). The streaming client in this repo does **not** write to `market_derived_metrics` or `market_book_snapshots`.

### Part 2 deliverable – Snapshot interval

| Question | Answer |
|----------|--------|
| **Exact effective polling interval?** | Determined by `BF_INTERVAL_SECONDS` at runtime. Default in code is 900 s. Confirm with `docker exec ... env` and startup log `interval=...`. |
| **Why are snapshots every ~1–3 minutes?** | Most likely: **`BF_INTERVAL_SECONDS` is 60–180** on the server. Alternatively, another process is writing snapshots for the same market. |
| **Is this expected?** | Only if you intentionally set a shorter interval (e.g. for testing). For “15-min history” the intended value is 900. |
| **Should we enforce fixed 15-min?** | If the goal is 15-min resolution, set and keep **`BF_INTERVAL_SECONDS=900`** (and ensure no other writer uses a shorter interval). No code change required for “one snapshot per tick”; the only variable is the tick interval. |

---

## Part 3 – Intended Behaviour (Clarification)

**Current model:**

- **A) Raw ingestion every X seconds, UI at 15-min buckets?**  
  - We do **not** “ingest every X seconds” in the sense of writing a row every few seconds. We ingest **once per tick** (every `INTERVAL_SECONDS`). So it’s “one snapshot per market per X seconds,” where X = 900 by default. The UI then aggregates into 15-min buckets for the timeseries chart (e.g. latest point per 15-min bucket). So we already have “ingestion at 15-min cadence” when X=900; no extra aggregation step in the DB.

- **B) Snapshot every poll tick (real-time history)?**  
  - We do **not** snapshot on every poll. We snapshot **once per tick** after all batches for that tick. So it’s “one snapshot per market per tick,” not “per HTTP poll.”

- **C) Hybrid?**  
  - Current design is: **fixed interval ticks** (e.g. 15 min), **one snapshot per market per tick**, **same `snapshot_at` for all markets in that tick**. So it’s a single model: time-based tick → one write per market per tick.

**If we want 15-min historical resolution only:**

- Store snapshots at a **fixed 15-minute grid** (e.g. truncate `snapshot_at` to 15-min boundaries) only if we need to **normalise** timestamps from multiple sources or from a shorter interval. With a single writer and **`BF_INTERVAL_SECONDS=900`**, timestamps will already be ~15 min apart; no need to bucket in the DB unless we later introduce other writers or variable intervals.

---

## Required Output Summary

### 1. Explanation of missing L1/L2/L3

- **Cause:** Betfair often returns fewer than three back levels (thin book, illiquid, or suspended). We correctly map “no level” → (0,0) in code and then → NULL in DB and "—" in the UI. `total_volume` is from `totalMatched`, so it can be non-null even when L2/L3 are null.

### 2. Explanation of current snapshot interval

- **Cause:** Snapshots are written **once per market per daemon tick**. The tick interval is **`BF_INTERVAL_SECONDS`** (default 900). If production shows 1–3 minute gaps, **`BF_INTERVAL_SECONDS` is likely 60–180** on the VPS, or another writer is inserting. No bug found in “snapshot every batch” vs “snapshot once per tick”; we do the latter.

### 3. Is this correct by design?

- **L1/L2/L3:** Yes. Missing depth is expected; we represent it correctly as NULL.
- **Intervals:** Yes, **if** you intend a 15-min cadence and set **`BF_INTERVAL_SECONDS=900`**. If the goal was 15 min but you see 1–3 min, then the configuration (or another writer) is not aligned with that goal.

### 4. Recommendations

| Topic | Recommendation |
|-------|----------------|
| **Missing L1/L2/L3** | **Keep as-is.** Optionally add temporary logging of `len(availableToBack)` (and `availableToLay`) when persisting to confirm in production that Betfair is often returning &lt; 3 levels. |
| **Snapshot cadence** | **Enforce 15-min if desired:** set **`BF_INTERVAL_SECONDS=900`** on the VPS and remove any override (e.g. in `.env`). Confirm with `docker logs` and, for one market, `SELECT snapshot_at FROM market_derived_metrics WHERE market_id = '...' ORDER BY snapshot_at DESC LIMIT 20;`. |
| **High-frequency ingestion + 15-min UI** | Not needed if the only writer is this REST client and interval is 900. The UI already buckets the timeseries into 15-min for the chart. If you later add a high-frequency writer, then we could add a DB view or aggregation that buckets to 15 min for the UI. |

No behaviour changes have been made; this is diagnosis only.
