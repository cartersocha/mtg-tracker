# scripts/mtgjson.py
"""
MTGJSON data client.
Pure parsing functions (find_uuids_for_card, extract_price_series,
compute_min_daily_price) are fully unit-testable.
Download functions (download_and_parse_gz, get_historical_prices_for_card)
require network access and are used only by bootstrap.py.
"""
import gzip
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import requests

ALLPRINTINGS_URL = "https://mtgjson.com/api/v5/AllPrintings.json.gz"
ALLPRICES_URL = "https://mtgjson.com/api/v5/AllPrices.json.gz"


# ── Pure parsing functions (unit-testable) ────────────────────────────────────

def find_uuids_for_card(card_name: str, all_printings: dict) -> list[str]:
    """
    Find all UUIDs matching card_name (case-insensitive) in AllPrintings data.
    Returns deduplicated list of UUID strings.
    """
    name_lower = card_name.lower()
    uuids: list[str] = []
    for set_code, set_data in all_printings.get("data", {}).items():
        for card in set_data.get("cards", []):
            if card.get("name", "").lower() == name_lower:
                uuid = card.get("uuid")
                if uuid and uuid not in uuids:
                    uuids.append(uuid)
    return uuids


def extract_price_series(uuid: str, price_type: str, all_prices: dict) -> dict[str, float]:
    """
    Extract TCGPlayer retail price series for a UUID.
    price_type: "normal" or "foil"
    Returns {date_str: price} dict. Empty dict if path not found.
    """
    try:
        return dict(
            all_prices["data"][uuid]["paper"]["tcgplayer"]["retail"][price_type]
        )
    except (KeyError, TypeError):
        return {}


def compute_min_daily_price(series_list: list[dict[str, float]]) -> dict[str, float]:
    """
    Given multiple {date: price} series, return the minimum price per date.
    """
    result: dict[str, float] = {}
    for series in series_list:
        for d, price in series.items():
            if d not in result or price < result[d]:
                result[d] = price
    return result


# ── Network functions (used by bootstrap.py) ─────────────────────────────────

def download_and_parse_gz(url: str) -> dict:
    """
    Download a .json.gz file, parse it, delete the temp file.
    Streams to disk to handle large files (AllPrices is ~1-2GB uncompressed).
    """
    print(f"[INFO] Downloading {url} ...")
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as tmp:
        tmp_path = tmp.name
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=65536):
            tmp.write(chunk)

    try:
        print(f"[INFO] Parsing {Path(url).name} ...")
        with gzip.open(tmp_path, "rt", encoding="utf-8") as f:
            return json.load(f)
    finally:
        os.unlink(tmp_path)
        print(f"[INFO] Temp file deleted.")


def get_historical_prices_for_card(
    card_name: str,
    all_printings: dict,
    all_prices: dict,
    days: int = 365,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Returns (nonfoil_history, foil_history) for card_name over the past `days` days.
    Uses TCGPlayer retail prices (cheapest across all printings per day).
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    uuids = find_uuids_for_card(card_name, all_printings)
    if not uuids:
        print(f"[WARN] No UUIDs found for '{card_name}' in MTGJSON AllPrintings")
        return {}, {}

    nonfoil_series: list[dict[str, float]] = []
    foil_series: list[dict[str, float]] = []

    for uuid in uuids:
        nf = extract_price_series(uuid, "normal", all_prices)
        ff = extract_price_series(uuid, "foil", all_prices)
        if nf:
            nonfoil_series.append({d: p for d, p in nf.items() if d >= cutoff})
        if ff:
            foil_series.append({d: p for d, p in ff.items() if d >= cutoff})

    return (
        compute_min_daily_price(nonfoil_series),
        compute_min_daily_price(foil_series),
    )
