"""Turn an ingredient-list string into structured items (syntax only).

No database lookups here: this module only understands *punctuation* and
*number formats*. Matching to known ingredients happens in normalizer.py.

Handles:
  * top-level comma/semicolon splitting that respects (), [], {}
  * percentages          "Wheat flour (72%)", "Sugar 12 %"
  * INS / E numbers      "INS 211", "E202", "(INS 501(i))", "160a(i)"
  * functional classes   "Emulsifier (322, 471)"  -> one item per number
  * OCR mistakes         "lNS 1O2" -> "INS 102", "501(l)" -> "501(i)"
"""
import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.rules import load_rules

_OPEN, _CLOSE = "([{", ")]}"


@dataclass
class ParsedIngredient:
    original: str  # text as printed (kept for display)
    name: str  # cleaned name without INS/percentage/brackets ("" if only an INS number)
    ins_number: str | None = None  # canonical, e.g. "211", "501(i)", "160a(i)"
    percentage: float | None = None
    functional_class: str | None = None  # e.g. "preservative" (from "Preservative (...)")
    parent_index: int | None = None  # index of the compound ingredient this came from


# ---------------------------------------------------------------- OCR fixes
_DIGITISH = {"O": "0", "o": "0", "l": "1", "I": "1"}


def fix_ocr(text: str) -> str:
    """Repair common OCR mistakes around INS numbers. Safe to run on any text."""
    # Full-width brackets/commas (e.g. "（", "，") -> plain ASCII.
    text = unicodedata.normalize("NFKC", text)

    # "lNS", "1NS", "|NS", "IN5" ... -> "INS" (only when a number/bracket follows)
    text = re.sub(r"(?i)\b[l1|i]n[s5]\b(?=\s*[-:.]?\s*[0-9oOlI(])", "INS", text)

    # Letters that are really digits, but only after an INS/E prefix:
    # "INS 1O2" -> "INS 102", "E2O2" -> "E202".
    def _digits(m: re.Match) -> str:
        token = m.group(3)
        # "E" is an ordinary letter, so demand at least 2 real digits before touching it.
        if m.group(1).upper() == "E" and sum(c.isdigit() for c in token) < 2:
            return m.group(0)
        return m.group(1) + m.group(2) + "".join(_DIGITISH.get(c, c) for c in token)

    text = re.sub(r"\b(INS|E)(\s*[-:.]?\s*)([0-9OolI]{3,4})(?![A-Za-z0-9])", _digits, text)

    # Roman-numeral suffix read as letters: "501(l)" -> "501(i)", "500(ll)" -> "500(ii)"
    text = re.sub(
        r"(?<=\d)\s*\(\s*([liI|]{1,3}|[iv]+)\s*\)",
        lambda m: "(" + re.sub(r"[lI|]", "i", m.group(1)) + ")",
        text,
    )
    return text


# ---------------------------------------------------------------- splitting
def split_top_level(text: str, separators: str = ",;") -> list[str]:
    """Split on separators that are NOT inside brackets.

    If brackets are unbalanced (OCR dropped one), fall back to a plain split so one
    missing ")" doesn't swallow the rest of the list into a single ingredient.
    """
    balanced = sum(text.count(c) for c in _OPEN) == sum(text.count(c) for c in _CLOSE)
    parts, depth, current = [], 0, []
    for ch in text:
        if balanced and ch in _OPEN:
            depth += 1
        elif balanced and ch in _CLOSE:
            depth = max(0, depth - 1)
        if ch in separators and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip(" .-")]


def _split_head_and_groups(item: str) -> tuple[str, list[str]]:
    """"Acidity regulator (INS 501(i)) (x)" -> ("Acidity regulator", ["INS 501(i)", "x"])."""
    head, groups, depth, current = [], [], 0, []
    for ch in item:
        if ch in _OPEN:
            if depth == 0:
                current = []
            else:
                current.append(ch)
            depth += 1
        elif ch in _CLOSE and depth > 0:
            depth -= 1
            if depth == 0:
                groups.append("".join(current).strip())
            else:
                current.append(ch)
        elif depth > 0:
            current.append(ch)
        else:
            head.append(ch)
    if depth > 0:  # unclosed bracket: keep what we have
        groups.append("".join(current).strip())
    return "".join(head).strip(" .-:"), groups


