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


# Case 1: Normal market with 3 runners – verify correct L - S calculation
def test_normal_market_three_runners():
    # Home: atb [2.0, 100], [2.2, 50] -> L = 100*(2-1) + 50*(2.2-1) = 100 + 60 = 160
    # Away: atb [3.0, 80] -> L = 80*2 = 160; totalMatched 1000
    # Draw: atb [4.0, 40] -> L = 40*3 = 120; totalMatched 500
    # Stakes for Home = (totalMatched + atb volume) of Away + Draw = (1000+80) + (500+40) = 1620
    # Home risk = 160 - 1620 = -1460
    runners = [
        _runner(1001, 2000.0, [[2.0, 100.0], [2.2, 50.0]]),   # HOME
        _runner(1002, 1000.0, [[3.0, 80.0]]),                  # AWAY
        _runner(1003, 500.0, [[4.0, 40.0]]),                   # DRAW
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, by_name = result
    # L_home = 100*1 + 50*1.2 = 160; S_home = 1000+80 + 500+40 = 1620 -> -1460
    assert abs(home_risk - (-1460.0)) < 0.01
    # L_away = 160; S_away = 2000+150 + 500+40 = 2590 -> -2430
    assert abs(away_risk - (-2430.0)) < 0.01
    # L_draw = 120; S_draw = 2000+150 + 1000+80 = 3230 -> -3110
    assert abs(draw_risk - (-3110.0)) < 0.01
    assert total_volume == 3500.0
    assert by_name["home"] == home_risk and by_name["away"] == away_risk and by_name["draw"] == draw_risk


# Case 2: Swapped runner order – metadata mapping correctly identifies roles
def test_swapped_runner_order():
    # Same data as above but runners list order is Away, Draw, Home
    runners = [
        _runner(1002, 1000.0, [[3.0, 80.0]]),                  # AWAY (first in list)
        _runner(1003, 500.0, [[4.0, 40.0]]),                   # DRAW
        _runner(1001, 2000.0, [[2.0, 100.0], [2.2, 50.0]]),   # HOME (last)
    ]
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, _ = result
    # Same numeric result as test 1 (roles identified by selectionId)
    assert abs(home_risk - (-1460.0)) < 0.01
    assert abs(away_risk - (-2430.0)) < 0.01
    assert abs(draw_risk - (-3110.0)) < 0.01
    assert total_volume == 3500.0


# Case 3: Empty or missing availableToBack levels – handle gracefully
def test_empty_or_missing_available_to_back():
    runners = [
        _runner(1001, 100.0, []),   # HOME – no back levels
        _runner(1002, 200.0, [[2.5, 50.0]]),
        {"selectionId": 1003, "totalMatched": 300.0, "ex": {}},  # DRAW – no availableToBack key
    ]
    # Normalize: risk.py uses _get_atb which returns [] for missing
    metadata = {1001: "HOME", 1002: "AWAY", 1003: "DRAW"}
    result = calculate_risk(runners, metadata, depth_limit=3)
    assert result is not None
    home_risk, away_risk, draw_risk, total_volume, _ = result
    # Home L=0, S = (200+50)+(300+0)=550 -> home_risk = -550
    assert abs(home_risk - (-550.0)) < 0.01
    # Away L=50*1.5=75, S = (100+0)+(300+0)=400 -> -325
    assert abs(away_risk - (-325.0)) < 0.01
    # Draw L=0, S = (100+0)+(200+50)=350 -> -350
    assert abs(draw_risk - (-350.0)) < 0.01
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
    # HOME: 4 levels; with depth_limit=3 only first 3 count
    # L = 10*(2-1) + 20*(2.1-1) + 30*(2.2-1) = 10 + 22 + 36 = 68 (4th level 40*(2.3-1)=52 ignored)
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
    # With depth 3: L_home = 68, S_home = 5+5 = 10 -> 58
    assert abs(home_3 - 58.0) < 0.01
    # With depth 5: L_home includes 40*1.3 + 100*1.5 = 52 + 150 = 202 more -> L = 68+202 = 270, S still 10 -> 260
    assert abs(home_5 - 260.0) < 0.01
    assert home_5 > home_3


# Case 6: Golden sample – raw JSON structure matching Betfair listMarketBook response
def test_golden_sample_real_world_json():
    """
    Raw JSON mimicking Betfair listMarketBook (nested ex, availableToBack, availableToLay).
    Manual calculation (depth_limit=3):
      HOME: L = 100*1.0 + 50*1.1 + 30*1.2 = 191. S = (500+40) + (300+20) = 860. Risk = -669.
      AWAY: L = 40*2.0 = 80. S = (1000+180) + (300+20) = 1500. Risk = -1420.
      DRAW: L = 20*3.0 = 60. S = (1000+180) + (500+40) = 1720. Risk = -1660.
      total_volume (sum runner totalMatched) = 1800.
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
    assert abs(home_risk - (-669.0)) < 0.01, f"home_risk expected -669 got {home_risk}"
    assert abs(away_risk - (-1420.0)) < 0.01, f"away_risk expected -1420 got {away_risk}"
    assert abs(draw_risk - (-1660.0)) < 0.01, f"draw_risk expected -1660 got {draw_risk}"
    assert abs(total_volume - 1800.0) < 0.01, f"total_volume expected 1800 got {total_volume}"
    # With market_total_matched override, total_volume should be that value
    result2 = calculate_risk(golden_runners, metadata, depth_limit=3, market_total_matched=9500.5)
    assert result2 is not None
    _, _, _, vol2, _ = result2
    assert abs(vol2 - 9500.5) < 0.01
