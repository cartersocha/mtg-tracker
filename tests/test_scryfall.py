# tests/test_scryfall.py
"""Unit tests for scryfall printing-matching (no network)."""
import pytest

import scryfall
from scryfall import _printing_matches, get_cheapest_prices


@pytest.fixture
def stub_printings(monkeypatch):
    """Stub out Scryfall network calls so get_cheapest_prices runs offline."""
    def _stub(printings):
        monkeypatch.setattr(scryfall, "_get", lambda *a, **k: {})
        monkeypatch.setattr(scryfall, "get_all_printings", lambda name: printings)
    return _stub


def test_standalone_card_matches():
    card = {"name": "Reanimate"}
    assert _printing_matches(card, "Reanimate") is True


def test_back_face_dfc_excluded():
    # Secrets of Strixhaven: "Reanimate" is the BACK face — different product.
    card = {
        "name": "Grave Researcher // Reanimate",
        "card_faces": [{"name": "Grave Researcher"}, {"name": "Reanimate"}],
    }
    assert _printing_matches(card, "Reanimate") is False


def test_demonic_tutor_back_face_excluded():
    card = {
        "name": "Emeritus of Woe // Demonic Tutor",
        "card_faces": [{"name": "Emeritus of Woe"}, {"name": "Demonic Tutor"}],
    }
    assert _printing_matches(card, "Demonic Tutor") is False


def test_front_face_dfc_included():
    # Watchlist tracks front-face name; this is the legit card we want.
    card = {
        "name": "Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun",
        "card_faces": [
            {"name": "Growing Rites of Itlimoc"},
            {"name": "Itlimoc, Cradle of the Sun"},
        ],
    }
    assert _printing_matches(card, "Growing Rites of Itlimoc") is True


def test_split_card_front_included():
    card = {
        "name": "Fire // Ice",
        "card_faces": [{"name": "Fire"}, {"name": "Ice"}],
    }
    assert _printing_matches(card, "Fire") is True
    # Ice is the back face → excluded
    assert _printing_matches(card, "Ice") is False


def test_unrelated_card_excluded():
    card = {"name": "Counterspell"}
    assert _printing_matches(card, "Reanimate") is False


def test_get_cheapest_prices_excludes_back_face_dfc(stub_printings):
    """A cheaper back-face DFC must NOT pull down the cheapest price."""
    stub_printings([
        {"name": "Reanimate", "prices": {"usd": "7.46", "usd_foil": "13.34"}},
        {  # Secrets of Strixhaven DFC — Reanimate is the BACK face
            "name": "Grave Researcher // Reanimate",
            "prices": {"usd": "3.16", "usd_foil": "4.32"},
            "card_faces": [
                {"name": "Grave Researcher", "prices": {"usd": "3.16"}},
                {"name": "Reanimate", "prices": {}},
            ],
        },
    ])
    nf, ff = get_cheapest_prices("Reanimate")
    assert nf == 7.46  # NOT 3.16 — the DFC was excluded
    assert ff == 13.34  # NOT 4.32


def test_get_cheapest_prices_front_face_dfc_included(stub_printings):
    """Front-face DFC tracking still resolves (Growing Rites of Itlimoc)."""
    stub_printings([
        {
            "name": "Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun",
            "prices": {"usd": "7.80", "usd_foil": "7.82"},
            "card_faces": [
                {"name": "Growing Rites of Itlimoc"},
                {"name": "Itlimoc, Cradle of the Sun"},
            ],
        }
    ])
    nf, ff = get_cheapest_prices("Growing Rites of Itlimoc")
    assert nf == 7.80
    assert ff == 7.82
