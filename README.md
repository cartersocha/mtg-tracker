# MTG Price Alert System

Daily Discord notifications when tracked Magic: The Gathering cards hit deal thresholds.
Runs on GitHub Actions; sends Discord embeds when prices drop significantly.

## How It Works

1. **Bootstrap (first run only, ~5 min):** Downloads 365 days of price history from MTGJSON.
2. **Daily run:** Fetches current prices from Scryfall (cheapest NM across all printings), evaluates four alert triggers, sends Discord embeds for any hits.
3. **State is committed back to git** after each run so history accumulates over time.

### Alert Triggers

| Trigger | Fires when | Min history |
|---|---|---|
| Manual target | `price ≤ target_nonfoil` / `target_foil` in watchlist.yaml | None |
| % drop | ≥ 15% drop vs 30 days ago | 7 days |
| % off 52w high | ≥ 25% below 52-week high | 30 days |
| Near 52w low | Within 10% of 52-week low | 30 days |

**Re-arm:** After an alert fires, it suppresses until price drops further OR recovers 10%+ above the alert price (then resets to fire fresh on the next decline).

**Note on first 30 days:** The bootstrap uses TCGPlayer retail prices (MTGJSON); daily runs use TCGPlayer market prices (Scryfall). These differ slightly. The 52w triggers require 30 days minimum, so they're inactive during this window. After 30 days, all data is consistent Scryfall market data.

---

## Setup

```bash
git clone <your-repo-url>
cd mtg-price-alerts
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your Discord webhook URL
```

---

## Adding Cards to the Watchlist

Edit `data/watchlist.yaml`. Add an entry under the appropriate deck section:

```yaml
- name: "Card Name"        # Must match Scryfall's exact card name
  decks:
    Explorers: 2           # Deck code and tier (1-4)
  target_nonfoil: null     # Set to a dollar amount for manual alert, e.g. 35.00
  target_foil: null
```

Deck codes: `Explorers`, `Ahoy`, `Rohan`. Tiers: 1 (~$50 upgrade), 2 (~$125), 3 (~$200), 4 (no-budget).

Double-faced cards (DFCs): use the **front face name** (e.g., `"Brass's Tunnel-Grinder"`, not `"Tecutlan, the Searing Rift"`).

---

## Setting Manual Price Targets

In `data/watchlist.yaml`, set `target_nonfoil` or `target_foil` to the price at which you want to be alerted:

```yaml
- name: "Cavern of Souls"
  target_nonfoil: 40.00    # Alert when any printing hits $40 or below
  target_foil: null
```

---

## Adjusting Global Thresholds

Edit `data/settings.yaml`:

```yaml
alerts:
  pct_drop:
    threshold_pct: 15    # Alert on 15%+ drop in 30 days
    lookback_days: 30
  pct_off_52w_high:
    threshold_pct: 25    # Alert when 25%+ below 52-week high
  near_52w_low:
    threshold_pct: 10    # Alert when within 10% of 52-week low
rearm:
  recovery_pct: 10       # Reset alert when price recovers 10%+ above last alert price
```

---

## Running Local Tests

See `LOCAL_TESTING.md` for the full 5-layer test plan. Quick summary:

```bash
# Layer 1 — Unit tests (no network required)
pytest tests/ -v

# Layer 2 — Scryfall API validation (~2 min)
python scripts/validate.py

# Layer 3 — MTGJSON bootstrap spot-check (~5 min, downloads ~500MB)
python scripts/validate.py --bootstrap-check

# Layer 4 — Discord webhook test (requires .env with DISCORD_WEBHOOK_URL)
python scripts/validate.py --discord

# Layer 5 — Full dry run (no writes, no Discord)
python scripts/run.py --dry-run
```

---

## Importing Your Manapool Saved List

To check your Manapool saved list against the watchlist:

```bash
# Paste your Manapool saved list into a text file, then:
python scripts/import_manapool.py my_manapool_list.txt
```

Prints which cards are already tracked and which need to be added.

---

## Deploying to GitHub Actions

1. Push this repo to GitHub.
2. Go to **Settings → Secrets and variables → Actions**.
3. Add a secret named `DISCORD_WEBHOOK_URL` with your webhook URL.
4. Go to **Actions → Daily MTG Price Check → Run workflow** to trigger the first run manually.
5. Verify Discord alerts arrived and state files (`data/price_history.json`, `data/alert_state.json`) were committed back.
6. The cron schedule takes over from there (14:00 UTC daily).

**First run:** Takes ~5 minutes while MTGJSON bootstraps 365 days of price history. Subsequent runs are fast (~2 minutes).

**Concurrent runs:** If two runs overlap (very unlikely with daily cron), the last one to push wins. State from the earlier run may be overwritten. This is acceptable for a daily price tracker.

---

## Project Structure

```
data/watchlist.yaml       — Cards to track (edit this to add/remove cards)
data/settings.yaml        — Global trigger thresholds (edit to tune sensitivity)
data/price_history.json   — 365-day price history (auto-updated daily, committed to git)
data/alert_state.json     — Last-alert prices per card/trigger (auto-updated, committed)
scripts/run.py            — Main pipeline
scripts/validate.py       — Integration tests (Layers 2-4)
LOCAL_TESTING.md          — Full 5-layer testing guide
```