# ---------------------------------------------------------------- numbers
_PCT_RE = re.compile(r"(?:min\.?|max\.?|minimum|maximum)?\s*(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE)
# One INS number: optional INS/E prefix, 3-4 digits, optional letter, optional (roman)
_INS_PART_RE = re.compile(
    r"^\s*(?:(?:INS|E)\s*[-:.]?\s*)?(\d{3,4})\s*([a-z])?\s*(?:\(\s*([ivx]+)\s*\))?\s*$",
    re.IGNORECASE,
)
_INS_PREFIXED_RE = re.compile(
    r"\b(?:INS|E)\s*[-:.]?\s*(\d{3,4})\s*([a-z](?![a-z]))?\s*(?:\(\s*([ivx]+)\s*\))?",
    re.IGNORECASE,
)


def _canonical_ins(num: str, letter: str | None, roman: str | None) -> str:
    return num + (letter.lower() if letter else "") + (f"({roman.lower()})" if roman else "")


def extract_percentage(text: str) -> tuple[float | None, str]:
    """Return (first percentage found, text with it removed)."""
    m = _PCT_RE.search(text)
    if not m:
        return None, text
    value = float(m.group(1).replace(",", "."))
    return value, (text[: m.start()] + text[m.end():]).strip()


def _ins_from_part(part: str, allow_bare: bool) -> str | None:
    m = _INS_PART_RE.match(part)
    if not m:
        return None
    if not allow_bare and not re.match(r"\s*(INS|E)", part, re.IGNORECASE):
        return None
    return _canonical_ins(m.group(1), m.group(2), m.group(3))


def _split_ins_list(group: str) -> list[str] | None:
    """If `group` is only INS numbers ("INS 627, 631", "471 & 322"), return them, else None."""
    numbers = []
    for part in split_top_level(group):
        for sub in re.split(r"\s*(?:&|\band\b)\s*", part, flags=re.IGNORECASE):
            ins = _ins_from_part(sub, allow_bare=True)
            if ins is None:
                return None
            numbers.append(ins)
    return numbers or None


def find_ins_in_text(text: str) -> tuple[str | None, str]:
    """Find an *INS/E-prefixed* number inside free text; return (ins, text without it)."""
    m = _INS_PREFIXED_RE.search(text)
    if not m:
        return None, text
    ins = _canonical_ins(m.group(1), m.group(2), m.group(3))
    return ins, (text[: m.start()] + " " + text[m.end():]).strip(" ,.-:")


# ---------------------------------------------------------------- functional classes
def _class_aliases() -> list[tuple[str, str]]:
    return [
        (alias, fc["category"])
        for fc in load_rules("additives.json")["functional_classes"]
        for alias in fc["aliases"]
    ]


def match_functional_class(head: str) -> str | None:
    """"Acidity regulator" / "Permitted natural colours" -> category, else None."""
    cleaned = re.sub(r"[^a-z ]", " ", head.lower())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return None
    best_cat, best_score = None, 0.0
    for alias, category in _class_aliases():
        if cleaned == alias or cleaned.endswith(" " + alias):
            return category  # exact, or "...natural colours"
        score = fuzz.ratio(cleaned, alias)
        if score > best_score:
            best_cat, best_score = category, score
    return best_cat if best_score >= 88 else None  # tolerate OCR typos


# ---------------------------------------------------------------- main parsing
def _parse_item(item: str, out: list[ParsedIngredient], parent: int | None) -> None:
    item = item.strip(" .;:-")
    if not item:
        return

    pct, no_pct = extract_percentage(item)
    head, groups = _split_head_and_groups(no_pct)
    groups = [g for g in groups if g.strip(" .-")]  # "(72%)" left an empty group
    head_class = match_functional_class(head) if head else None

    # --- Case 1: "Emulsifier (322, 471)" / "Preservative (Sodium benzoate)"
    # One item per number/name inside the brackets, each remembering its class.
    if head_class and groups:
        for group in groups:
            ins_list = _split_ins_list(group)
            if ins_list:
                for n in ins_list:
                    out.append(ParsedIngredient(
                        original=f"{head} (INS {n})", name="", ins_number=n,
                        functional_class=head_class, parent_index=parent,
                    ))
                continue
            for sub in split_top_level(group):
                first = len(out)
                _parse_item(sub, out, parent)  # e.g. "Sodium benzoate", "INS 211 (sodium benzoate)"
                for parsed in out[first:]:
                    parsed.original = f"{head} ({parsed.original})"
                    parsed.functional_class = parsed.functional_class or head_class
        return

    # --- Case 2: ordinary ingredient, maybe with an INS number and/or sub-ingredients
    ins, name = find_ins_in_text(head)
    if not ins:  # "INS 211" can't be found in head; look for a bare INS-only head like "E202"
        ins_only = _ins_from_part(head, allow_bare=False)
        if ins_only:
            ins, name = ins_only, ""
    sub_groups: list[str] = []
    for group in groups:
        group_ins = _split_ins_list(group)
        if group_ins and len(group_ins) == 1 and ins is None:
            ins = group_ins[0]  # "Sodium benzoate (INS 211)"
        elif group_ins and ins is None:
            # several numbers after a plain name: one item per number
            for n in group_ins:
                out.append(ParsedIngredient(original=f"{head} (INS {n})", name=head, ins_number=n,
                                            functional_class=head_class, parent_index=parent))
            head = ""  # the head was fully expanded
        elif not group_ins:
            sub_groups.append(group)

    if not name and ins and sub_groups:  # "INS 211 (sodium benzoate)"
        name, sub_groups = sub_groups[0], sub_groups[1:]

    if head or ins:
        this_index = len(out)
        printed = item if not sub_groups else (head + (f" ({pct:g}%)" if pct is not None else ""))
        out.append(ParsedIngredient(
            original=printed, name=name or (head if not ins else ""), ins_number=ins,
            percentage=pct, functional_class=head_class, parent_index=parent,
        ))
    else:
        this_index = parent

    # Sub-ingredients of a compound ingredient, e.g. "Spices (chilli, turmeric)"
    for group in sub_groups:
        for sub in split_top_level(group):
            _parse_item(sub, out, this_index)


def parse_ingredients(text: str) -> list[ParsedIngredient]:
    """Split an ingredient list into structured items, in printed order."""
    text = fix_ocr(text)
    # OCR often reads a comma as a full stop: "Flour (72%).Palm oil" -> "Flour (72%), Palm oil".
    # Only when a lowercase letter/bracket/% comes right before and a capital right after,
    # so decimals ("3.4") and "min. 20%" are left alone.
    text = re.sub(r"(?<=[a-z)\]%])\.\s*(?=[A-Z])", ", ", text)
    out: list[ParsedIngredient] = []
    for item in split_top_level(text):
        _parse_item(item, out, None)
    return out
