"""Match parsed ingredients to the known ingredient/additive lists.

Order of attempts (first hit wins):
  1. INS number            -> exact entry (confidence 1.0); base-number fallback (0.85)
  2. exact alias           -> confidence 1.0
  3. fuzzy alias           -> rapidfuzz token_sort_ratio >= 88, confidence = score/100
  4. run-together fallback -> a long single token ("Refinedwheatflour") is split into known
                              words and matched again; accepted only if THAT matches (1-3).
                              The ingredient keeps the raw token in `original` and gets
                              `repaired=True`; `normalized` holds the matched name.
  5. nothing matched       -> known=False, confidence = best score seen (< 0.88)

`match_confidence` is passed on to the FSSAI engine (Phase 3), which downgrades
a PASS to REVIEW when the match is shaky.
"""
import re
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz, process

from app.config import BASE_INS_MATCH_CONFIDENCE
from app.pipeline.ingredient_parser import ParsedIngredient, parse_ingredients
from app.rules import load_rules
from app.schemas import Ingredient

# Bracketed words that only describe their parent ("Salt (iodised)"), not real ingredients.
DESCRIPTORS = {
    "iodised", "iodized", "refined", "edible", "natural", "organic", "fortified", "enriched",
    "dehydrated", "dried", "roasted", "powder", "powdered", "flakes", "raw", "fresh", "pure",
    "permitted", "food grade", "added", "synthetic", "artificial",
}
FUZZY_CUTOFF = 88
RUN_TOGETHER_MIN_LENGTH = 12  # shorter unknown tokens are not split (too many false splits)
MIN_FUZZY_LENGTH = 4  # very short strings ("oil") match too easily


def clean_name(text: str) -> str:
    """Lowercase, drop punctuation, collapse spaces: "Palm-Oil (refined)" -> "palm oil refined"."""
    text = re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("-", " "))
    return " ".join(text.split())


@dataclass
class _Index:
    by_ins: dict[str, dict]  # "501(i)" -> additive entry
    by_alias: dict[str, dict]  # cleaned alias -> entry (additives and plain ingredients)
    aliases: list[str]  # keys of by_alias, for fuzzy search


@lru_cache(maxsize=1)
def _index() -> _Index:
    by_ins: dict[str, dict] = {}
    by_alias: dict[str, dict] = {}
    for entry in load_rules("additives.json")["additives"]:
        by_ins[entry["ins"].lower()] = entry
        for alias in entry["aliases"]:
            by_alias.setdefault(clean_name(alias), entry)
    for entry in load_rules("ingredients.json")["ingredients"]:
        for alias in entry["aliases"]:
            by_alias.setdefault(clean_name(alias), entry)
    return _Index(by_ins, by_alias, list(by_alias))


# ---------------------------------------------------------------- run-together words
@lru_cache(maxsize=1)
def _vocabulary() -> frozenset[str]:
    """Every alphabetic word used by an ingredient/additive name or alias (lowercase)."""
    phrases = list(_index().aliases) + sorted(DESCRIPTORS)
    for fc in load_rules("additives.json")["functional_classes"]:
        phrases += [clean_name(a) for a in fc["aliases"]]
    return frozenset(w for phrase in phrases for w in phrase.split() if w.isalpha() and len(w) >= 2)


def segment_words(text: str, vocabulary: frozenset[str] | set[str]) -> list[str] | None:
    """Split letters-only `text` into words from `vocabulary`, or None if it can't be covered.

    Dynamic programming over prefixes; the cheapest split wins (one unit per word, short
    words of 1-2 letters cost 3), so "wheatflour" prefers wheat+flour over w+heat+f+lour.
    """
    n = len(text)
    max_word = max((len(w) for w in vocabulary), default=0)
    best: list[tuple[int, list[str]] | None] = [None] * (n + 1)
    best[0] = (0, [])
    for end in range(1, n + 1):
        for start in range(max(0, end - max_word), end):
            if best[start] is None:
                continue
            word = text[start:end]
            if word in vocabulary:
                cost = best[start][0] + (1 if len(word) >= 3 else 3)
                if best[end] is None or cost < best[end][0]:
                    best[end] = (cost, best[start][1] + [word])
    return best[n][1] if best[n] else None


