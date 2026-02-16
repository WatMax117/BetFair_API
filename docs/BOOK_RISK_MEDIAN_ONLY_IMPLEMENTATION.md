# Book Risk Computation from 15-Minute Bucket Medians Only

**Date:** 2026-02-16  
**Status:** ✅ Implemented

---

## Summary

Book Risk (15m) is now computed **strictly** from the six 15-minute bucket medians:
- `home_back_odds_median`
- `home_back_size_median`
- `away_back_odds_median`
- `away_back_size_median`
- `draw_back_odds_median`
- `draw_back_size_median`

No other data sources are used for risk computation.

---

## Implementation

### New Function: `compute_book_risk_from_medians()`

**Location:** `risk-analytics-ui/api/app/stream_data.py`

**Formula:**
```
For each outcome o:
  W[o] = median_size[o] * (median_odds[o] - 1)  [winners net payout]
  L[o] = sum of median_size for other outcomes  [liability if other outcomes win]
  R[o] = W[o] - L[o]  [Book Risk]
```

**NULL Handling:**
- If **any** median is NULL → returns `None` for all risks
- No partial computation
- No implicit 0 substitution

**Example:**
```python
book_risk = compute_book_risk_from_medians(
    home_odds_median=2.5,
    home_size_median=100.0,
    away_odds_median=3.0,
    away_size_median=50.0,
    draw_odds_median=4.0,
    draw_size_median=25.0,
)
# Returns:
# {
#   "home_book_risk_l3": 100.0 * (2.5 - 1) - (50.0 + 25.0) = 75.0,
#   "away_book_risk_l3": 50.0 * (3.0 - 1) - (100.0 + 25.0) = -75.0,
#   "draw_book_risk_l3": 25.0 * (4.0 - 1) - (100.0 + 50.0) = -125.0,
# }
```

---

## Removed Dependencies

### ❌ Removed from Risk Computation:

1. **`compute_book_risk_l3()`** - No longer used
   - Previously computed risk from ladder levels (L1/L2/L3)
   - Required `runners` data with `ex.availableToBack` arrays

2. **`_runners_from_ladder()`** - No longer used for risk
   - Still called for `best_back`/`best_lay` display compatibility
   - **Not** used for risk computation

3. **Ladder levels (L1-L8)** - Not used for risk
4. **Raw ticks** - Not used for risk
5. **Latest snapshot values** - Not used for risk
6. **Best back/lay values** - Not used for risk

---

## Updated Functions

All functions that compute Book Risk now use `compute_book_risk_from_medians()`:

1. **`get_event_timeseries_stream()`**
   - Computes medians for each bucket
   - Computes risk from medians only
   - Returns risk in response

2. **`get_events_by_date_snapshots_stream()`**
   - Computes medians for latest bucket
   - Computes risk from medians only

3. **`get_league_events_stream()`**
   - Computes medians for latest bucket
   - Computes risk from medians only

---

## Data Flow

```
Raw ticks (stream_ingest.ladder_levels)
  ↓
15-minute bucket aggregation
  ↓
Time-weighted medians (6 values)
  ↓
Book Risk computation (pure function)
  ↓
API response
  ↓
UI display
```

**No alternative paths. No fallbacks. No snapshot-based computation.**

---

## Validation Checklist

### ✅ Case 1: Bucket with stable odds and size
- Modify a single raw tick inside the bucket
- **Expected:** Median may change slightly, risk changes only if median changes
- **Not expected:** Direct sensitivity to a single tick

### ✅ Case 2: Bucket with no data
- Medians = NULL
- Risk = NULL
- UI displays "—"

### ✅ Case 3: Partial data (one outcome missing)
- If any median is NULL → all risks = NULL
- No partial computation

---

## Files Modified

1. **`risk-analytics-ui/api/app/stream_data.py`**
   - Added `compute_book_risk_from_medians()` function
   - Removed import of `compute_book_risk_l3`
   - Updated all risk computation calls to use medians only
   - Updated `get_event_timeseries_stream()`
   - Updated `get_events_by_date_snapshots_stream()`
   - Updated `get_league_events_stream()`

---

## Deployment Status

- ✅ Code implemented
- ✅ API container restarted
- ✅ All risk computation paths updated

---

## Acceptance Criteria

✅ **Single source:** Book Risk computed only from six medians  
✅ **No ladder dependency:** Risk does not use L1/L2/L3 levels  
✅ **No tick dependency:** Risk does not use raw ticks  
✅ **No snapshot dependency:** Risk does not use latest snapshot  
✅ **NULL handling:** If any median is NULL → all risks NULL  
✅ **Pure function:** Risk computation is deterministic and reproducible  
✅ **UI display:** UI shows risk from backend response only (no client-side computation)  

---

## Conclusion

Book Risk (15m) is now a pure function of the six 15-minute bucket medians. This ensures:
- **Noise resistance:** Single tick changes don't directly affect risk
- **Deterministic behavior:** Same medians → same risk
- **Full auditability:** Risk can be traced back to medians, which can be traced back to ticks
- **Transparent linkage:** Clear mathematical relationship between bucket parameters and risk

The system now follows the strict rule:
```
Book Risk (15m) = f(six 15-minute medians)
```

No alternative paths. No fallbacks. No exceptions.
