"""
Back-liquidity Imbalance Index for Match Odds markets (simplified V1).

Snapshot-based visible-liquidity pressure only. No cumulative totalMatched in the index.
Metadata-aware: uses runner_metadata mapping selectionId -> 'HOME' | 'AWAY' | 'DRAW'.
Depth-limited: only first `depth_limit` levels of availableToBack (default 3).

Formula (per runner):
  L (liability) = sum of size * (price - 1) for that runner's first depth_limit back levels.
  P (opposing pressure) = sum of size * (price - 1) for the OTHER two runners' first depth_limit back levels.
  Imbalance = L - P.

total_volume is returned for reporting only (market maturity); it is NOT used in the index.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("betfair_rest_client.risk")

# Normalize selectionId for dict lookup (API may return int or str)
def _sid(runner: Any) -> Optional[Union[int, str]]:
    if isinstance(runner, dict):
        return runner.get("selectionId") or runner.get("selection_id")
    return getattr(runner, "selectionId", None) or getattr(runner, "selection_id", None)


def _get_atb(runner: Any) -> List[Any]:
    """Get availableToBack list from runner.ex."""
    ex = runner.get("ex") if isinstance(runner, dict) else getattr(runner, "ex", None)
    if not ex:
        return []
    atb = ex.get("availableToBack") if isinstance(ex, dict) else getattr(ex, "available_to_back", None) or getattr(ex, "availableToBack", None)
    return atb if atb else []


def _safe_float(val: Any) -> float:
    """Sanitize None or non-numeric to 0.0."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _price_size(level: Any) -> Tuple[float, float]:
    if isinstance(level, (list, tuple)) and len(level) >= 2:
        return _safe_float(level[0]), _safe_float(level[1])
    if isinstance(level, dict):
        p = _safe_float(level.get("price") or level.get("Price"))
        s = _safe_float(level.get("size") or level.get("Size"))
        return p, s
    return 0.0, 0.0


def _liability(runner: Any, depth_limit: int) -> float:
    """L = sum of (size * (price - 1)) for first depth_limit levels of AvailableToBack."""
    total = 0.0
    atb = _get_atb(runner)
    for level in atb[:depth_limit]:
        price, size = _price_size(level)
        total += size * (price - 1.0)
    return total


def _total_matched(runner: Any) -> float:
    """Runner-level totalMatched; used only for total_volume reporting, not for the index."""
    if isinstance(runner, dict):
        return _safe_float(runner.get("totalMatched") or runner.get("total_matched"))
    return _safe_float(getattr(runner, "total_matched", None) or getattr(runner, "totalMatched", None))


def calculate_risk(
    runners: List[Any],
    runner_metadata: Dict[Union[int, str], str],
    depth_limit: int = 3,
    market_total_matched: Optional[float] = None,
) -> Optional[Tuple[float, float, float, float, Dict[str, float]]]:
    """
    Compute back-liquidity Imbalance Index (snapshot-only; no totalMatched in index).

    Args:
        runners: List of runner objects (dict or resource) from listMarketBook.
        runner_metadata: Map selectionId -> 'HOME' | 'AWAY' | 'DRAW'.
        depth_limit: Use only first N levels of availableToBack (default 3).
        market_total_matched: If provided, use as total_volume (reporting only); else sum runner totalMatched.

    Returns:
        (home_risk, away_risk, draw_risk, total_volume, risks_by_name) or None if not all three roles present.
        Risk values = L - P (liability minus opposing back-liquidity pressure). total_volume for reporting only.
    """
    # Build selection_id -> runner
    by_sid: Dict[Union[int, str], Any] = {}
    for r in runners:
        sid = _sid(r)
        if sid is not None:
            by_sid[sid] = r

    required = {"HOME", "AWAY", "DRAW"}
    role_to_runner: Dict[str, Any] = {}
    for sid_key, role in runner_metadata.items():
        role_upper = (role or "").upper()
        if role_upper not in required:
            continue
        if sid_key in by_sid:
            role_to_runner[role_upper] = by_sid[sid_key]

    if set(role_to_runner.keys()) != required:
        missing = required - set(role_to_runner.keys())
        logger.warning(
            "Imbalance index skipped: missing selection(s) for role(s) %s (need HOME, AWAY, DRAW).",
            missing,
        )
        return None

    home_runner = role_to_runner["HOME"]
    away_runner = role_to_runner["AWAY"]
    draw_runner = role_to_runner["DRAW"]

    # total_volume for reporting only (not used in index)
    if market_total_matched is not None:
        total_volume = _safe_float(market_total_matched)
    else:
        total_volume = sum(_total_matched(r) for r in runners)

    def opposing_pressure(target_runner: Any) -> float:
        """P = sum of L (liability) from the other two runners (same units as L)."""
        others = [r for r in (home_runner, away_runner, draw_runner) if r is not target_runner]
        return sum(_liability(r, depth_limit) for r in others)

    home_risk = _liability(home_runner, depth_limit) - opposing_pressure(home_runner)
    away_risk = _liability(away_runner, depth_limit) - opposing_pressure(away_runner)
    draw_risk = _liability(draw_runner, depth_limit) - opposing_pressure(draw_runner)

    risks_by_name = {"home": home_risk, "away": away_risk, "draw": draw_risk}
    return home_risk, away_risk, draw_risk, total_volume, risks_by_name
