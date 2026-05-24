# tests/conftest.py
import sys
from pathlib import Path
from datetime import date, timedelta
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))


def make_history(days: int, start_price: float, end_price: float) -> dict:
    """Generate a linear price history dict from start_price to end_price over N days."""
    today = date.today()
    history = {}
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        price = start_price + (end_price - start_price) * i / max(days - 1, 1)
        history[d.isoformat()] = round(price, 2)
    return history


@pytest.fixture
def flat_history_30d():
    return make_history(30, 50.0, 50.0)


@pytest.fixture
def declining_history_365d():
    return make_history(365, 80.0, 45.0)
