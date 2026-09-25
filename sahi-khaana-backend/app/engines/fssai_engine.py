"""Deterministic FSSAI rule check. NO AI / LLM in here: same input, same output.

Per ingredient:
  * not recognised                         -> REVIEW
  * rule status NOT_PERMITTED              -> FLAG
  * rule status PERMITTED                  -> PASS
  * rule status CONDITIONAL                -> needs the food category:
        category missing                   -> REVIEW
        a condition covers the category    -> that condition's result (PASS / FLAG)
        no condition covers it             -> REVIEW
  * a PASS with a shaky match (confidence < settings.match_confidence_cutoff) -> REVIEW

Declaration rules (e.g. "contains permitted colour") give ONE label-level finding
(ingredient_id = null, always REVIEW, never FLAG) when the phrase is not found.
They do not change any ingredient's own finding or the per-ingredient summary counts.

Overall: any FLAG -> FLAG, else any REVIEW (ingredient or label-level) -> REVIEW, else PASS.
"""
import re

from rapidfuzz import fuzz

from app.config import get_settings
from app.rules import load_entries, load_rules
from app.schemas import Finding, FssaiResult, FssaiSummary, Ingredient

DECLARATION_MATCH_SCORE = 90  # fuzzy score for finding a required phrase in noisy OCR text

def _squash(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


class FssaiEngine:
    def __init__(self, entries: list[dict] | None = None, declarations: list[dict] | None = None):
        """Pass your own `entries` / `declarations` in tests; default is the JSON rule files."""
        entries = load_entries() if entries is None else entries
        self.by_name = {e["name"].lower(): e for e in entries}
        self.declarations = (
            load_rules("declarations.json")["declarations"] if declarations is None else declarations
        )

    # ------------------------------------------------------------ one ingredient
    def _check_ingredient(self, ing: Ingredient, food_category: str | None) -> tuple[str, str, str, str]:
        """Returns (status, rule_id, reason, source)."""
        if not ing.known or not ing.normalized:
            return ("REVIEW", "UNKNOWN_INGREDIENT",
                    "Ingredient not recognised; needs manual review.",
                    "No matching entry in the rule database")

        entry = self.by_name.get(ing.normalized.lower())
        if entry is None:
            return ("REVIEW", "NO_RULE", f"No rule found for '{ing.normalized}'.",
                    "No matching entry in the rule database")

        rule_id, source, name = entry["id"], entry["source"], entry["name"]
        rule_status = entry["status"]

        if rule_status == "NOT_PERMITTED":
            status, reason = "FLAG", f"{name} is not permitted."
        elif rule_status == "PERMITTED":
            status, reason = "PASS", f"{name} is permitted."
        else:  # CONDITIONAL
            status, reason = self._check_conditions(entry, food_category)

        if status == "PASS" and ing.match_confidence < get_settings().match_confidence_cutoff:
            status = "REVIEW"
            reason += f" Match confidence is only {ing.match_confidence:.2f}; please verify."
        return status, rule_id, reason, source

    @staticmethod
    def _check_conditions(entry: dict, food_category: str | None) -> tuple[str, str]:
        name = entry["name"]
        if not food_category:
            return "REVIEW", f"{name} depends on the food category; none was given."
        for cond in entry.get("conditions", []):
            categories = cond.get("food_categories", [])
            if food_category in categories or "*" in categories:
                result = cond["result"]
                note = cond.get("note", "")
                verb = "permitted" if result == "PASS" else "not permitted"
                return result, f"{name} is {verb} in this food category. {note}".strip()
        return "REVIEW", f"No verified rule for {name} in category '{food_category}'."

    # ------------------------------------------------------------ declarations
    def _declaration_present(self, decl: dict, label_text: str | None) -> bool:
        if not label_text:
            return False
        haystack = _squash(label_text)
        for phrase in decl["accepted_phrases"]:
            needle = _squash(phrase)
            if needle in haystack or fuzz.partial_ratio(needle, haystack) >= DECLARATION_MATCH_SCORE:
                return True
        return False

    # ------------------------------------------------------------ whole label
    def evaluate(
        self,
        ingredients: list[Ingredient],
        food_category: str | None,
        label_text: str | None = None,
        ocr_confidence: float = 1.0,
    ) -> FssaiResult:
        findings: list[Finding] = []
        per_ingredient: dict[str, str] = {}  # summary counts come from these only

        for ing in ingredients:
            status, rule_id, reason, source = self._check_ingredient(ing, food_category)
            findings.append(Finding(ingredient_id=ing.id, rule_id=rule_id, status=status, reason=reason, source=source))
            per_ingredient[ing.id] = status

        # Declaration rules: one label-level finding per rule whose phrase is missing.
        for decl in self.declarations:
            if not any(i.category == decl["applies_to_category"] for i in ingredients):
                continue
            if self._declaration_present(decl, label_text):
                continue
            findings.append(Finding(
                ingredient_id=None, rule_id=decl["id"], status="REVIEW",
                reason="Declaration not found in the scanned area", source=decl["source"],
            ))

        counts = {"PASS": 0, "FLAG": 0, "REVIEW": 0}
        for status in per_ingredient.values():
            counts[status] += 1
        scanned = len(ingredients)
        matched = sum(1 for i in ingredients if i.known)

        label_level = {f.status for f in findings if f.ingredient_id is None}
        if counts["FLAG"] or "FLAG" in label_level:
            overall = "FLAG"
        elif counts["REVIEW"] or label_level or scanned == 0:
            overall = "REVIEW"
        else:
            overall = "PASS"

        confidence = ocr_confidence * matched / scanned if scanned else 0.0
        return FssaiResult(
            overall_status=overall,
            summary=FssaiSummary(scanned=scanned, matched=matched, pass_=counts["PASS"],
                                 flag=counts["FLAG"], review=counts["REVIEW"]),
            confidence=round(max(0.0, min(1.0, confidence)), 4),
            findings=findings,
        )


_default_engine: FssaiEngine | None = None


def evaluate_fssai(
    ingredients: list[Ingredient], food_category: str | None,
    label_text: str | None = None, ocr_confidence: float = 1.0,
) -> FssaiResult:
    """Convenience wrapper using the JSON rule files (engine is built once)."""
    global _default_engine
    if _default_engine is None:
        _default_engine = FssaiEngine()
    return _default_engine.evaluate(ingredients, food_category, label_text, ocr_confidence)
