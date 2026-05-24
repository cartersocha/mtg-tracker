# scripts/scryfall.py
"""
Scryfall API client.
- Fetches cheapest nonfoil + foil price across all printings of a card.
- Handles pagination, rate limiting (150ms), 429 retry (5/15/30/60s backoff).
- Handles double-faced cards (DFCs).
"""
import time
from typing import Optional

import requests

BASE_URL = "https://api.scryfall.com"
RATE_LIMIT_SLEEP = 0.15  # 150ms between requests (~6-7 req/sec, safely under Scryfall's limit)


def _get(url: str, params: Optional[dict] = None) -> dict:
    """
    GET request with rate limiting and 429 retry backoff.
    Raises requests.HTTPError on non-retryable errors.
    """
    time.sleep(RATE_LIMIT_SLEEP)
    response = requests.get(url, params=params, timeout=30)

    if response.status_code == 429:
        for delay in (5, 15, 30, 60):
            print(f"[WARN] Scryfall 429 — retrying in {delay}s...")
            time.sleep(delay)
            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 429:
                break

    response.raise_for_status()
    return response.json()


def _extract_prices(card: dict) -> tuple[Optional[float], Optional[float]]:
    """
    Extract (nonfoil_price, foil_price) from a Scryfall card object.
    Falls back to card_faces[0] if top-level prices are both null (DFC handling).
    """
    prices = card.get("prices", {})

    # DFC fallback: if main prices object is empty, check card_faces[0]
    if prices.get("usd") is None and prices.get("usd_foil") is None:
        faces = card.get("card_faces", [])
        if faces:
            prices = faces[0].get("prices", prices)

    nf = float(prices["usd"]) if prices.get("usd") is not None else None
    ff = float(prices["usd_foil"]) if prices.get("usd_foil") is not None else None
    return nf, ff


def get_all_printings(card_name: str) -> list[dict]:
    """
    Fetch all printings of a card. Follows pagination until has_more is False.
    Returns list of Scryfall card objects.
    """
    url = f"{BASE_URL}/cards/search"
    params: Optional[dict] = {"q": f'!"{card_name}"', "unique": "prints"}
    results: list[dict] = []

    while url:
        data = _get(url, params=params)
        results.extend(data.get("data", []))
        url = data.get("next_page") if data.get("has_more") else None
        params = None  # next_page URL includes all params already

    return results


def get_cheapest_prices(card_name: str) -> tuple[Optional[float], Optional[float]]:
    """
    Returns (cheapest_nonfoil, cheapest_foil) across all printings of card_name.
    Either value is None if no printings carry that price type.
    Logs WARN for fuzzy name match; logs ERROR and returns (None, None) if not found.
    """
    # Resolve canonical name first (catches typos, DFC front-face check)
    try:
        _get(f"{BASE_URL}/cards/named", params={"exact": card_name})
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"[WARN] Exact name '{card_name}' not found, trying fuzzy...")
            try:
                _get(f"{BASE_URL}/cards/named", params={"fuzzy": card_name})
            except requests.HTTPError as e2:
                if e2.response.status_code == 404:
                    print(f"[ERROR] '{card_name}' not found on Scryfall (exact + fuzzy failed)")
                    return None, None
                raise
        elif e.response.status_code == 429:
            # Persistent 429 after all retries — skip gracefully rather than hard FAIL
            print(f"[WARN] Scryfall rate limit not recovered for '{card_name}' — skipping")
            return None, None
        else:
            raise

    # Fetch all printings and find cheapest prices
    try:
        printings = get_all_printings(card_name)
    except requests.HTTPError as e:
        print(f"[ERROR] Failed to fetch printings for '{card_name}': {e}")
        return None, None

    if not printings:
        print(f"[ERROR] No printings returned for '{card_name}'")
        return None, None

    nonfoil_prices: list[float] = []
    foil_prices: list[float] = []

    for card in printings:
        nf, ff = _extract_prices(card)
        if nf is not None:
            nonfoil_prices.append(nf)
        if ff is not None:
            foil_prices.append(ff)

    cheapest_nf = min(nonfoil_prices) if nonfoil_prices else None
    cheapest_ff = min(foil_prices) if foil_prices else None

    if cheapest_nf is None:
        print(f"[WARN] No non-foil prices found for '{card_name}'")

    return cheapest_nf, cheapest_ff
