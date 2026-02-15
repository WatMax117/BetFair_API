"""
Unit tests for Book Risk L3 (risk.py). Imbalance and Impedance indices removed (MVP).

Run from betfair-rest-client directory:
  pip install -r requirements-dev.txt
  pytest tests/ -v

Or from repo root:
  pytest betfair-rest-client/tests/ -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from risk import compute_book_risk_l3


def _runner(selection_id: int, total_matched: float, available_to_back: list) -> dict:
    """Build a runner dict as from listMarketBook (lightweight)."""
    return {
        "selectionId": selection_id,
        "totalMatched": total_matched,
        "ex": {"availableToBack": available_to_back},
    }


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
