"""Shared loader for references/log_symptom_routes.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTES_FILE = ROOT / "references" / "log_symptom_routes.json"


@lru_cache(maxsize=1)
def load_symptom_routes() -> tuple[dict, ...]:
    """Load immutable route records once for every local tool process."""
    try:
        data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    symptoms = data.get("symptoms", [])
    return tuple(item for item in symptoms if isinstance(item, dict) and item.get("id"))
