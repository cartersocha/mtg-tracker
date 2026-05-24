# tests/test_state.py
import json
import pytest
from datetime import date, timedelta
from pathlib import Path
from state import (
    load_price_history,
    save_price_history,
    load_alert_state,
    save_alert_state,
    append_price,
    prune_history,
    get_card_history,
    init_alert_state_for_card,
)


class TestLoadSavePriceHistory:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = load_price_history(tmp_path / "price_history.json")
        assert result == {}

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "price_history.json"
        data = {"Roaming Throne": {"nonfoil": {"2024-01-01": 45.83}, "foil": {}}}
        save_price_history(data, path)
        assert load_price_history(path) == data

    def test_creates_parent_dir_if_missing(self, tmp_path):
        path = tmp_path / "subdir" / "price_history.json"
        save_price_history({}, path)
        assert path.exists()


class TestLoadSaveAlertState:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = load_alert_state(tmp_path / "alert_state.json")
        assert result == {}

    def test_roundtrip(self, tmp_path):
        path = tmp_path / "alert_state.json"
        state = {"Roaming Throne": {"nonfoil": {"manual": None, "pct_drop": 45.83}}}
        save_alert_state(state, path)
        assert load_alert_state(path) == state


class TestAppendPrice:
    def test_adds_new_card(self):
        h = append_price({}, "Cyclonic Rift", "nonfoil", "2024-01-01", 33.0)
        assert h["Cyclonic Rift"]["nonfoil"]["2024-01-01"] == 33.0

    def test_does_not_overwrite_existing_date(self):
        h = {"Cyclonic Rift": {"nonfoil": {"2024-01-01": 33.0}, "foil": {}}}
        h = append_price(h, "Cyclonic Rift", "nonfoil", "2024-01-01", 99.0)
        assert h["Cyclonic Rift"]["nonfoil"]["2024-01-01"] == 33.0

    def test_adds_foil_separately(self):
        h = append_price({}, "Cyclonic Rift", "foil", "2024-01-01", 55.0)
        assert h["Cyclonic Rift"]["foil"]["2024-01-01"] == 55.0

    def test_creates_missing_foil_type_key(self):
        h = {"Cyclonic Rift": {"nonfoil": {"2024-01-01": 33.0}}}
        h = append_price(h, "Cyclonic Rift", "foil", "2024-01-01", 55.0)
        assert h["Cyclonic Rift"]["foil"]["2024-01-01"] == 55.0


class TestPruneHistory:
    def test_removes_entries_older_than_365_days(self):
        today = date.today()
        old = (today - timedelta(days=400)).isoformat()
        recent = (today - timedelta(days=10)).isoformat()
        h = {"Card": {"nonfoil": {old: 50.0, recent: 45.0}, "foil": {}}}
        pruned = prune_history(h, days=365)
        assert old not in pruned["Card"]["nonfoil"]
        assert recent in pruned["Card"]["nonfoil"]

    def test_keeps_entries_within_window(self):
        today = date.today()
        dates = {(today - timedelta(days=i)).isoformat(): 45.0 for i in range(364)}
        h = {"Card": {"nonfoil": dates, "foil": {}}}
        pruned = prune_history(h, days=365)
        assert len(pruned["Card"]["nonfoil"]) == 364

    def test_empty_history_no_crash(self):
        pruned = prune_history({}, days=365)
        assert pruned == {}


class TestGetCardHistory:
    def test_returns_history_for_known_card(self):
        h = {"Card": {"nonfoil": {"2024-01-01": 45.0}, "foil": {}}}
        assert get_card_history(h, "Card", "nonfoil") == {"2024-01-01": 45.0}

    def test_returns_empty_for_unknown_card(self):
        assert get_card_history({}, "Unknown", "nonfoil") == {}

    def test_returns_empty_for_missing_foil_type(self):
        h = {"Card": {"nonfoil": {"2024-01-01": 45.0}}}
        assert get_card_history(h, "Card", "foil") == {}


class TestInitAlertState:
    def test_creates_null_state_for_new_card(self):
        state = init_alert_state_for_card({}, "Roaming Throne")
        assert state["Roaming Throne"]["nonfoil"]["manual"] is None
        assert state["Roaming Throne"]["nonfoil"]["pct_drop"] is None
        assert state["Roaming Throne"]["nonfoil"]["pct_off_52w_high"] is None
        assert state["Roaming Throne"]["nonfoil"]["near_52w_low"] is None
        assert state["Roaming Throne"]["foil"]["manual"] is None

    def test_does_not_overwrite_existing_card(self):
        state = {"Roaming Throne": {"nonfoil": {"manual": 45.0}}}
        state = init_alert_state_for_card(state, "Roaming Throne")
        assert state["Roaming Throne"]["nonfoil"]["manual"] == 45.0
