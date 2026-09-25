"""Loads the JSON rule files (cached). Keeping data out of code makes it easy to verify/edit."""
import json
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_rules(filename: str) -> dict:
    with open(RULES_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def load_entries() -> list[dict]:
    """Every rule entry (additives first, then plain ingredients)."""
    return load_rules("additives.json")["additives"] + load_rules("ingredients.json")["ingredients"]
