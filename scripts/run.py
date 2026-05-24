# scripts/run.py
"""
Main daily pipeline.
Usage:
  python scripts/run.py            — live run (fetches prices, sends Discord, writes state)
  python scripts/run.py --dry-run  — read-only, verbose output, no writes, no Discord
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from bootstrap import bootstrap_if_needed
from discord_client import Alert, send_alerts
from scryfall import get_cheapest_prices
from state import (
    DEFAULT_ALERT_STATE_PATH,
    DEFAULT_PRICE_HISTORY_PATH,
    append_price,
    get_card_history,
    init_alert_state_for_card,
    load_alert_state,
    load_price_history,
    prune_history,
    save_alert_state,
    save_price_history,
)
from triggers import (
    apply_rearm,
    check_manual_target,
    check_near_52w_low,
    check_pct_drop,
    check_pct_off_52w_high,
)

WATCHLIST_PATH = Path("data/watchlist.yaml")
SETTINGS_PATH = Path("data/settings.yaml")


def load_config() -> tuple[list[dict], dict]:
    with open(WATCHLIST_PATH) as f:
        watchlist = yaml.safe_load(f)
    with open(SETTINGS_PATH) as f:
        settings = yaml.safe_load(f)
    return watchlist["cards"], settings


def _sort_key(alert: Alert) -> float:
    """Sort alerts by urgency descending (higher return = shown first in Discord)."""
    if alert.pct_change is not None:
        # near_52w_low: pct_change = % above the low; 0% above = most urgent → invert
        if alert.trigger_type == "near_52w_low":
            return -alert.pct_change
        return alert.pct_change
    if alert.trigger_type == "manual" and alert.target and alert.current_price:
        return (alert.target - alert.current_price) / alert.target * 100
    return 0.0


def run(dry_run: bool = False) -> int:
    today = date.today().isoformat()

    # ── Load config ───────────────────────────────────────────────────────────
    cards, settings = load_config()
    card_names = [c["name"] for c in cards]
    alert_cfg = settings["alerts"]
    rearm_cfg = settings["rearm"]
    discord_cfg = settings.get("discord", {})

    tag = "[DRY RUN]" if dry_run else "[INFO]"

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    try:
        bootstrap_if_needed(card_names)
    except Exception as e:
        print(f"[ERROR] Bootstrap failed: {e}")
        return 1

    print(f"{tag} Fetching prices for {len(cards)} cards...")

    # ── Fetch current prices from Scryfall ────────────────────────────────────
    current_prices: dict[str, dict] = {}
    for card in cards:
        name = card["name"]
        try:
            nf, ff = get_cheapest_prices(name)
            current_prices[name] = {"nonfoil": nf, "foil": ff}
        except Exception as e:
            print(f"[ERROR] Scryfall failure for '{name}': {e}")
            print("[ERROR] Aborting run — state not saved, alerts not sent.")
            return 1

    # ── Load state ────────────────────────────────────────────────────────────
    history = load_price_history()
    alert_state = load_alert_state()

    # ── Append today's prices to history ─────────────────────────────────────
    for card in cards:
        name = card["name"]
        prices = current_prices.get(name, {})
        for foil_type in ("nonfoil", "foil"):
            price = prices.get(foil_type)
            if price is not None:
                history = append_price(history, name, foil_type, today, price)
        init_alert_state_for_card(alert_state, name)

    history = prune_history(history, days=365)

    if dry_run:
        print(f"[DRY RUN] Loading price history (365 days bootstrapped)...")
        print(f"[DRY RUN] Running trigger checks...\n")

    # ── Evaluate triggers ─────────────────────────────────────────────────────
    fired_alerts: list[Alert] = []

    for card in cards:
        name = card["name"]
        prices = current_prices.get(name, {})
        decks = card.get("decks", {})

        for foil_type in ("nonfoil", "foil"):
            current_price = prices.get(foil_type)
            if current_price is None:
                continue

            card_history = get_card_history(history, name, foil_type)
            history_days = len(card_history)

            if dry_run:
                print(f"  {name} ({foil_type}, ${current_price:.2f})")

            for trigger_name in ("manual", "pct_drop", "pct_off_52w_high", "near_52w_low"):
                condition_met = False
                alert_kwargs: dict = {"history_days": history_days}
                skip_msg: Optional[str] = None

                # ── Evaluate condition ────────────────────────────────────────
                if trigger_name == "manual":
                    target = card.get(f"target_{foil_type}")
                    condition_met = check_manual_target(current_price, target)
                    alert_kwargs["target"] = target
                    if target is None:
                        skip_msg = "null"

                elif trigger_name == "pct_drop":
                    cfg = alert_cfg.get("pct_drop", {})
                    if not cfg.get("enabled", True):
                        skip_msg = "disabled"
                    else:
                        fired, details = check_pct_drop(
                            current_price,
                            card_history,
                            cfg["threshold_pct"],
                            cfg["lookback_days"],
                        )
                        condition_met = fired
                        if not fired:
                            skip_msg = details.get("skip_reason")
                        alert_kwargs.update({
                            k: details.get(k)
                            for k in ("actual_days", "comparison_price", "pct_change")
                        })

                elif trigger_name == "pct_off_52w_high":
                    cfg = alert_cfg.get("pct_off_52w_high", {})
                    if not cfg.get("enabled", True):
                        skip_msg = "disabled"
                    else:
                        fired, details = check_pct_off_52w_high(
                            current_price, card_history, cfg["threshold_pct"]
                        )
                        condition_met = fired
                        if not fired:
                            skip_msg = details.get("skip_reason")
                        alert_kwargs.update({k: details.get(k) for k in ("high_52w", "pct_change")})

                elif trigger_name == "near_52w_low":
                    cfg = alert_cfg.get("near_52w_low", {})
                    if not cfg.get("enabled", True):
                        skip_msg = "disabled"
                    else:
                        fired, details = check_near_52w_low(
                            current_price, card_history, cfg["threshold_pct"]
                        )
                        condition_met = fired
                        if not fired:
                            skip_msg = details.get("skip_reason")
                        alert_kwargs.update({k: details.get(k) for k in ("low_52w", "pct_change")})

                # ── Apply re-arm ──────────────────────────────────────────────
                last_price = alert_state[name][foil_type][trigger_name]
                should_fire, new_last_price = apply_rearm(
                    condition_met,
                    last_price,
                    current_price,
                    rearm_cfg["recovery_pct"],
                )

                # ── Dry-run output ────────────────────────────────────────────
                if dry_run:
                    if skip_msg:
                        print(f"    → {trigger_name}: {skip_msg} — SKIP")
                    elif condition_met:
                        fire_str = "WOULD FIRE" if should_fire else "SUPPRESS (re-arm)"
                        print(f"    → {trigger_name}: condition met — {fire_str}")
                        print(f"       last_alert_price: {last_price} → {fire_str}")
                    else:
                        print(f"    → {trigger_name}: NO TRIGGER")

                # ── Update state ──────────────────────────────────────────────
                alert_state[name][foil_type][trigger_name] = new_last_price

                if should_fire:
                    fired_alerts.append(Alert(
                        card_name=name,
                        foil_type=foil_type,
                        trigger_type=trigger_name,
                        current_price=current_price,
                        decks=decks,
                        **alert_kwargs,
                    ))

    fired_alerts.sort(key=_sort_key, reverse=True)

    # ── Dry-run summary ───────────────────────────────────────────────────────
    if dry_run:
        print(f"\n[DRY RUN] {len(fired_alerts)} alert(s) would fire today.")
        print("[DRY RUN] No writes made. No Discord messages sent.")
        return 0

    # ── Send Discord (live only) ──────────────────────────────────────────────
    if fired_alerts:
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            print("[ERROR] DISCORD_WEBHOOK_URL not set")
            return 1
        try:
            send_alerts(webhook_url, fired_alerts)
            print(f"[INFO] Sent {len(fired_alerts)} alert(s) to Discord")
        except Exception as e:
            print(f"[ERROR] Discord webhook failed: {e}")
            print("[ERROR] State NOT saved — alerts will re-fire on next run")
            return 1
    elif discord_cfg.get("quiet_if_nothing_triggered", True):
        print("[INFO] No alerts today. Discord suppressed (quiet_if_nothing_triggered=true)")

    # ── Save state (live only, only on success) ───────────────────────────────
    save_price_history(history)
    save_alert_state(alert_state)
    print(f"[INFO] State saved. {len(fired_alerts)} alert(s) fired.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="MTG Price Alert System")
    parser.add_argument("--dry-run", action="store_true", help="Read-only run, no writes, no Discord")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
