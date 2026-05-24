# tests/test_bootstrap.py
"""
Unit tests for MTGJSON parsing logic.
Uses in-memory fixture data — no network calls, no file I/O.
"""
import pytest
from datetime import date, timedelta
from mtgjson import find_uuids_for_card, extract_price_series, compute_min_daily_price

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TWO_DAYS_AGO = (date.today() - timedelta(days=2)).isoformat()

FAKE_ALL_PRINTINGS = {
    "data": {
        "LCI": {
            "cards": [
                {"uuid": "uuid-cav-1", "name": "Cavern of Souls"},
                {"uuid": "uuid-cav-2", "name": "Cavern of Souls"},
                {"uuid": "uuid-bolt-1", "name": "Lightning Bolt"},
            ]
        },
        "MH2": {
            "cards": [
                {"uuid": "uuid-cav-3", "name": "Cavern of Souls"},
            ]
        },
    }
}

FAKE_ALL_PRICES = {
    "data": {
        "uuid-cav-1": {
            "paper": {
                "tcgplayer": {
                    "retail": {
                        "normal": {TODAY: 48.00, YESTERDAY: 50.00},
                        "foil": {TODAY: 90.00},
                    }
                }
            }
        },
        "uuid-cav-2": {
            "paper": {
                "tcgplayer": {
                    "retail": {
                        "normal": {TODAY: 46.00, YESTERDAY: 47.00},
                        "foil": {TODAY: 85.00},
                    }
                }
            }
        },
        "uuid-cav-3": {
            "paper": {
                "tcgplayer": {
                    "retail": {
                        "normal": {TWO_DAYS_AGO: 44.00},
                        "foil": {},
                    }
                }
            }
        },
        "uuid-bolt-1": {
            "paper": {
                "tcgplayer": {
                    "retail": {
                        "normal": {TODAY: 1.50},
                        "foil": {},
                    }
                }
            }
        },
    }
}


class TestFindUuidsForCard:
    def test_finds_all_matching_uuids(self):
        uuids = find_uuids_for_card("Cavern of Souls", FAKE_ALL_PRINTINGS)
        assert set(uuids) == {"uuid-cav-1", "uuid-cav-2", "uuid-cav-3"}

    def test_case_insensitive(self):
        uuids = find_uuids_for_card("cavern of souls", FAKE_ALL_PRINTINGS)
        assert len(uuids) == 3

    def test_returns_empty_for_unknown_card(self):
        uuids = find_uuids_for_card("Nonexistent Card", FAKE_ALL_PRINTINGS)
        assert uuids == []

    def test_does_not_partial_match(self):
        uuids = find_uuids_for_card("Cavern", FAKE_ALL_PRINTINGS)
        assert uuids == []

    def test_no_duplicate_uuids(self):
        uuids = find_uuids_for_card("Cavern of Souls", FAKE_ALL_PRINTINGS)
        assert len(uuids) == len(set(uuids))


class TestExtractPriceSeries:
    def test_extracts_normal_series(self):
        series = extract_price_series("uuid-cav-1", "normal", FAKE_ALL_PRICES)
        assert series[TODAY] == 48.00
        assert series[YESTERDAY] == 50.00

    def test_extracts_foil_series(self):
        series = extract_price_series("uuid-cav-1", "foil", FAKE_ALL_PRICES)
        assert series[TODAY] == 90.00

    def test_returns_empty_for_unknown_uuid(self):
        series = extract_price_series("uuid-missing", "normal", FAKE_ALL_PRICES)
        assert series == {}

    def test_returns_empty_for_missing_price_type(self):
        # uuid-cav-3 has no foil prices
        series = extract_price_series("uuid-cav-3", "foil", FAKE_ALL_PRICES)
        assert series == {}

    def test_returns_empty_for_missing_tcgplayer_key(self):
        fake = {"data": {"uuid-x": {"paper": {}}}}
        series = extract_price_series("uuid-x", "normal", fake)
        assert series == {}


class TestComputeMinDailyPrice:
    def test_picks_minimum_across_uuids_same_date(self):
        series = [
            {TODAY: 48.00, YESTERDAY: 50.00},
            {TODAY: 46.00, YESTERDAY: 47.00},
        ]
        result = compute_min_daily_price(series)
        assert result[TODAY] == 46.00
        assert result[YESTERDAY] == 47.00

    def test_handles_dates_only_in_one_series(self):
        series = [
            {TODAY: 48.00},
            {YESTERDAY: 47.00},
        ]
        result = compute_min_daily_price(series)
        assert result[TODAY] == 48.00
        assert result[YESTERDAY] == 47.00

    def test_empty_list_returns_empty(self):
        assert compute_min_daily_price([]) == {}

    def test_empty_series_in_list_no_crash(self):
        result = compute_min_daily_price([{}, {TODAY: 46.00}])
        assert result[TODAY] == 46.00

    def test_single_series(self):
        result = compute_min_daily_price([{TODAY: 42.00}])
        assert result[TODAY] == 42.00
