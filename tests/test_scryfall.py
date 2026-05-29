# tests/test_scryfall.py
"""Unit tests for scryfall printing-matching (no network)."""
from scryfall import _printing_matches


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
