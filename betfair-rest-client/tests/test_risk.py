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

# Ensure risk module is importable when running from project root or betfair-rest-client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from risk import calculate_risk


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
