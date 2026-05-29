# scripts/import_manapool.py
"""
Parse a Manapool saved-list text file and compare against watchlist.yaml.
Does NOT modify watchlist.yaml — prints a comparison report.

Usage:
  python scripts/import_manapool.py manapool_list.txt

To use: paste your Manapool saved list into a plain text file, then run this script.

Handles:
  - Secret Lair alternate names: "Slash, Evil Turtle from Dimension X (Pirated Copy)"
  - DFC display names: "Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun"
  - Multiple printings of the same card (deduplicates, keeps lowest price)
  - Foil vs non-foil (tracks separately)
"""
import re
import sys
from pathlib import Path

import yaml

from paths import WATCHLIST_PATH

# Pattern: "Alternate Display Name (Canonical Card Name)"
CANONICAL_PAREN = re.compile(r'^.+\((.+)\)\s*$')
# Pattern: price line — "$XX.XX  Nx"
PRICE_LINE = re.compile(r'\$(\d+\.?\d*)\s+(\d+)x')


def parse_manapool_text(text: str) -> list[dict]:
    """
    Parse pasted Manapool saved-list text.
    Returns list of {name, price, foil, qty} dicts.

    Expected line groups (Manapool format):
      [Set name line] - [Set]
          [Card Name or Alternate (Canonical Name)]
      NM [Foil] [Printing type]
          $XX.XX   Nx
    """
    cards = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    i = 0

    while i < len(lines):
        line = lines[i]

        # A "set header" line contains " - " and links a printing to its set
        if " - " in line:
            # Card name is before the first " - "
            raw_name = line.split(" - ")[0].strip()
            i += 1

            # Next non-empty line might be canonical name (if different from display)
            if i < len(lines) and "$" not in lines[i] and not lines[i].startswith(("NM", "Foil")):
                raw_name = lines[i].strip()
                i += 1

            # Resolve canonical name from parenthetical
            m = CANONICAL_PAREN.match(raw_name)
            canonical = m.group(1).strip() if m else raw_name

            # Handle DFC names: "Front // Back" → use "Front"
            if " // " in canonical:
                canonical = canonical.split(" // ")[0].strip()

            # Parse condition/foil/price line
            foil = False
            price = None
            qty = 1

            if i < len(lines):
                cond_line = lines[i]
                if cond_line.startswith(("NM", "Foil", "LP", "MP")):
                    foil = "Foil" in cond_line
                    i += 1

                    # Price may be on same line or next line
                    pm = PRICE_LINE.search(cond_line)
                    if pm:
                        price = float(pm.group(1))
                        qty = int(pm.group(2))
                    elif i < len(lines):
                        pm = PRICE_LINE.search(lines[i])
                        if pm:
                            price = float(pm.group(1))
                            qty = int(pm.group(2))
                            i += 1

            if canonical:
                cards.append({"name": canonical, "price": price, "foil": foil, "qty": qty})
        else:
            i += 1

    return cards


def deduplicate(cards: list[dict]) -> dict[str, dict]:
    """
    Deduplicate by canonical name, keeping the lowest price per foil type.
    Returns {name: {nonfoil: float|None, foil: float|None}}.
    """
    result: dict[str, dict] = {}
    for card in cards:
        name = card["name"]
        if name not in result:
            result[name] = {"nonfoil": None, "foil": None}
        key = "foil" if card["foil"] else "nonfoil"
        price = card["price"]
        if price is not None:
            if result[name][key] is None or price < result[name][key]:
                result[name][key] = price
    return result


def compare_with_watchlist(deduped: dict[str, dict]) -> None:
    """Print a comparison of Manapool cards vs watchlist.yaml."""
    with open(WATCHLIST_PATH) as f:
        watchlist = yaml.safe_load(f)
    watchlist_names = {c["name"] for c in watchlist["cards"]}

    in_watchlist = []
    not_in_watchlist = []
    for name, prices in sorted(deduped.items()):
        (in_watchlist if name in watchlist_names else not_in_watchlist).append((name, prices))

    print(f"=== Manapool -> Watchlist Comparison ===\n")
    print(f"  In watchlist ({len(in_watchlist)} unique cards):")
    for name, prices in in_watchlist:
        nf = f"${prices['nonfoil']:.2f}" if prices["nonfoil"] else "-"
        ff = f"${prices['foil']:.2f}" if prices["foil"] else "-"
        print(f"   {name:<45} nonfoil: {nf:<10} foil: {ff}")

    if not_in_watchlist:
        print(f"\n  NOT in watchlist ({len(not_in_watchlist)} cards - consider adding):")
        for name, prices in not_in_watchlist:
            nf = f"${prices['nonfoil']:.2f}" if prices["nonfoil"] else "-"
            ff = f"${prices['foil']:.2f}" if prices["foil"] else "-"
            print(f"   {name:<45} nonfoil: {nf:<10} foil: {ff}")
    else:
        print("\n  All Manapool cards are already in watchlist.yaml")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_manapool.py <manapool_list.txt>")
        print("")
        print("Paste your Manapool saved list into a .txt file, then run this script.")
        print("It compares against data/watchlist.yaml and prints what to add/review.")
        sys.exit(1)

    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    cards = parse_manapool_text(text)
    deduped = deduplicate(cards)
    compare_with_watchlist(deduped)


if __name__ == "__main__":
    main()
