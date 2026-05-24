# scripts/discord_client.py
"""
Discord embed builder and webhook sender.
Builds one embed per alert; chunks into messages of max 10 embeds.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import requests

TRIGGER_COLORS = {
    "manual": 0x00FF00,
    "near_52w_low": 0x00FF00,
    "pct_drop": 0xFFAA00,
    "pct_off_52w_high": 0xFF4444,
}


@dataclass
class Alert:
    card_name: str
    foil_type: str           # "nonfoil" or "foil"
    trigger_type: str        # "manual" | "pct_drop" | "pct_off_52w_high" | "near_52w_low"
    current_price: float
    decks: dict              # {"Explorers": 2, "Ahoy": 2}
    history_days: Optional[int] = None
    comparison_price: Optional[float] = None  # pct_drop: price N days ago
    actual_days: Optional[int] = None          # pct_drop: actual days used
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    target: Optional[float] = None             # manual trigger target
    pct_change: Optional[float] = None


def _format_decks(decks: dict) -> str:
    return " | ".join(f"{deck} (T{tier})" for deck, tier in decks.items())


def build_embed(alert: Alert) -> dict:
    """Build a single Discord embed dict for one alert."""
    today_str = date.today().strftime("%Y-%m-%d")
    foil_label = "Foil" if alert.foil_type == "foil" else "Non-foil"

    # Trigger description
    if alert.trigger_type == "manual":
        desc = f"Dropped to ${alert.current_price:.2f} — at or below your target of ${alert.target:.2f}"
    elif alert.trigger_type == "pct_drop":
        desc = (
            f"Down {alert.pct_change:.1f}% in the last {alert.actual_days} days "
            f"(${alert.comparison_price:.2f} → ${alert.current_price:.2f})"
        )
    elif alert.trigger_type == "pct_off_52w_high":
        desc = f"{alert.pct_change:.1f}% below 52-week high of ${alert.high_52w:.2f}"
    else:  # near_52w_low
        desc = f"Within {alert.pct_change:.1f}% of 52-week low of ${alert.low_52w:.2f}"

    fields = [
        {"name": "Deck(s)", "value": _format_decks(alert.decks), "inline": True},
        {"name": "Type",    "value": foil_label,                  "inline": True},
        {"name": "Price",   "value": f"${alert.current_price:.2f}", "inline": True},
    ]

    if alert.trigger_type == "pct_off_52w_high" and alert.high_52w is not None:
        fields.append({"name": "52w High", "value": f"${alert.high_52w:.2f}", "inline": True})
    if alert.trigger_type == "near_52w_low" and alert.low_52w is not None:
        fields.append({"name": "52w Low", "value": f"${alert.low_52w:.2f}", "inline": True})
    if alert.trigger_type == "manual" and alert.target is not None:
        fields.append({"name": "Target", "value": f"${alert.target:.2f}", "inline": True})

    footer_text = f"MTG Price Alert • {today_str}"
    if (
        alert.history_days is not None
        and alert.history_days < 365
        and alert.trigger_type in ("pct_off_52w_high", "near_52w_low")
    ):
        footer_text += f"\n⚠️ 52-week data based on {alert.history_days} days of history"

    return {
        "title": alert.card_name,
        "description": desc,
        "color": TRIGGER_COLORS.get(alert.trigger_type, 0xAAAAAA),
        "fields": fields,
        "footer": {"text": footer_text},
    }


def send_alerts(webhook_url: str, alerts: list[Alert]) -> None:
    """
    Send alerts to Discord. Chunks into messages of max 10 embeds.
    Raises RuntimeError if any webhook POST fails.
    """
    if not alerts:
        return

    embeds = [build_embed(a) for a in alerts]
    for i in range(0, len(embeds), 10):
        chunk = embeds[i:i + 10]
        response = requests.post(webhook_url, json={"embeds": chunk}, timeout=30)
        if not response.ok:
            raise RuntimeError(
                f"Discord webhook failed (HTTP {response.status_code}): {response.text}"
            )


def send_test_message(webhook_url: str) -> None:
    """
    Layer 4 validation: send one test embed + a fabricated 15-alert batch.
    The 15-alert batch verifies chunking (should arrive as 2 Discord messages).
    """
    today_str = date.today().strftime("%Y-%m-%d")

    # Single test embed
    test_embed = {
        "title": "MTG Price Alert — Test",
        "description": "Webhook connection confirmed. Price alerts are working.",
        "color": 0x00FF00,
        "footer": {"text": f"MTG Price Alert • {today_str}"},
    }
    response = requests.post(webhook_url, json={"embeds": [test_embed]}, timeout=30)
    if not response.ok:
        raise RuntimeError(f"Discord webhook failed: {response.status_code} {response.text}")
    print("[PASS] Single test embed sent")

    # 15-alert chunk test
    fake_alerts = [
        Alert(
            card_name=f"Test Card {i + 1}",
            foil_type="nonfoil",
            trigger_type="pct_drop",
            current_price=round(50.00 - i * 0.50, 2),
            decks={"Explorers": 2},
            comparison_price=60.00,
            actual_days=30,
            pct_change=round((60.00 - (50.00 - i * 0.50)) / 60.00 * 100, 1),
            history_days=90,
        )
        for i in range(15)
    ]
    send_alerts(webhook_url, fake_alerts)
    print("[PASS] 15-alert chunk test sent (verify 2 Discord messages arrived)")
