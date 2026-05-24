# scripts/state.py
"""
Read/write price_history.json and alert_state.json.
All functions accept explicit path arguments for testability.
"""
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

DEFAULT_PRICE_HISTORY_PATH = Path("data/price_history.json")
DEFAULT_ALERT_STATE_PATH = Path("data/alert_state.json")


def load_price_history(path: Path = DEFAULT_PRICE_HISTORY_PATH) -> dict:
    """Load price history from disk. Returns empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_price_history(history: dict, path: Path = DEFAULT_PRICE_HISTORY_PATH) -> None:
    """Save price history to disk. Creates parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")


def load_alert_state(path: Path = DEFAULT_ALERT_STATE_PATH) -> dict:
    """Load alert state from disk. Returns empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_alert_state(state: dict, path: Path = DEFAULT_ALERT_STATE_PATH) -> None:
    """Save alert state to disk. Creates parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def append_price(
    history: dict,
    card_name: str,
    foil_type: str,
    price_date: str,
    price: float,
) -> dict:
    """
    Append a price entry to history in-memory. Does not write to disk.
    Skips if the date already exists (idempotent).
    foil_type: "nonfoil" or "foil"
    """
    if card_name not in history:
        history[card_name] = {"nonfoil": {}, "foil": {}}
    if foil_type not in history[card_name]:
        history[card_name][foil_type] = {}
    if price_date not in history[card_name][foil_type]:
        history[card_name][foil_type][price_date] = price
    return history


def prune_history(history: dict, days: int = 365) -> dict:
    """Remove price entries older than `days` days. Returns modified history."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    for card in history:
        for foil_type in list(history[card].keys()):
            history[card][foil_type] = {
                d: p for d, p in history[card][foil_type].items()
                if d >= cutoff
            }
    return history


def get_card_history(history: dict, card_name: str, foil_type: str) -> dict:
    """Return price history for a specific card and foil type. Empty dict if not found."""
    return history.get(card_name, {}).get(foil_type, {})


def init_alert_state_for_card(state: dict, card_name: str) -> dict:
    """Add a card to alert state with all-null triggers if not already present."""
    if card_name not in state:
        state[card_name] = {
            "nonfoil": {
                "manual": None,
                "pct_drop": None,
                "pct_off_52w_high": None,
                "near_52w_low": None,
            },
            "foil": {
                "manual": None,
                "pct_drop": None,
                "pct_off_52w_high": None,
                "near_52w_low": None,
            },
        }
    return state
