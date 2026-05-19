"""Simple JSON-backed favorites store keyed by listing_id."""
from __future__ import annotations

import json
from pathlib import Path


def load_favorites(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_favorites(path: Path, favorites: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(favorites), indent=2), encoding="utf-8")
