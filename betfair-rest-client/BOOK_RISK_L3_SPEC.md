# 3-way Book Risk L3 — Implementation Summary

## Formula (per outcome o ∈ {HOME, AWAY, DRAW})

- **W[o]** = Σ_i S[o,i] × (O[o,i] − 1) — winners' net payout if outcome o happens  
- **L[o]** = Σ_{p≠o} Σ_i S[p,i] — losers' stakes collected if outcome o happens  
- **R[o]** = W[o] − L[o]  

**Sign convention:** R[o] > 0 ⇒ book loses money if outcome o wins; R[o] < 0 ⇒ book wins.

## Data source

- **REST:** `market_book_snapshots.raw_payload` → `runners[].ex.availableToBack` (top 3 levels: price, size).
- Levels are ordered best price first; we use the first 3 levels per runner. If fewer than 3 levels exist, we use available levels.

## DB

- **Table:** `market_derived_metrics`
- **Columns added (nullable):** `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`
- **Migration:** Columns are added at runtime in `_ensure_three_layer_tables()` (same pattern as impedance columns).

## API

- **GET /debug/markets/{market_id}/snapshots** — each snapshot row includes `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`.
- **GET /events/{market_id}/timeseries** — each point includes `home_book_risk_l3`, `away_book_risk_l3`, `draw_book_risk_l3`.

### Example JSON (one snapshot from debug endpoint)

```json
{
  "snapshot_id": 4829,
  "snapshot_at": "2026-02-09T14:47:25.946006+00:00",
  "market_id": "1.253538481",
  "home_risk": -8371.7372,
  "away_risk": -4864.836800000001,
  "draw_risk": 2862.4712000000004,
  "home_book_risk_l3": -312.90,
  "away_book_risk_l3": 1513.94,
  "draw_book_risk_l3": -2384.95,
  "mbs_total_matched": 18643.73,
  "mdm_total_volume": 18643.73
}
```

*(Values above are illustrative; real `home_book_risk_l3` / `away_book_risk_l3` / `draw_book_risk_l3` come from the acceptance example.)*

## Acceptance test (Ajax–Olympiacos)

| Outcome | (S,O) levels | Expected R[o] |
|---------|----------------|----------------|
| HOME    | (321,2.96), (103,2.98), (583,3.00) | -312.90 |
| AWAY    | (813,2.32), (1105,2.34), (153,2.36) | +1513.94 |
| DRAW    | (138,3.85), (82,3.90), (21,3.95) | -2384.95 |

Run: `pytest betfair-rest-client/tests/test_risk.py -k "book_risk_l3" -v`

## Code reference

- **Calculation:** `betfair-rest-client/risk.py` → `compute_book_risk_l3(runners, runner_metadata, depth_limit=3)`
- **Persistence:** `betfair-rest-client/main.py` → `_ensure_three_layer_tables`, `_insert_derived_metrics`, metrics dict
- **API:** `risk-analytics-ui/api/app/main.py` → debug snapshots SELECT, timeseries SELECT + _serialize
