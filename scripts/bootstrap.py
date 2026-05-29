# scripts/bootstrap.py
"""
One-time MTGJSON history seeding + incremental bootstrap for new cards.
The sentinel file data/.bootstrapped prevents re-downloading on subsequent runs.
"""
from pathlib import Path

from mtgjson import download_and_parse_gz, get_historical_prices_for_card, ALLPRINTINGS_URL, ALLPRICES_URL
from paths import SENTINEL_PATH
from state import load_price_history, save_price_history, DEFAULT_PRICE_HISTORY_PATH


def _bootstrap_cards(
    card_names: list[str],
    history_path: Path = DEFAULT_PRICE_HISTORY_PATH,
) -> None:
    """Download MTGJSON and seed price history for the given card names."""
    print("[INFO] Downloading MTGJSON data (this may take ~5 minutes on first run)...")
    all_printings = download_and_parse_gz(ALLPRINTINGS_URL)
    all_prices = download_and_parse_gz(ALLPRICES_URL)

    history = load_price_history(history_path)

    for name in card_names:
        nf, ff = get_historical_prices_for_card(name, all_printings, all_prices)
        if name not in history:
            history[name] = {"nonfoil": {}, "foil": {}}
        history[name]["nonfoil"].update(nf)
        history[name]["foil"].update(ff)

        if not nf and not ff:
            print(f"[WARN] '{name}': no MTGJSON price history found — will build from Scryfall going forward")
        else:
            print(f"[INFO] '{name}': seeded {len(nf)} nonfoil days, {len(ff)} foil days")

    save_price_history(history, history_path)


def bootstrap_if_needed(
    watchlist_cards: list[str],
    history_path: Path = DEFAULT_PRICE_HISTORY_PATH,
) -> None:
    """
    Full bootstrap on first run (no sentinel); incremental for missing cards thereafter.
    Writes sentinel after full bootstrap completes.
    """
    history = load_price_history(history_path)

    if not SENTINEL_PATH.exists():
        print(f"[INFO] First run — bootstrapping all {len(watchlist_cards)} cards from MTGJSON...")
        _bootstrap_cards(watchlist_cards, history_path)
        SENTINEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        SENTINEL_PATH.touch()
        print("[INFO] Bootstrap complete. Sentinel written to data/.bootstrapped")
    else:
        missing = [c for c in watchlist_cards if c not in history]
        if missing:
            print(f"[INFO] Incremental bootstrap for {len(missing)} new card(s): {missing}")
            _bootstrap_cards(missing, history_path)
        else:
            print(f"[INFO] All {len(watchlist_cards)} cards present in price history. Bootstrap skipped.")
