# scripts/validate.py
"""
Integration validation script — Layers 2, 3, and 4.
Run from project root:
  python scripts/validate.py                    — Layer 2: Scryfall
  python scripts/validate.py --bootstrap-check  — Layer 3: MTGJSON
  python scripts/validate.py --discord          — Layer 4: Discord
"""
import argparse
import sys
from pathlib import Path

import yaml

WATCHLIST_PATH = Path("data/watchlist.yaml")


def validate_scryfall() -> int:
    """Layer 2: Hit Scryfall for every card and report results."""
    from scryfall import get_cheapest_prices, get_all_printings

    with open(WATCHLIST_PATH) as f:
        watchlist = yaml.safe_load(f)

    cards = watchlist["cards"]
    total = len(cards)
    passed = warnings = failed = 0

    print(f"Validating {total} cards against Scryfall...\n")

    for card in cards:
        name = card["name"]
        try:
            nf, ff = get_cheapest_prices(name)
            nf_str = f"${nf:.2f}" if nf is not None else "null"
            ff_str = f"${ff:.2f}" if ff is not None else "null"

            if nf is None and ff is None:
                print(f"[WARN] {name:<40} nonfoil: null   foil: null   (no prices found)")
                warnings += 1
            elif ff is None:
                print(f"[WARN] {name:<40} nonfoil: {nf_str:<10} foil: null   (no foil printing exists)")
                warnings += 1
            else:
                print(f"[PASS] {name:<40} nonfoil: {nf_str:<10} foil: {ff_str}")
                passed += 1
        except Exception as e:
            print(f"[FAIL] {name:<40} ERROR: {e}")
            failed += 1

    # Pagination test: Lightning Bolt has 60+ printings
    print("\n--- Pagination test: Lightning Bolt ---")
    try:
        printings = get_all_printings("Lightning Bolt")
        count = len(printings)
        status = "PASS" if count >= 60 else "WARN"
        print(f"[{status}] Found {count} printings ({'pagination working' if count >= 60 else 'expected 60+'})")
    except Exception as e:
        print(f"[FAIL] Pagination test: {e}")

    # DFC test
    print("\n--- DFC test: Brass's Tunnel-Grinder ---")
    try:
        nf, ff = get_cheapest_prices("Brass's Tunnel-Grinder")
        nf_str = f"${nf:.2f}" if nf else "null"
        ff_str = f"${ff:.2f}" if ff else "null"
        status = "PASS" if (nf is not None or ff is not None) else "FAIL"
        print(f"[{status}] Brass's Tunnel-Grinder   nonfoil: {nf_str}   foil: {ff_str}   (DFC — front face)")
    except Exception as e:
        print(f"[FAIL] DFC test: {e}")

    # Cheapest-across-printings spot check: Cavern of Souls
    print("\n--- Cheapest-across-printings spot check: Cavern of Souls ---")
    try:
        cheapest_nf, _ = get_cheapest_prices("Cavern of Souls")
        printings = get_all_printings("Cavern of Souls")
        first_prices = [
            float(p["prices"]["usd"])
            for p in printings
            if p.get("prices", {}).get("usd") is not None
        ]
        if first_prices and cheapest_nf and cheapest_nf < max(first_prices):
            print(f"[PASS] Cheapest ${cheapest_nf:.2f} < most expensive printing ${max(first_prices):.2f}")
        else:
            print(f"[WARN] Could not confirm cheapest-across-printings (cheapest={cheapest_nf})")
    except Exception as e:
        print(f"[FAIL] Spot check: {e}")

    print(f"\nSummary: {passed} passed, {warnings} warnings, {failed} failed")
    return 0 if failed == 0 else 1


def validate_bootstrap_check() -> int:
    """Layer 3: Download MTGJSON and verify UUID resolution for 5 spot-check cards."""
    from mtgjson import (
        download_and_parse_gz,
        find_uuids_for_card,
        get_historical_prices_for_card,
        ALLPRINTINGS_URL,
        ALLPRICES_URL,
    )

    SPOT_CHECK = ["Roaming Throne", "Cavern of Souls", "Cyclonic Rift", "Mana Crypt", "Smothering Tithe"]

    print("Checking MTGJSON reachability and parsing...\n")
    try:
        all_printings = download_and_parse_gz(ALLPRINTINGS_URL)
        all_prices = download_and_parse_gz(ALLPRICES_URL)
        print("[PASS] AllPrintings.json.gz downloaded and parsed")
        print("[PASS] AllPrices.json.gz downloaded and parsed\n")
    except Exception as e:
        print(f"[FAIL] MTGJSON download failed: {e}")
        return 1

    passed = failed = 0
    for name in SPOT_CHECK:
        uuids = find_uuids_for_card(name, all_printings)
        if not uuids:
            print(f"[FAIL] {name}: no UUIDs found")
            failed += 1
            continue

        nf, _ = get_historical_prices_for_card(name, all_printings, all_prices)
        if not nf:
            print(f"[WARN] {name}: {len(uuids)} UUIDs but no nonfoil history")
            continue

        high = max(nf.values())
        low = min(nf.values())
        days = len(nf)
        if high > low > 0 and days > 0:
            print(f"[PASS] {name}: {days} days, 52w low ${low:.2f}, 52w high ${high:.2f}")
            passed += 1
        else:
            print(f"[FAIL] {name}: implausible data (high={high:.2f}, low={low:.2f}, days={days})")
            failed += 1

    return 0 if failed == 0 else 1


def validate_discord() -> int:
    """Layer 4: Send test embed + 15-alert chunk test to Discord webhook."""
    import os
    from dotenv import load_dotenv
    from discord_client import send_test_message

    load_dotenv()
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[FAIL] DISCORD_WEBHOOK_URL not set in .env")
        return 1

    try:
        send_test_message(webhook_url)
        print("[PASS] Discord validation complete — check your Discord channel")
        return 0
    except Exception as e:
        print(f"[FAIL] Discord webhook failed: {e}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="MTG Price Alert — Validation")
    parser.add_argument("--bootstrap-check", action="store_true", help="Layer 3: MTGJSON spot-check")
    parser.add_argument("--discord", action="store_true", help="Layer 4: Discord webhook test")
    args = parser.parse_args()

    if args.bootstrap_check:
        sys.exit(validate_bootstrap_check())
    elif args.discord:
        sys.exit(validate_discord())
    else:
        sys.exit(validate_scryfall())


if __name__ == "__main__":
    main()
