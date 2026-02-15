"""
Sanity tests for ROI Toxic (Uncovered ROI Pressure) index.
Validates: ROI_N = back_liability_sum_N / back_size_sum_N (weighted avg odds - 1),
coverage_N = back_size_sum_N / TotalVolume, ROIToxic_N = ROI_N * (1 - coverage_N).
"""
import pytest

# Test the real implementation from the API (no DB used by _compute_roi_toxic)
from app.main import _compute_roi_toxic


def test_roi_n_equals_weighted_odds_minus_one():
    """ROI_N = back_liability_sum_N / back_size_sum_N = (weighted avg odds) - 1."""
    # odds 2.0 -> (2-1)=1 profit per unit -> ROI = 1.0
    out = {
        "home_back_size_sum_N": 100.0,
        "home_back_liability_sum_N": 100.0,  # 100 * (2-1)
        "away_back_size_sum_N": 50.0,
        "away_back_liability_sum_N": 75.0,   # 50 * (2.5-1) -> avg odds 2.5, ROI=1.5
        "draw_back_size_sum_N": 0.0,
        "draw_back_liability_sum_N": 0.0,
        "mdm_total_volume": 1000.0,
    }
    r = _compute_roi_toxic(out)
    assert r["home_roi_N"] == 1.0   # odds 2 -> ROI 1
    assert r["away_roi_N"] == 1.5   # 75/50 = 1.5 (odds 2.5 - 1)
    assert r["draw_roi_N"] is None   # size 0 -> null


def test_roi_n_odds_less_than_2():
    """odds < 2 -> ROI_N < 1."""
    out = {
        "home_back_size_sum_N": 100.0,
        "home_back_liability_sum_N": 50.0,   # e.g. odds 1.5 -> (1.5-1)*100=50
        "away_back_size_sum_N": 0.0,
        "away_back_liability_sum_N": 0.0,
        "draw_back_size_sum_N": 0.0,
        "draw_back_liability_sum_N": 0.0,
        "mdm_total_volume": 500.0,
    }
    r = _compute_roi_toxic(out)
    assert r["home_roi_N"] == 0.5
    assert r["home_roi_N"] < 1.0


def test_coverage_responds_to_total_volume():
    """Coverage_N = back_size_sum_N / TotalVolume."""
    out = {
        "home_back_size_sum_N": 100.0,
        "home_back_liability_sum_N": 100.0,
        "away_back_size_sum_N": 50.0,
        "away_back_liability_sum_N": 50.0,
        "draw_back_size_sum_N": 50.0,
        "draw_back_liability_sum_N": 50.0,
        "mdm_total_volume": 1000.0,
    }
    r = _compute_roi_toxic(out)
    assert r["home_coverage_N"] == 0.1   # 100/1000
    assert r["away_coverage_N"] == 0.05   # 50/1000
    assert r["draw_coverage_N"] == 0.05

    out["mdm_total_volume"] = 500.0
    r2 = _compute_roi_toxic(out)
    assert r2["home_coverage_N"] == 0.2   # 100/500
    assert r2["away_coverage_N"] == 0.1


def test_roi_toxic_increases_with_roi_and_decreases_with_coverage():
    """ROIToxic_N = ROI_N * (1 - Coverage_N). High ROI + low coverage -> high ROIToxic."""
    # High ROI, low coverage -> high roi_toxic
    out1 = {
        "home_back_size_sum_N": 10.0,
        "home_back_liability_sum_N": 20.0,   # ROI=2
        "away_back_size_sum_N": 0.0,
        "away_back_liability_sum_N": 0.0,
        "draw_back_size_sum_N": 0.0,
        "draw_back_liability_sum_N": 0.0,
        "mdm_total_volume": 1000.0,  # coverage = 10/1000 = 0.01
    }
    r1 = _compute_roi_toxic(out1)
    assert r1["home_roi_N"] == 2.0
    assert r1["home_coverage_N"] == 0.01
    assert r1["home_roi_toxic_N"] == pytest.approx(2.0 * (1 - 0.01), rel=1e-9)

    # Same ROI, high coverage -> lower roi_toxic
    out2 = {
        "home_back_size_sum_N": 500.0,
        "home_back_liability_sum_N": 1000.0,  # ROI=2
        "away_back_size_sum_N": 0.0,
        "away_back_liability_sum_N": 0.0,
        "draw_back_size_sum_N": 0.0,
        "draw_back_liability_sum_N": 0.0,
        "mdm_total_volume": 1000.0,  # coverage = 0.5
    }
    r2 = _compute_roi_toxic(out2)
    assert r2["home_roi_N"] == 2.0
    assert r2["home_coverage_N"] == 0.5
    assert r2["home_roi_toxic_N"] == pytest.approx(2.0 * 0.5, rel=1e-9)
    assert r2["home_roi_toxic_N"] < r1["home_roi_toxic_N"]


def test_fallback_volume_from_sum_of_sizes():
    """When mdm_total_volume and mbs_total_matched missing, use sum of back_size_sum_N."""
    out = {
        "home_back_size_sum_N": 100.0,
        "home_back_liability_sum_N": 100.0,
        "away_back_size_sum_N": 200.0,
        "away_back_liability_sum_N": 200.0,
        "draw_back_size_sum_N": 100.0,
        "draw_back_liability_sum_N": 100.0,
        "mdm_total_volume": None,
        "mbs_total_matched": None,
    }
    r = _compute_roi_toxic(out)
    total = 400.0
    assert r["home_coverage_N"] == pytest.approx(100 / total, rel=1e-9)
    assert r["away_coverage_N"] == pytest.approx(200 / total, rel=1e-9)
    assert r["draw_coverage_N"] == pytest.approx(100 / total, rel=1e-9)
