"""
Unit tests for Market Imbalance Index (risk.py).

Run from betfair-rest-client directory:
  pip install -r requirements-dev.txt
  pytest tests/ -v

Or from repo root:
  pytest betfair-rest-client/tests/ -v
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure risk module is importable when running from project root or betfair-rest-client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from risk import calculate_risk, compute_impedance_index, compute_book_risk_l3


def _runner(selection_id: int, total_matched: float, available_to_back: list) -> dict:
    """Build a runner dict as from listMarketBook (lightweight)."""
    return {
        "selectionId": selection_id,
        "totalMatched": total_matched,
        "ex": {"availableToBack": available_to_back},
    }


# Case 1: Normal market with 3 runners – verify L - P (imbalance only, no totalMatched)
def test_normal_market_three_runners():
    # L_home = 100*1 + 50*1.2 = 160; L_away = 80*2 = 160; L_draw = 40*3 = 120
    # P_home = L_away + L_draw = 280 -> home_risk = 160 - 280 = -120
    # P_away = L_home + L_draw = 280 -> away_risk = 160 - 280 = -120
    # P_draw = L_home + L_away = 320 -> draw_risk = 120 - 320 = -200
    runners = [
        _runner(1001, 2000.0, [[2.0, 100.0], [2.2, 50.0]]),   # HOME
        _runner(1002, 1000.0, [[3.0, 80.0]]),                  # AWAY
        _runner(1003, 500.0, [[4.0, 40.0]]),                   # DRAW
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, by_name = result
    assert abs(home_risk - (-120.0)) < 0.01
    assert abs(away_risk - (-120.0)) < 0.01
    assert abs(draw_risk - (-200.0)) < 0.01
    assert total_volume == 3500.0
    assert by_name["home"] == home_risk and by_name["away"] == away_risk and by_name["draw"] == draw_risk


# Case 2: Swapped runner order – metadata mapping correctly identifies roles
def test_swapped_runner_order():
    runners = [
        _runner(1002, 1000.0, [[3.0, 80.0]]),                  # AWAY
        _runner(1003, 500.0, [[4.0, 40.0]]),                   # DRAW
        _runner(1001, 2000.0, [[2.0, 100.0], [2.2, 50.0]]),   # HOME
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, _ = result
    assert abs(home_risk - (-120.0)) < 0.01
    assert abs(away_risk - (-120.0)) < 0.01
    assert abs(draw_risk - (-200.0)) < 0.01
    assert total_volume == 3500.0


# Case 3: Empty or missing availableToBack levels – handle gracefully
def test_empty_or_missing_available_to_back():
    runners = [
        _runner(1001, 100.0, []),   # HOME – no back levels -> L=0
        _runner(1002, 200.0, [[2.5, 50.0]]),  # L_away = 75
        {"selectionId": 1003, "totalMatched": 300.0, "ex": {}},  # DRAW – L=0
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, _ = result
    # Home L=0, P = 75+0 = 75 -> -75
    assert abs(home_risk - (-75.0)) < 0.01
    # Away L=75, P = 0+0 = 0 -> 75
    assert abs(away_risk - 75.0) < 0.01
    # Draw L=0, P = 0+75 = 75 -> -75
    assert abs(draw_risk - (-75.0)) < 0.01
    assert total_volume == 600.0


# Case 4: Missing one selection (only 2 runners) – return None and log warning
def test_missing_one_selection_two_runners():
    runners = [
        _runner(1001, 100.0, [[2.0, 50.0]]),
        _runner(1002, 200.0, [[3.0, 30.0]]),
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}  # DRAW not in runners
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is None


# Case 5: Verify depth_limit – levels 4+ are ignored
def test_depth_limit_levels_four_plus_ignored():
    # L_home(depth 3) = 10+22+36 = 68; L_away = 10, L_draw = 15; P_home = 25 -> home_3 = 43
    runners = [
        _runner(1001, 0.0, [[2.0, 10], [2.1, 20], [2.2, 30], [2.3, 40], [2.5, 100]]),
        _runner(1002, 0.0, [[3.0, 5]]),
        _runner(1003, 0.0, [[4.0, 5]]),
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result_3 = calculate_risk(runners, metadata, depth_limit=3)
    result_5 = calculate_risk(runners, metadata, depth_limit=5)
    assert result_3 is not None and result_5 is not None
    home_3, _, _, _, _ = result_3
    home_5, _, _, _, _ = result_5
    assert abs(home_3 - 43.0) < 0.01   # 68 - 25
    assert abs(home_5 - 245.0) < 0.01  # L_home(depth 5) = 270, P = 25 -> 245
    assert home_5 > home_3


# Case 6: Golden sample – raw JSON structure matching Betfair listMarketBook response
def test_golden_sample_real_world_json():
    """
    Imbalance only (L - P). L_home=191, L_away=80, L_draw=60.
    P_home=140 -> home_risk=51; P_away=251 -> away_risk=-171; P_draw=271 -> draw_risk=-211.
    """
    golden_runners = [
        {
            "selectionId": 47931,
            "totalMatched": 1000.0,
            "ex": {
                "availableToBack": [[2.0, 100.0], [2.1, 50.0], [2.2, 30.0]],
                "availableToLay": [[2.02, 80.0], [2.04, 60.0]],
            },
        },
        {
            "selectionId": 47932,
            "totalMatched": 500.0,
            "ex": {
                "availableToBack": [[3.0, 40.0]],
                "availableToLay": [[3.1, 30.0]],
            },
        },
        {
            "selectionId": 47933,
            "totalMatched": 300.0,
            "ex": {
                "availableToBack": [[4.0, 20.0]],
                "availableToLay": [[4.2, 15.0]],
            },
        },
    ]
    metadata = {47931: "HOME", 47932: "AWAY", 47933: "DRAW"}
    result = calculate_risk(golden_runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, by_name = result
    assert abs(home_risk - 51.0) < 0.01, f"home_risk expected 51 got {home_risk}"
    assert abs(away_risk - (-171.0)) < 0.01, f"away_risk expected -171 got {away_risk}"
    assert abs(draw_risk - (-211.0)) < 0.01, f"draw_risk expected -211 got {draw_risk}"
    assert abs(total_volume - 1800.0) < 0.01, f"total_volume expected 1800 got {total_volume}"
    result2 = calculate_risk(golden_runners, metadata, depth_limit=3, market_total_matched=9500.5)
    assert result2 is not None
    _, _, _, vol2, _ = result2
    assert abs(vol2 - 9500.5) < 0.01


# --- Impedance Index tests ---


def _runner_ex(sid: int, available_to_back: list, available_to_lay: list) -> dict:
    """Runner with ex.availableToBack and ex.availableToLay (Betfair listMarketBook shape)."""
    return {
        "selectionId": sid,
        "ex": {"availableToBack": available_to_back, "availableToLay": available_to_lay},
    }


def test_impedance_no_liquidity_all_zero():
    """No liquidity at all -> all impedance and normImpedance 0 (must not crash)."""
    runners = [
        _runner_ex(1, [], []),
        _runner_ex(2, [], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts="2025-01-01T00:00:00Z")
    assert out["snapshot_ts"] == "2025-01-01T00:00:00Z"
    assert len(out["runners"]) == 2
    for ro in out["runners"]:
        assert ro["impedance"] == 0.0
        assert ro["normImpedance"] == 0.0
        assert ro["backStake"] == 0.0
        assert ro["layStake"] == 0.0


def test_impedance_fewer_than_four_levels_uses_available():
    """Fewer than 4 levels -> use available ones; must not crash."""
    runners = [
        _runner_ex(1, [[2.0, 100.0]], []),   # 1 back level
        _runner_ex(2, [[3.0, 50.0], [3.1, 20.0]], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    assert len(out["runners"]) == 2
    r1 = next(r for r in out["runners"] if r["selectionId"] == 1)
    r2 = next(r for r in out["runners"] if r["selectionId"] == 2)
    assert r1["backStake"] == 100.0
    assert r1["backOdds"] == 2.0
    assert r2["backStake"] == 70.0
    assert abs(r2["backOdds"] - (3.0 * 50 + 3.1 * 20) / 70) < 0.01


def test_impedance_invalid_levels_ignored():
    """Odds <= 1.0 or size <= 0 -> ignore (must not crash)."""
    runners = [
        _runner_ex(1, [[1.0, 100.0], [2.0, 0.0], [2.5, 50.0]], []),  # first two ignored
        _runner_ex(2, [], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    r1 = next(r for r in out["runners"] if r["selectionId"] == 1)
    assert r1["backStake"] == 50.0
    assert r1["backOdds"] == 2.5


def test_impedance_synthetic_two_runner_hand_calc():
    """
    Hand-calc: Runner 1 back 100@2, Runner 2 back 50@3 (no lay).
    If 1 wins: bookPnL = (0 - 100) + (50 - 0) = -50 -> Impedance(1) = 50.
    If 2 wins: bookPnL = (0 - 100) + (100 - 0) = 0 -> Impedance(2) = 0.
    """
    runners = [
        _runner_ex(1, [[2.0, 100.0]], []),
        _runner_ex(2, [[3.0, 50.0]], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    assert len(out["runners"]) == 2
    imp_by_sid = {r["selectionId"]: r["impedance"] for r in out["runners"]}
    assert abs(imp_by_sid[1] - 50.0) < 0.01, f"expected Impedance(1)=50 got {imp_by_sid[1]}"
    assert abs(imp_by_sid[2] - 0.0) < 0.01, f"expected Impedance(2)=0 got {imp_by_sid[2]}"
    scale = 100.0 + 50.0
    r1 = next(r for r in out["runners"] if r["selectionId"] == 1)
    assert abs(r1["normImpedance"] - 50.0 / scale) < 0.001


def test_impedance_worst_case_runner_largest_positive():
    """Worst-case runner (highest book loss if it wins) must have the largest positive Impedance."""
    # Runner 1: large back stake -> if 1 wins book pays a lot (liability_back_1 large).
    # Runner 2 and 3: small back stakes -> if 1 wins book wins little from others.
    # So runner 1 should have the largest positive impedance.
    runners = [
        _runner_ex(1, [[2.0, 500.0]], []),   # liability_back = 500
        _runner_ex(2, [[3.0, 10.0]], []),
        _runner_ex(3, [[4.0, 10.0]], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    impedances = [(r["selectionId"], r["impedance"]) for r in out["runners"]]
    worst_sid = max(impedances, key=lambda x: x[1])[0]
    assert worst_sid == 1, f"expected worst-case runner 1, got {impedances}"
    assert all(r["impedance"] >= 0 or abs(r["impedance"]) < 0.01 for r in out["runners"] if r["selectionId"] == 1)


def test_impedance_output_contract():
    """Output has snapshot_ts and per-runner selectionId, impedance, normImpedance, backStake, backOdds, layStake, layOdds."""
    runners = [
        _runner_ex(10, [[2.0, 100.0]], [[2.02, 50.0]]),
        _runner_ex(20, [[3.0, 30.0]], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts="2025-06-15T12:00:00")
    assert "snapshot_ts" in out
    assert out["snapshot_ts"] == "2025-06-15T12:00:00"
    assert "runners" in out
    for ro in out["runners"]:
        for key in ("selectionId", "impedance", "normImpedance", "backStake", "backOdds", "layStake", "layOdds"):
            assert key in ro, f"missing key {key}"
        assert isinstance(ro["impedance"], (int, float))
        assert isinstance(ro["normImpedance"], (int, float))
        assert isinstance(ro["backStake"], (int, float))
        assert isinstance(ro["layStake"], (int, float))


def test_impedance_timestamp_always_iso8601_string():
    """snapshot_ts accepts datetime | str | None; output snapshot_ts is always an ISO-8601 string (or "")."""
    runners = [_runner_ex(1, [[2.0, 10.0]], [])]
    out_none = compute_impedance_index(runners, snapshot_ts=None)
    assert out_none["snapshot_ts"] == ""
    out_str = compute_impedance_index(runners, snapshot_ts="2025-02-10T14:30:00Z")
    assert out_str["snapshot_ts"] == "2025-02-10T14:30:00Z"
    dt = datetime(2025, 2, 10, 14, 30, 0, tzinfo=timezone.utc)
    out_dt = compute_impedance_index(runners, snapshot_ts=dt)
    assert out_dt["snapshot_ts"].startswith("2025-02-10") and "14:30" in out_dt["snapshot_ts"]


def test_impedance_output_sorted_by_selection_id():
    """Output runners are in stable order by selectionId (deterministic across snapshots/logs/tests)."""
    runners = [
        _runner_ex(300, [[2.0, 10.0]], []),
        _runner_ex(100, [[3.0, 10.0]], []),
        _runner_ex(200, [[4.0, 10.0]], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    sids = [r["selectionId"] for r in out["runners"]]
    assert sids == [100, 200, 300], f"expected [100,200,300] got {sids}"


def test_impedance_back_and_lay_both_sides_synthetic():
    """
    Synthetic test with both BACK and LAY on two runners (full formula).
    Runner 1: back 100@2, lay 50@2.02 -> liability_back=100, win_back=100, win_lay=51, payout_lay=50.
    Runner 2: back 60@3, lay 40@3.1 -> liability_back=120, win_back=60, win_lay=84, payout_lay=40.
    If 1 wins: bookPnL = (51-100) + (60-40) = -29 -> Impedance(1) = 29.
    If 2 wins: bookPnL = (84-120) + (100-50) = 14 -> Impedance(2) = -14.
    """
    runners = [
        _runner_ex(1, [[2.0, 100.0]], [[2.02, 50.0]]),
        _runner_ex(2, [[3.0, 60.0]], [[3.1, 40.0]]),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    assert len(out["runners"]) == 2
    imp_by_sid = {r["selectionId"]: r["impedance"] for r in out["runners"]}
    assert abs(imp_by_sid[1] - 29.0) < 0.01, f"expected Impedance(1)=29 got {imp_by_sid[1]}"
    assert abs(imp_by_sid[2] - (-14.0)) < 0.01, f"expected Impedance(2)=-14 got {imp_by_sid[2]}"
    r1 = next(r for r in out["runners"] if r["selectionId"] == 1)
    r2 = next(r for r in out["runners"] if r["selectionId"] == 2)
    assert r1["backStake"] == 100.0 and r1["layStake"] == 50.0
    assert r2["backStake"] == 60.0 and r2["layStake"] == 40.0
    scale = 100.0 + 50.0 + 60.0 + 40.0
    assert abs(r1["normImpedance"] - 29.0 / scale) < 0.001
    assert abs(r2["normImpedance"] - (-14.0) / scale) < 0.001


def test_impedance_no_nan_or_inf():
    """Output numerics must be finite (no NaN/Inf); rounding applied at boundary."""
    runners = [
        _runner_ex(1, [[2.0, 100.0]], []),
        _runner_ex(2, [[3.0, 50.0]], []),
    ]
    out = compute_impedance_index(runners, snapshot_ts=None)
    for ro in out["runners"]:
        for key in ("impedance", "normImpedance", "backStake", "backOdds", "layStake", "layOdds"):
            v = ro[key]
            assert isinstance(v, (int, float)), f"{key} not numeric"
            assert v == v, f"{key} is NaN"
            assert abs(v) != float("inf"), f"{key} is Inf"


# --- 3-way Book Risk L3 (Ajax–Olympiacos acceptance test) ---


def test_book_risk_l3_ajax_olympiacos_example():
    """
    Acceptance test: Ajax–Olympiacos example from spec.
    HOME (Ajax): (321, 2.96), (103, 2.98), (583, 3.00)
    AWAY (Olympiacos): (813, 2.32), (1105, 2.34), (153, 2.36)
    DRAW: (138, 3.85), (82, 3.90), (21, 3.95)
    Expected: R[HOME]=-312.90, R[AWAY]=+1513.94, R[DRAW]=-2384.95
    """
    runners = [
        _runner(1001, 0.0, [[2.96, 321.0], [2.98, 103.0], [3.00, 583.0]]),   # HOME
        _runner(1002, 0.0, [[2.32, 813.0], [2.34, 1105.0], [2.36, 153.0]]),   # AWAY
        _runner(1003, 0.0, [[3.85, 138.0], [3.90, 82.0], [3.95, 21.0]]),      # DRAW
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    out = compute_book_risk_l3(runners, metadata, depth_limit=3)
    assert out is not None
    assert abs(out["home_book_risk_l3"] - (-312.90)) < 0.02, f"R[HOME] expected -312.90 got {out['home_book_risk_l3']}"
    assert abs(out["away_book_risk_l3"] - 1513.94) < 0.02, f"R[AWAY] expected 1513.94 got {out['away_book_risk_l3']}"
    assert abs(out["draw_book_risk_l3"] - (-2384.95)) < 0.02, f"R[DRAW] expected -2384.95 got {out['draw_book_risk_l3']}"


def test_book_risk_l3_fewer_than_three_levels_uses_available():
    """If fewer than 3 levels exist, compute with available levels."""
    runners = [
        _runner(1, 0.0, [[2.0, 100.0]]),           # HOME: 1 level
        _runner(2, 0.0, [[3.0, 50.0], [3.1, 50.0]]),  # AWAY: 2 levels
        _runner(3, 0.0, []),                       # DRAW: 0 levels
    ]
    metadata = {1: "HOME", 2: "AWAY", 3: "DRAW"}
    out = compute_book_risk_l3(runners, metadata, depth_limit=3)
    assert out is not None
    # W[HOME]=100*1=100, L[HOME]=50+50+0=100 -> R[HOME]=0
    assert abs(out["home_book_risk_l3"] - 0.0) < 0.01
    # W[AWAY]=50*2+50*2.1=205, L[AWAY]=100+0=100 -> R[AWAY]=105
    assert abs(out["away_book_risk_l3"] - 105.0) < 0.02
    # W[DRAW]=0, L[DRAW]=100+100=200 -> R[DRAW]=-200
    assert abs(out["draw_book_risk_l3"] - (-200.0)) < 0.01


def test_book_risk_l3_missing_role_returns_none():
    """If HOME/AWAY/DRAW mapping is incomplete, returns None."""
    runners = [
        _runner(1, 0.0, [[2.0, 100.0]]),
        _runner(2, 0.0, [[3.0, 50.0]]),
    ]
    metadata = {1: "HOME", 2: "AWAY"}  # no DRAW
    out = compute_book_risk_l3(runners, metadata, depth_limit=3)
    assert out is None
