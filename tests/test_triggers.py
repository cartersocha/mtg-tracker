# tests/test_triggers.py
import pytest
from datetime import date, timedelta
from conftest import make_history
from triggers import (
    check_manual_target,
    check_pct_drop,
    check_pct_off_52w_high,
    check_near_52w_low,
    apply_rearm,
)


class TestManualTarget:
    def test_fires_at_target(self):
        assert check_manual_target(45.00, 45.00) is True

    def test_fires_below_target(self):
        assert check_manual_target(40.00, 45.00) is True

    def test_does_not_fire_above_target(self):
        assert check_manual_target(46.00, 45.00) is False

    def test_null_target_no_alert(self):
        assert check_manual_target(45.00, None) is False


class TestPctDrop:
    def test_fires_on_sufficient_drop(self):
        history = make_history(31, 60.00, 45.00)
        fired, _ = check_pct_drop(45.00, history, threshold_pct=15, lookback_days=30)
        assert fired is True

    def test_does_not_fire_on_small_drop(self):
        history = make_history(31, 50.00, 47.00)
        fired, _ = check_pct_drop(47.00, history, threshold_pct=15, lookback_days=30)
        assert fired is False

    def test_does_not_fire_on_price_increase(self):
        history = make_history(31, 40.00, 50.00)
        fired, _ = check_pct_drop(50.00, history, threshold_pct=15, lookback_days=30)
        assert fired is False

    def test_skips_fewer_than_7_days(self):
        history = make_history(6, 60.00, 40.00)
        fired, msg = check_pct_drop(40.00, history, threshold_pct=15, lookback_days=30)
        assert fired is False
        assert "insufficient" in msg.get("skip_reason", "").lower()

    def test_uses_oldest_available_when_lookback_exceeds_history(self):
        history = make_history(15, 60.00, 45.00)
        fired, _ = check_pct_drop(45.00, history, threshold_pct=15, lookback_days=30)
        assert fired is True

    def test_returns_actual_days_used(self):
        history = make_history(15, 60.00, 45.00)
        _, details = check_pct_drop(45.00, history, threshold_pct=15, lookback_days=30)
        assert details["actual_days"] <= 15

    def test_empty_history_no_crash(self):
        fired, _ = check_pct_drop(45.00, {}, threshold_pct=15, lookback_days=30)
        assert fired is False


class TestPctOff52wHigh:
    def test_fires_when_well_below_high(self):
        history = make_history(31, 80.00, 55.00)
        fired, details = check_pct_off_52w_high(55.00, history, threshold_pct=25)
        assert fired is True
        assert details["high_52w"] is not None

    def test_does_not_fire_near_high(self):
        history = make_history(31, 60.00, 55.00)
        fired, _ = check_pct_off_52w_high(55.00, history, threshold_pct=25)
        assert fired is False

    def test_skips_fewer_than_30_days(self):
        history = make_history(29, 80.00, 55.00)
        fired, details = check_pct_off_52w_high(55.00, history, threshold_pct=25)
        assert fired is False
        assert details["high_52w"] is None

    def test_empty_history_no_crash(self):
        fired, details = check_pct_off_52w_high(45.00, {}, threshold_pct=25)
        assert fired is False
        assert details["high_52w"] is None


class TestNear52wLow:
    def test_fires_when_near_low(self):
        history = make_history(31, 80.00, 45.00)
        fired, details = check_near_52w_low(45.50, history, threshold_pct=10)
        assert fired is True
        assert details["low_52w"] is not None

    def test_does_not_fire_well_above_low(self):
        history = make_history(31, 80.00, 40.00)
        fired, _ = check_near_52w_low(70.00, history, threshold_pct=10)
        assert fired is False

    def test_skips_fewer_than_30_days(self):
        history = make_history(29, 80.00, 45.00)
        fired, details = check_near_52w_low(45.50, history, threshold_pct=10)
        assert fired is False
        assert details["low_52w"] is None

    def test_empty_history_no_crash(self):
        fired, details = check_near_52w_low(45.00, {}, threshold_pct=10)
        assert fired is False
        assert details["low_52w"] is None


class TestRearm:
    def test_fires_first_time(self):
        should_fire, new_price = apply_rearm(True, None, 45.00, recovery_pct=10.0)
        assert should_fire is True
        assert new_price == 45.00

    def test_suppresses_at_same_price(self):
        should_fire, _ = apply_rearm(True, 45.00, 45.00, recovery_pct=10.0)
        assert should_fire is False

    def test_suppresses_above_last_alert_price(self):
        should_fire, _ = apply_rearm(True, 45.00, 46.00, recovery_pct=10.0)
        assert should_fire is False

    def test_fires_on_further_drop(self):
        should_fire, new_price = apply_rearm(True, 45.00, 40.00, recovery_pct=10.0)
        assert should_fire is True
        assert new_price == 40.00

    def test_recovery_resets_last_alert_price(self):
        _, new_price = apply_rearm(False, 45.00, 50.00, recovery_pct=10.0)
        assert new_price is None

    def test_fires_fresh_after_recovery(self):
        _, after_recovery = apply_rearm(False, 45.00, 50.00, recovery_pct=10.0)
        assert after_recovery is None
        should_fire, new_price = apply_rearm(True, after_recovery, 44.00, recovery_pct=10.0)
        assert should_fire is True
        assert new_price == 44.00

    def test_no_fire_when_condition_not_met(self):
        should_fire, last = apply_rearm(False, None, 50.00, recovery_pct=10.0)
        assert should_fire is False
        assert last is None

    def test_no_fire_and_state_unchanged_when_suppressed(self):
        should_fire, new_price = apply_rearm(True, 45.00, 45.50, recovery_pct=10.0)
        assert should_fire is False
        assert new_price == 45.00


class TestEdgeCases:
    def test_single_day_history_pct_drop_skips(self):
        history = {date.today().isoformat(): 50.0}
        fired, _ = check_pct_drop(50.00, history, threshold_pct=15, lookback_days=30)
        assert fired is False

    def test_single_day_history_52w_skips(self):
        history = {date.today().isoformat(): 50.0}
        fired, _ = check_pct_off_52w_high(50.00, history, threshold_pct=25)
        assert fired is False

    def test_history_with_gaps_no_crash(self):
        today = date.today()
        history = {
            (today - timedelta(days=i * 2)).isoformat(): 50.0 - i
            for i in range(20)
        }
        fired, _ = check_pct_drop(40.00, history, threshold_pct=15, lookback_days=30)
        # Should not crash
