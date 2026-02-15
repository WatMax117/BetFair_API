"""
Book Risk L3 for Match Odds markets.

3-way exposure at top N back levels: R[o] = W[o] - L[o]. Uses runner_metadata (selectionId -> HOME/AWAY/DRAW).
Imbalance Index and Impedance Index removed (MVP simplification).
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


def _get_ex_side(runner: Any, key: str) -> List[Any]:
    """Get ex.availableToBack or ex.availableToLay list. key: 'availableToBack' | 'availableToLay'."""
    ex = runner.get("ex") if isinstance(runner, dict) else getattr(runner, "ex", None)
    if not ex:
        return []
    if isinstance(ex, dict):
        side = ex.get(key)
    else:
        side = getattr(ex, key, None) or getattr(ex, key[0].lower() + "".join("_" + c.lower() if c.isupper() else c for c in key[1:]), None)
    return side if side else []


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


# -----------------------------------------------------------------------------
# 3-way Book Risk / Exposure (per snapshot)
# -----------------------------------------------------------------------------
# Level-based: S[o,i] = size, O[o,i] = price at level i for outcome o (from availableToBack).
# W[o] = Σ_i S[o,i]*(O[o,i]-1) = winners' net payout if o happens.
# L[o] = Σ_{p≠o} Σ_i S[p,i] = losers' stakes collected if o happens.
# R[o] = W[o] - L[o]. R[o] > 0 = book loses; R[o] < 0 = book wins.
# Uses top 3 levels per outcome (or fewer if not available); ordering = best price first.
# -----------------------------------------------------------------------------


def compute_book_risk_l3(
    runners: List[Any],
    runner_metadata: Dict[Union[int, str], str],
    depth_limit: int = 3,
) -> Optional[Dict[str, float]]:
    """
    3-way Book Risk (exposure) per snapshot: R[o] = W[o] - L[o] for o in {HOME, AWAY, DRAW}.

    Data source: ex.availableToBack per runner. Each level i has (price, size) -> S[o,i], O[o,i].
    Uses first `depth_limit` levels (default 3); if fewer exist, uses available levels.
    Returns home_book_risk_l3, away_book_risk_l3, draw_book_risk_l3; or None if not all three roles.
    """
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
        return None

    def winners_net_payout(runner: Any) -> float:
        """W[o] = Σ_i S[o,i] * (O[o,i] - 1) over first depth_limit back levels."""
        total = 0.0
        atb = _get_atb(runner)
        for level in atb[:depth_limit]:
            price, size = _price_size(level)
            if size <= 0:
                continue
            total += size * (price - 1.0)
        return total

    def total_stake(runner: Any) -> float:
        """Σ_i S[o,i] for outcome o."""
        total = 0.0
        atb = _get_atb(runner)
        for level in atb[:depth_limit]:
            _, size = _price_size(level)
            total += size
        return total

    home_runner = role_to_runner["HOME"]
    away_runner = role_to_runner["AWAY"]
    draw_runner = role_to_runner["DRAW"]

    w_home = winners_net_payout(home_runner)
    w_away = winners_net_payout(away_runner)
    w_draw = winners_net_payout(draw_runner)

    stake_home = total_stake(home_runner)
    stake_away = total_stake(away_runner)
    stake_draw = total_stake(draw_runner)

    # L[o] = sum of stakes on all other outcomes
    l_home = stake_away + stake_draw
    l_away = stake_home + stake_draw
    l_draw = stake_home + stake_away

    r_home = w_home - l_home
    r_away = w_away - l_away
    r_draw = w_draw - l_draw

    return {
        "home_book_risk_l3": r_home,
        "away_book_risk_l3": r_away,
        "draw_book_risk_l3": r_draw,
    }


