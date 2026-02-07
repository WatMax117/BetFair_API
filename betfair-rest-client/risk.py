"""
Market Imbalance Index (Risk Index) for Match Odds markets (Valeri.docx).

Metadata-aware: uses runner_metadata mapping selectionId -> 'HOME' | 'AWAY' | 'DRAW'.
Depth-limited: only first `depth_limit` levels of availableToBack (default 3).

Formula:
  Liability (L): sum of (size * (price - 1)) for target selection's Back offers (up to depth_limit).
  Stakes (S): sum of totalMatched on other selections + availableToBack (current offers) on other selections (up to depth_limit).
  Net Index: Risk = L - S.
  total_volume: strictly from market_book.total_matched (market-level field) when provided.
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


def _back_volume(runner: Any, depth_limit: int) -> float:
    """Sum of sizes for first depth_limit levels of AvailableToBack."""
    total = 0.0
    atb = _get_atb(runner)
    for level in atb[:depth_limit]:
        _, size = _price_size(level)
        total += size
    return total


def _total_matched(runner: Any) -> float:
    """Runner-level totalMatched for stake calculation (explicit runner.total_matched)."""
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
    Compute Market Imbalance Index using selectionId -> role mapping. No list-order assumption.

    Args:
        runners: List of runner objects (dict or resource) from listMarketBook.
        runner_metadata: Map selectionId -> 'HOME' | 'AWAY' | 'DRAW'.
        depth_limit: Use only first N levels of availableToBack (default 3).
        market_total_matched: If provided, use as total_volume (market_book.total_matched); else sum runner totalMatched.

    Returns:
        (home_risk, away_risk, draw_risk, total_volume, risks_by_name) or None if not all three roles present.
        total_volume = market_total_matched when provided, else sum of runner totalMatched.
        Stakes use runner.total_matched explicitly.
        risks_by_name: keys "home", "away", "draw" with risk values.
    """
    # Build selection_id -> runner
    by_sid: Dict[Union[int, str], Any] = {}
    for r in runners:
        sid = _sid(r)
        if sid is not None:
            by_sid[sid] = r

    required = {"HOME", "AWAY", "DRAW"}
    # Resolve role -> runner (must have exactly one selection per role for valid market)
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
            "Risk index skipped: missing selection(s) for role(s) %s (need HOME, AWAY, DRAW).",
            missing,
        )
        return None

    home_runner = role_to_runner["HOME"]
    away_runner = role_to_runner["AWAY"]
    draw_runner = role_to_runner["DRAW"]

    # Log once per market when any runner has missing or zero total_matched (per-selection volume from API)
    for role_name, r in [("HOME", home_runner), ("AWAY", away_runner), ("DRAW", draw_runner)]:
        sid = _sid(r)
        tm = _total_matched(r)
        if tm == 0.0:
            logger.debug(
                "Runner %s (role=%s) has missing or zero total_matched; per-selection volume may not be from API.",
                sid, role_name,
            )

    # total_volume strictly from market_book.total_matched (market-level field) for consistency
    if market_total_matched is not None:
        total_volume = _safe_float(market_total_matched)
    else:
        logger.debug("market_total_matched not provided; using sum of runner totalMatched for total_volume.")
        total_volume = sum(_total_matched(r) for r in runners)

    def stakes_for_target(target_runner: Any) -> float:
        """S = totalMatched on other two + availableToBack (depth-limited) on other two."""
        others = [r for r in (home_runner, away_runner, draw_runner) if r is not target_runner]
        s = 0.0
        for r in others:
            s += _total_matched(r) + _back_volume(r, depth_limit)
        return s

    home_risk = _liability(home_runner, depth_limit) - stakes_for_target(home_runner)
    away_risk = _liability(away_runner, depth_limit) - stakes_for_target(away_runner)
    draw_risk = _liability(draw_runner, depth_limit) - stakes_for_target(draw_runner)

    risks_by_name = {"home": home_risk, "away": away_risk, "draw": draw_risk}
    return home_risk, away_risk, draw_risk, total_volume, risks_by_name
