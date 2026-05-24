# scripts/triggers.py
"""
Trigger evaluation logic for MTG price alerts.
All functions are pure — no I/O, no side effects.
"""
from datetime import date, timedelta
from typing import Optional


def check_manual_target(current_price: float, target: Optional[float]) -> bool:
    """Returns True if current_price is at or below target."""
    if target is None:
        return False
    return current_price <= target


def check_pct_drop(
    current_price: float,
    history: dict[str, float],
    threshold_pct: float,
    lookback_days: int,
) -> tuple[bool, dict]:
    """
    Returns (fired, details).
    details keys: actual_days, comparison_price, pct_change, skip_reason (if not fired).
    Fires when price dropped >= threshold_pct% compared to lookback_days ago.
    Requires at least 7 days of history.
    """
    if len(history) < 7:
        return False, {"skip_reason": "insufficient history (< 7 days)"}

    sorted_dates = sorted(history.keys())
    today = date.today()
    target_date = (today - timedelta(days=lookback_days)).isoformat()

    older_dates = [d for d in sorted_dates if d <= target_date]
    if older_dates:
        ref_date = older_dates[-1]
    else:
        ref_date = sorted_dates[0]

    past_price = history[ref_date]
    actual_days = (today - date.fromisoformat(ref_date)).days

    if past_price == 0:
        return False, {"skip_reason": "past price is zero"}

    pct_change = (past_price - current_price) / past_price * 100
    details = {
        "actual_days": actual_days,
        "comparison_price": past_price,
        "pct_change": pct_change,
    }

    if pct_change >= threshold_pct:
        return True, details
    return False, details


def check_pct_off_52w_high(
    current_price: float,
    history: dict[str, float],
    threshold_pct: float,
) -> tuple[bool, dict]:
    """
    Returns (fired, details).
    details keys: high_52w, pct_change (or high_52w=None if skipped).
    Fires when current price is >= threshold_pct% below the 52-week high.
    Requires at least 30 days of history.
    """
    if len(history) < 30:
        return False, {"high_52w": None, "skip_reason": f"insufficient history ({len(history)} days, need 30)"}

    high_52w = max(history.values())
    if high_52w == 0:
        return False, {"high_52w": None, "skip_reason": "52w high is zero"}

    pct_off = (high_52w - current_price) / high_52w * 100
    details = {"high_52w": high_52w, "pct_change": pct_off}

    if pct_off >= threshold_pct:
        return True, details
    return False, details


def check_near_52w_low(
    current_price: float,
    history: dict[str, float],
    threshold_pct: float,
) -> tuple[bool, dict]:
    """
    Returns (fired, details).
    details keys: low_52w, pct_change (or low_52w=None if skipped).
    Fires when current price is within threshold_pct% above the 52-week low.
    Requires at least 30 days of history.
    """
    if len(history) < 30:
        return False, {"low_52w": None, "skip_reason": f"insufficient history ({len(history)} days, need 30)"}

    low_52w = min(history.values())
    if low_52w == 0:
        return False, {"low_52w": None, "skip_reason": "52w low is zero"}

    pct_above = (current_price - low_52w) / low_52w * 100
    details = {"low_52w": low_52w, "pct_change": pct_above}

    if pct_above <= threshold_pct:
        return True, details
    return False, details


def apply_rearm(
    condition_met: bool,
    last_alert_price: Optional[float],
    current_price: float,
    recovery_pct: float,
) -> tuple[bool, Optional[float]]:
    """
    Apply re-arm logic. Returns (should_fire, new_last_alert_price).

    Step 1 — Recovery reset:
        If price rose >= recovery_pct above last_alert_price, reset to None.
    Step 2 — Fire check:
        If condition met and (never fired OR dropped further), fire.
        Otherwise suppress.
    """
    if last_alert_price is not None:
        if current_price > last_alert_price * (1 + recovery_pct / 100):
            last_alert_price = None

    if not condition_met:
        return False, last_alert_price

    if last_alert_price is None:
        return True, current_price

    if current_price < last_alert_price:
        return True, current_price

    return False, last_alert_price
