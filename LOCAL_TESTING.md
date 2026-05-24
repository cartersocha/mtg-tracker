# Local Testing Plan

Run these tests in order before setting up GitHub Actions.
Each layer is independent — unit tests need no internet or credentials.

---

## Prerequisites

```bash
pip install requests pyyaml pytest
cp .env.example .env          # fill in DISCORD_WEBHOOK_URL
```

---

## Layer 1 — Unit Tests (no network, no credentials)

```bash
pytest tests/ -v
```

Tests all trigger logic against mock price data. Every case must pass before
moving on. Covers:

**Manual target trigger**
- [ ] Fires when `current_price <= target`
- [ ] Does NOT fire when `current_price > target`
- [ ] Handles `target = null` (no alert, no crash)

**% drop in N days trigger**
- [ ] Fires when drop >= threshold_pct within lookback_days
- [ ] Does NOT fire when drop < threshold_pct
- [ ] Does NOT fire when price has risen over lookback window
- [ ] Handles fewer than lookback_days of history (skip gracefully, log warning)

**% off 52-week high trigger**
- [ ] Fires when `(high - current) / high >= threshold_pct`
- [ ] Does NOT fire when drop is below threshold
- [ ] Uses correct 52-week window (365 days back from today, not all-time)
- [ ] Handles fewer than 365 days of history (skip gracefully, log warning)

**Near 52-week low trigger**
- [ ] Fires when `(current - low) / low <= threshold_pct`
- [ ] Does NOT fire when price is well above 52-week low
- [ ] Handles fewer than 365 days of history (skip gracefully, log warning)

**Re-arm logic**
- [ ] Alert does NOT re-fire when current price == last_alert_price
- [ ] Alert does NOT re-fire when current price > last_alert_price
- [ ] Alert DOES re-fire when current price < last_alert_price
- [ ] Alert RESETS when price rises >= recovery_pct above last_alert_price
- [ ] After reset: alert fires fresh on next qualifying drop

**Null price handling**
- [ ] No crash when nonfoil price is null
- [ ] No crash when foil price is null
- [ ] No crash when BOTH are null (card not listed on TCGPlayer)
- [ ] No false alert fired for null prices

**Edge cases**
- [ ] Card with zero days of history: all 52-week triggers skip, manual still works
- [ ] Single day of history: pct_drop skips (no 30-day window), others skip
- [ ] Price history has gaps (missing dates): handled without crash

---

## Layer 2 — API Validation (requires network)

```bash
python scripts/validate.py
```

Hits Scryfall for every card in watchlist.yaml and prints a result table.
No writes to any state files. Output format:

```
Validating 71 cards against Scryfall...

[PASS] Roaming Throne           nonfoil: $45.83   foil: $89.00
[PASS] Cyclonic Rift            nonfoil: $33.24   foil: $52.11
[PASS] Brass's Tunnel-Grinder   nonfoil: $2.17    foil: $3.50   (DFC — front face)
[WARN] Tropical Island          nonfoil: $287.00  foil: null    (no foil printing exists)
[WARN] Titan of Littjara        nonfoil: $1.80    foil: null    (dropped below $2 threshold)
[FAIL] Some Typo'd Card         ERROR: not found on Scryfall

Summary: 68 passed, 2 warnings, 1 failed
```

Checks:
- [ ] All 71 cards resolve by name (exact match, then fuzzy fallback with warning)
- [ ] Each resolved card returns at least one non-null price (foil OR nonfoil)
- [ ] DFC cards return price data correctly (Brass's Tunnel-Grinder)
- [ ] Cards with many printings paginate correctly (test: Lightning Bolt, not on
      watchlist, but run as an explicit pagination test)
- [ ] Cheapest-across-printings logic returns lower price than first-printing-found
      for at least one multi-printing card (spot check: Cavern of Souls)
- [ ] Scryfall rate limiting respected (no 429 errors across 71 requests)

---

## Layer 3 — MTGJSON Bootstrap Validation (requires network, ~5 min)

```bash
python scripts/validate.py --bootstrap-check
```

Downloads a sample of MTGJSON data and validates the UUID mapping for a
subset of watchlist cards (not all 71 — just verify the approach works).

Checks:
- [ ] AllPrices.json.gz is reachable and parseable
- [ ] UUID mapping resolves for at least 5 spot-check cards
- [ ] Historical price data present for past 365 days for those cards
- [ ] "Cheapest across all printings per day" logic produces a valid time series
- [ ] Resulting 52-week high and low are plausible (high > low, both > $0)

---

## Layer 4 — Discord Webhook Test (requires DISCORD_WEBHOOK_URL)

```bash
python scripts/validate.py --discord
```

Sends one test embed to your Discord channel. Verify it arrives and looks correct.

Checks:
- [ ] Webhook URL accepts the POST request (200 response)
- [ ] Embed renders with card name, deck, tier, prices, trigger type
- [ ] Multi-alert chunking works: sends a fabricated batch of 15 alerts and
      confirms they arrive as multiple messages (Discord 2000-char limit)

---

## Layer 5 — Dry Run (requires network + credentials)

```bash
python scripts/run.py --dry-run
```

Runs the full pipeline end-to-end using real API data but makes NO writes
and sends NO Discord messages. Prints what would have happened:

```
[DRY RUN] Fetching prices for 71 cards...
[DRY RUN] Loading price history (365 days bootstrapped)...
[DRY RUN] Running trigger checks...

  Roaming Throne (nonfoil, $45.83)
    → manual target: null — SKIP
    → pct_drop (30d): was $45.83, now $45.83, drop 0.0% — NO TRIGGER
    → pct_off_52w_high: high $55.00, now $45.83, off 16.7% — NO TRIGGER (threshold 25%)
    → near_52w_low: low $44.00, now $45.83, above low by 4.2% — WOULD TRIGGER
       last_alert_price: null → WOULD FIRE

[DRY RUN] 1 alert(s) would fire today.
[DRY RUN] No writes made. No Discord messages sent.
```

This is the final gate before GitHub Actions. If the dry run output looks
correct, the live deployment should behave identically.

---

## Only After All 5 Layers Pass

Set up GitHub Actions:
1. Create repo on GitHub
2. Add `DISCORD_WEBHOOK_URL` as a repository secret
3. Push all files
4. Manually trigger the workflow once (`workflow_dispatch`) and verify Discord alert
5. Confirm the state files were committed back correctly
6. Let the cron schedule take over