def segment_run_together(token: str) -> str | None:
    """"Refinedwheatflour" -> "Refined Wheat Flour"; None unless it is a long, letters-only
    token that splits completely into at least two known words."""
    if len(token) < RUN_TOGETHER_MIN_LENGTH or not re.fullmatch(r"[A-Za-z]+", token):
        return None
    words = segment_words(token.lower(), _vocabulary())
    if not words or len(words) < 2:
        return None
    return " ".join(w.capitalize() for w in words)


def _lookup_ins(ins: str) -> tuple[dict | None, float]:
    idx = _index()
    key = ins.lower()
    if key in idx.by_ins:
        return idx.by_ins[key], 1.0
    base = re.match(r"\d+", key)  # "331(i)" -> try "331" (e.g. "sodium citrates")
    if base and base.group() in idx.by_ins:
        return idx.by_ins[base.group()], BASE_INS_MATCH_CONFIDENCE
    return None, 0.0


def _lookup_name(name: str) -> tuple[dict | None, float]:
    """Returns (entry, confidence). entry is None when below the fuzzy cutoff;
    confidence is then the best score seen, so callers can still show it."""
    idx = _index()
    cleaned = clean_name(name)
    if not cleaned:
        return None, 0.0
    if cleaned in idx.by_alias:
        return idx.by_alias[cleaned], 1.0
    if len(cleaned) < MIN_FUZZY_LENGTH:
        return None, 0.0
    best = process.extractOne(cleaned, idx.aliases, scorer=fuzz.token_sort_ratio)
    if best is None:
        return None, 0.0
    alias, score, _ = best
    if score >= FUZZY_CUTOFF:
        return idx.by_alias[alias], round(score / 100, 2)
    return None, round(score / 100, 2)


def _match(item: ParsedIngredient) -> tuple[dict | None, float, bool]:
    """Returns (entry, confidence, repaired). `repaired` is True only when the match was found
    after splitting a run-together token into words."""
    if item.ins_number:
        entry, conf = _lookup_ins(item.ins_number)
        if entry:
            return entry, conf, False
    entry, conf = _lookup_name(item.name)
    if entry:
        return entry, conf, False

    segmented = segment_run_together(item.name)
    if segmented:
        entry2, conf2 = _lookup_name(segmented)  # must pass the normal exact/fuzzy cutoff
        if entry2:
            return entry2, conf2, True
    return None, conf, False


def normalize_items(items: list[ParsedIngredient]) -> list[Ingredient]:
    """Match every parsed item and build the API `Ingredient` objects."""
    matches = [_match(item) for item in items]

    result: list[Ingredient] = []
    for i, (item, (entry, conf, repaired)) in enumerate(zip(items, matches)):
        if item.parent_index is not None and not item.ins_number and clean_name(item.name) in DESCRIPTORS:
            continue
        # "Refined wheat flour (Maida)": the bracket is a synonym, not a 2nd ingredient.
        if entry and item.parent_index is not None:
            parent_entry = matches[item.parent_index][0]
            if parent_entry is not None and parent_entry["id"] == entry["id"]:
                continue

        # A functional class ("Preservative") is a useful category even if the item is unknown.
        category = entry["category"] if entry else item.functional_class
        result.append(Ingredient(
            id=f"ing_{len(result) + 1}",
            original=item.original,
            normalized=entry["name"] if entry else None,
            category=category,
            ins_number=item.ins_number or (entry.get("ins") if entry else None),
            percentage=item.percentage,
            match_confidence=conf,
            known=entry is not None,
            repaired=repaired,
        ))
    return result


def extract_ingredients(text: str) -> list[Ingredient]:
    """Full text -> parsed -> normalised ingredient list."""
    return normalize_items(parse_ingredients(text))
