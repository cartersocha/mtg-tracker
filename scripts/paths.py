# scripts/paths.py
"""Central definitions of on-disk data artifact paths (relative to repo root)."""
from pathlib import Path

DATA_DIR = Path("data")
WATCHLIST_PATH = DATA_DIR / "watchlist.yaml"
SETTINGS_PATH = DATA_DIR / "settings.yaml"
SENTINEL_PATH = DATA_DIR / ".bootstrapped"
