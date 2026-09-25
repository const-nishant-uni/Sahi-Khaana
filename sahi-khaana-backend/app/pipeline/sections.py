"""Find the "Ingredients" and "Nutrition" parts inside raw OCR text.

OCR mangles headings ("INGREDIENTS" -> "lNGREDlENTS", "NUTRITI0N"), so headings
are found with fuzzy word matching rather than an exact regex.
"""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

# Words that mean "the ingredient list has ended" (matched case-insensitively).
_STOP_RE = re.compile(
    r"\b("
    r"allergen|may\s+contain|manufactured|mfd|marketed|packed\s+by|packed\s+for|"
    r"best\s+before|use\s+by|expiry|storage|store\s+in|net\s+(?:wt|weight|quantity|qty|content)|"
    r"fssai|lic\.?\s*no|mrp|batch|customer\s+care|directions?\s+for|"
    r"contains\s+(?:milk|soy|soya|wheat|gluten|nuts?|peanuts?|eggs?|fish|allergens?)"
    r")\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z0-9|]{6,14}")


@dataclass
class Sections:
    ingredients_text: str | None  # None => no ingredients heading found
    nutrition_text: str | None  # None => no nutrition heading found
    rest_text: str = ""  # the whole text minus the ingredients block (nutrition fallback)


def _find_heading(text: str, target: str, min_ratio: int, start: int = 0) -> re.Match | None:
    """First word at/after `start` that looks like `target` (fuzzy)."""
    for m in _WORD_RE.finditer(text, start):
        if fuzz.ratio(m.group().lower().replace("|", "l"), target) >= min_ratio:
            return m
    return None


def _skip_separators(text: str, pos: int) -> int:
    """Move past ':' '-' spaces right after a heading."""
    while pos < len(text) and text[pos] in " \t:;-.":
        pos += 1
    return pos


def _join_lines(text: str) -> str:
    """Turn OCR line breaks into spaces; re-join words split with a hyphen."""
    text = re.sub(r"-\s*\n\s*(?=[a-z])", "", text)
    return re.sub(r"\s*\n\s*", " ", text).strip()


def extract_sections(raw_text: str) -> Sections:
    ing_head = _find_heading(raw_text, "ingredients", 80)
    nut_head = _find_heading(raw_text, "nutrition", 78)
    # "Nutritional Information": also accept the longer spelling.
    if nut_head is None:
        nut_head = _find_heading(raw_text, "nutritional", 80)

    ingredients_text = None
    rest_text = raw_text
    if ing_head:
        start = _skip_separators(raw_text, ing_head.end())
        end = len(raw_text)
        stop = _STOP_RE.search(raw_text, start)
        if stop:
            end = stop.start()
        if nut_head and nut_head.start() > ing_head.start():
            end = min(end, nut_head.start())
        ingredients_text = _join_lines(raw_text[start:end]).strip(" .;,:-") or None
        rest_text = raw_text[: ing_head.start()] + "\n" + raw_text[end:]

    nutrition_text = None
    if nut_head:
        end = len(raw_text)
        # Nutrition table printed BEFORE the ingredients: stop at the ingredients heading.
        if ing_head and ing_head.start() > nut_head.start():
            end = ing_head.start()
        nutrition_text = raw_text[nut_head.start():end]

    return Sections(ingredients_text, nutrition_text, rest_text)
