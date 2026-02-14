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

Also: Impedance Index (Exposure/Liability) from marketBook snapshot.
  Top 4 levels per side (back/lay), VWAP-aggregated; Impedance(j) = -bookPnL_ifWin(j).
"""

import logging
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("betfair_rest_client.risk")

# Decimal context for impedance (avoid float drift)
_ctx = getcontext()
_ctx.prec = 28
_ctx.rounding = ROUND_HALF_UP

IMPEDANCE_EPS = Decimal("1e-9")
IMPEDANCE_DEPTH_LEVELS = 4

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


# -----------------------------------------------------------------------------
# Impedance Index (Exposure/Liability from marketBook snapshot)
# -----------------------------------------------------------------------------


def _to_decimal(val: Any) -> Decimal:
    """Convert to Decimal; None or non-numeric -> 0."""
    if val is None:
        return Decimal("0")
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0")


def _price_size_decimal(level: Any) -> Tuple[Decimal, Decimal]:
    """Parse (price, size) from level; dict {price, size} or list [price, size]. Invalid -> (0, 0)."""
    if isinstance(level, (list, tuple)) and len(level) >= 2:
        return _to_decimal(level[0]), _to_decimal(level[1])
    if isinstance(level, dict):
        p = _to_decimal(level.get("price") or level.get("Price"))
        s = _to_decimal(level.get("size") or level.get("Size"))
        return p, s
    return Decimal("0"), Decimal("0")


# Output boundary: Decimal -> float, no NaN/Inf; round for logging/DB (e.g. 8 decimals)
IMPEDANCE_OUTPUT_DECIMALS = 8


def _safe_float_output(val: Decimal) -> float:
    """Convert Decimal to float at output boundary; round and clamp to finite value."""
    try:
        f = float(val)
    except (OverflowError, TypeError, ValueError):
        return 0.0
    if f != f or f == float("inf") or f == float("-inf"):
        return 0.0
    return round(f, IMPEDANCE_OUTPUT_DECIMALS)


def _snapshot_ts_to_iso8601(snapshot_ts: Any) -> str:
    """Normalize snapshot_ts (datetime | str | None) to ISO-8601 string for output."""
    if snapshot_ts is None:
        return ""
    if hasattr(snapshot_ts, "isoformat"):
        return snapshot_ts.isoformat()
    s = str(snapshot_ts).strip()
    return s if s else ""


def compute_impedance_index(
    runners: List[Any],
    snapshot_ts: Optional[Union[str, Any]] = None,
    depth_limit: int = IMPEDANCE_DEPTH_LEVELS,
    normalise: bool = True,
) -> Dict[str, Any]:
    """
    Compute Impedance Index (Exposure/Liability) for a single marketBook snapshot.

    Input: runners as returned by Betfair listMarketBook (selectionId, ex.availableToBack, ex.availableToLay).
    snapshot_ts: datetime, str, or None; output snapshot_ts is always an ISO-8601 string (or "" if None).
    Uses top 4 levels per side (or depth_limit), aggregated with VWAP.
    Sign: Impedance(j) = -bookPnL_ifWin(j). Large positive = high loss for book if runner wins.

    Edge cases: fewer than 4 levels -> use available; missing side -> stake 0; odds<=1 or size<=0 -> ignore;
    no liquidity -> all impedance/normImpedance 0.

    Returns:
        { "snapshot_ts": str (ISO-8601), "runners": [ ... ] }.
        Runners are sorted by selectionId. Numeric values are rounded float (no NaN/Inf); Decimal used internally.
    """
    ordered: List[Any] = []
    seen_sids: set = set()
    for r in runners:
        sid = _sid(r)
        if sid is None:
            continue
        if sid in seen_sids:
            continue
        seen_sids.add(sid)
        ordered.append(r)

    def _sort_key(r: Any):
        s = _sid(r)
        if s is None:
            return (1, "")
        return (0, str(s)) if isinstance(s, (int, float)) else (0, str(s))

    ordered.sort(key=_sort_key)

    per_runner: Dict[Union[int, str], Dict[str, Decimal]] = {}

    for r in ordered:
        sid = _sid(r)
        if sid is None:
            continue

        atb = _get_ex_side(r, "availableToBack")[:depth_limit]
        back_notional = Decimal("0")
        back_stake = Decimal("0")
        for level in atb:
            price, size = _price_size_decimal(level)
            if size <= 0 or price <= 1:
                continue
            back_notional += price * size
            back_stake += size

        back_odds = (back_notional / (back_stake + IMPEDANCE_EPS)) if back_stake > 0 else Decimal("0")

        atl = _get_ex_side(r, "availableToLay")[:depth_limit]
        lay_notional = Decimal("0")
        lay_stake = Decimal("0")
        for level in atl:
            price, size = _price_size_decimal(level)
            if size <= 0 or price <= 1:
                continue
            lay_notional += price * size
            lay_stake += size

        lay_odds = (lay_notional / (lay_stake + IMPEDANCE_EPS)) if lay_stake > 0 else Decimal("0")

        liability_back = (back_odds - Decimal("1")) * back_stake
        win_back = back_stake
        win_lay = (lay_odds - Decimal("1")) * lay_stake
        payout_lay = lay_stake

        per_runner[sid] = {
            "backStake": back_stake,
            "backOdds": back_odds,
            "layStake": lay_stake,
            "layOdds": lay_odds,
            "liability_back": liability_back,
            "win_back": win_back,
            "payout_lay": payout_lay,
            "win_lay": win_lay,
        }

    total_back = sum(v["backStake"] for v in per_runner.values())
    total_lay = sum(v["layStake"] for v in per_runner.values())
    scale = (total_back + total_lay) if (total_back + total_lay) > 0 else IMPEDANCE_EPS
    no_liquidity = (total_back + total_lay) <= 0

    out_runners: List[Dict[str, Any]] = []
    for r in ordered:
        sid = _sid(r)
        if sid is None or sid not in per_runner:
            continue
        comp_j = per_runner[sid]
        win_lay_j = comp_j["win_lay"]
        liability_back_j = comp_j["liability_back"]
        others_pnl = Decimal("0")
        for sid_i, comp_i in per_runner.items():
            if sid_i == sid:
                continue
            others_pnl += comp_i["win_back"] - comp_i["payout_lay"]
        book_pnl_if_win_j = (win_lay_j - liability_back_j) + others_pnl
        impedance = -book_pnl_if_win_j
        if no_liquidity:
            impedance = Decimal("0")
            norm_impedance = Decimal("0")
        else:
            norm_impedance = (impedance / scale) if normalise else Decimal("0")

        out_runners.append({
            "selectionId": sid,
            "impedance": _safe_float_output(impedance),
            "normImpedance": _safe_float_output(norm_impedance),
            "backStake": _safe_float_output(comp_j["backStake"]),
            "backOdds": _safe_float_output(comp_j["backOdds"]),
            "layStake": _safe_float_output(comp_j["layStake"]),
            "layOdds": _safe_float_output(comp_j["layOdds"]),
        })

    def _runner_sort_key(ro: Dict[str, Any]) -> Tuple[int, Union[int, str]]:
        sid = ro["selectionId"]
        if isinstance(sid, (int, float)):
            return (0, int(sid) if sid == int(sid) else sid)
        return (1, str(sid))
    out_runners.sort(key=_runner_sort_key)
    return {
        "snapshot_ts": _snapshot_ts_to_iso8601(snapshot_ts),
        "runners": out_runners,
    }
