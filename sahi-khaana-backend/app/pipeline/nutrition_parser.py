"""Pull nutrient values out of nutrition-table text with regexes.

Missing nutrients stay None (never guessed). Units are converted so the
output is always: energy in kcal, sugar/fat/protein/fibre in g, sodium in mg.
"""
import re

from app.schemas import Nutrition

KJ_PER_KCAL = 4.184
SALT_TO_SODIUM = 400.0  # 1 g salt ~ 400 mg sodium (sodium = salt / 2.5)

# Longest labels first so "saturated fat" wins over plain "fat".
_LABELS = [
    ("energy_kcal", r"energy|calories|calorie"),
    ("sat_fat_g", r"saturated\s*fat(?:ty\s*acids)?|sat\.?\s*fat|saturates"),
    ("trans_fat_g", r"trans\s*fat(?:ty\s*acids)?|trans\s*fats"),
    ("total_fat_g", r"total\s*fat|fat"),
    ("ignore_added_sugar", r"added\s*sugars?"),  # skipped: not the same as total sugars
    ("sugar_g", r"total\s*sugars?|sugars?"),
    ("sodium_mg", r"sodium"),
    ("salt_g", r"salt"),
    ("protein_g", r"proteins?"),
    ("fiber_g", r"dietary\s*fib(?:er|re)|fib(?:er|re)"),
]
_LABEL_RE = "|".join(f"(?P<{key}>{pat})" for key, pat in _LABELS)
# OCR often drops spaces ("Energy452kcal", "Totalfat17.5g", "452kcalTotal fat"), so the label is
# bounded by letters rather than by a word boundary: it must not sit inside a longer word
# ("Salted", "Sugarcane", "Fatty"), but a digit may follow it, and it may directly follow a unit.
_LABEL_START = r"(?:(?<![a-z])|(?<=\dg)|(?<=\dmg)|(?<=\dmcg)|(?<=\dkj)|(?<=\dkcal))"
_LABEL_END = r"(?![a-z])"
# label, up to 20 non-digit chars (e.g. ":", "(kcal)", "of which"), value, optional unit.
# The value may contain OCR look-alikes (O, l) but must contain at least one real digit.
# Nothing is required after the unit, because the next label may follow it directly ("17.5gSaturated fat").
_ROW_RE = re.compile(
    rf"{_LABEL_START}(?:{_LABEL_RE}){_LABEL_END}(?P<mid>[^\d\n]{{0,20}}?)"
    r"(?P<val>(?=[\dOoIl.,]*\d)[\dOoIl]+(?:[.,][\dOoIl]+)?)\s*(?P<unit>kcal|kj|mg|mcg|µg|g)?",
    re.IGNORECASE,
)
# Allowed range per 100 g; larger numbers are almost certainly OCR errors ("17.5" -> "175").
_MAX_G = 100.0
_MAX_KCAL = 950.0
_MAX_SODIUM_MG = 40000.0


def _to_float(raw: str) -> float:
    fixed = "".join(_DIGIT_FIX.get(c, c) for c in raw).replace(",", ".")
    return float(fixed)


_DIGIT_FIX = {"O": "0", "o": "0", "l": "1", "I": "1"}


def _detect_basis(text: str) -> str | None:
    if re.search(r"100\s*(?:g|gm|gms|grams?)\b", text, re.IGNORECASE):
        return "per_100g"
    if re.search(r"100\s*ml\b", text, re.IGNORECASE):
        return "per_100ml"
    if re.search(r"per\s*(?:serve|serving|portion|pack)", text, re.IGNORECASE):
        return "per_serving"
    return None


def parse_nutrition(text: str | None) -> tuple[Nutrition, list[str]]:
    """Return (Nutrition, warnings). Empty/None text gives an all-None Nutrition."""
    if not text or not text.strip():
        return Nutrition(), []

    basis = _detect_basis(text)
    # Remove "per 100 g" style phrases so their numbers aren't read as nutrient values.
    cleaned = re.sub(r"(?:per|/)\s*100\s*(?:g|gm|gms|grams?|ml)\b|\(\s*100\s*(?:g|ml)\s*\)", " ", text, flags=re.IGNORECASE)

    found: dict[str, float] = {}
    warnings: list[str] = []
    for m in _ROW_RE.finditer(cleaned):
        key = next(k for k, _ in _LABELS if m.group(k) is not None)
        if key.startswith("ignore"):
            continue
        if cleaned[m.end("val"):].lstrip().startswith("%"):
            continue  # "Sugar (12%)" in an ingredient list is not a nutrient amount
        unit = (m.group("unit") or "").lower()
        if not unit:  # unit may be in the label: "Energy (kcal) 452"
            um = re.search(r"kcal|kj|mg|mcg|g", m.group("mid"), re.IGNORECASE)
            unit = um.group().lower() if um else ""
        if key in found or key == "salt_g" and "sodium_mg" in found:
            continue  # first occurrence wins (per-100g column comes before per-serving)
        try:
            value = _to_float(m.group("val"))
        except ValueError:
            continue

        # ---- unit conversion to the canonical unit
        if key == "energy_kcal":
            if unit == "kj":
                # "1890 kJ (452 kcal)": prefer the printed kcal figure over converting.
                kcal = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", cleaned[m.end(): m.end() + 30], re.IGNORECASE)
                value = _to_float(kcal.group(1)) if kcal else value / KJ_PER_KCAL
            elif unit != "kcal":
                continue  # a bare number after "Energy" could be kJ or kcal: don't guess
        elif key == "sodium_mg":
            value = value * 1000 if unit == "g" else value / 1000 if unit in ("mcg", "µg") else value
        elif key == "salt_g":
            value = value / 1000 if unit == "mg" else value
        else:  # grams
            value = value / 1000 if unit == "mg" else value

        # ---- plausibility (skipped for per-serving/unknown bases where sizes vary less strictly)
        limit = {"energy_kcal": _MAX_KCAL, "sodium_mg": _MAX_SODIUM_MG}.get(key, _MAX_G)
        if basis in ("per_100g", "per_100ml") and value > limit:
            warnings.append(f"IMPLAUSIBLE_NUTRIENT_IGNORED:{key}")
            continue
        found[key] = value

    # salt -> sodium only when sodium itself is not printed
    if "sodium_mg" not in found and "salt_g" in found:
        found["sodium_mg"] = found["salt_g"] * SALT_TO_SODIUM
    found.pop("salt_g", None)

    values = {k: round(v, 2) for k, v in found.items()}
    return Nutrition(basis=basis if values else None, **values), warnings
