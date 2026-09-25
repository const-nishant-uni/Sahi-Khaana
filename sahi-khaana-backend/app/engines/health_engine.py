"""Configurable health assessment. Thresholds and impacts live in rules/nutrition_rules.json.

Score = base (100) + sum of factor impacts, clamped to 0-100.
  * Nutrient factors use per-100 g (or per-100 ml) values. A per-serving table is not
    comparable to the thresholds, so it counts as "no usable nutrition".
  * Beverages (per 100 ml, or a beverage food category) use half of the FSA thresholds.
  * Only if there is NO usable nutrition do ingredient-based fallbacks apply, and then the
    assessment can never be better than MODERATE ("we know too little to say FEWER CONCERNS").
This is general information, not medical advice (see the disclaimer in the result).
"""
from app.rules import load_entries, load_rules
from app.schemas import HealthFactor, HealthResult, Ingredient, Nutrition

TOP_BAND = "FEWER CONCERNS"
CAPPED_BAND = "MODERATE"

_NUTRIENT_LABELS = {  # for the "detail" text
    "sugar_g": ("sugar", "g"), "sodium_mg": ("sodium", "mg"), "sat_fat_g": ("saturated fat", "g"),
    "trans_fat_g": ("trans fat", "g"), "total_fat_g": ("total fat", "g"), "energy_kcal": ("energy", "kcal"),
    "fiber_g": ("fibre", "g"), "protein_g": ("protein", "g"),
}


def _detail(nutrient: str, value: float, rule_detail: str) -> str:
    name, unit = _NUTRIENT_LABELS.get(nutrient, (nutrient, ""))
    return f"{rule_detail} (this product: {value:g} {unit} {name})."


class HealthEngine:
    def __init__(self, rules: dict | None = None, entries: list[dict] | None = None):
        """Pass your own `rules` / `entries` in tests; default is the JSON rule files."""
        self.rules = load_rules("nutrition_rules.json") if rules is None else rules
        entries = load_entries() if entries is None else entries
        self.id_by_name = {e["name"].lower(): e["id"] for e in entries}

    def assess(
        self, nutrition: Nutrition, ingredients: list[Ingredient], food_category: str | None = None
    ) -> tuple[HealthResult, list[str]]:
        """Returns (result, warnings). Warnings go into the top-level `warnings` of the response."""
        rules = self.rules
        warnings: list[str] = []
        factors: list[HealthFactor] = []

        has_values = any(v is not None for k, v in nutrition.model_dump().items() if k != "basis")
        if has_values and nutrition.basis == "per_serving":
            warnings.append("NUTRITION_PER_SERVING_ONLY")
        usable = nutrition.basis != "per_serving"

        scoring_keys = list(rules["nutrients"])
        present = [k for k in scoring_keys if usable and getattr(nutrition, k) is not None]
        halve = self._is_beverage(nutrition, food_category)

        if present:
            for key in scoring_keys:
                value = getattr(nutrition, key) if usable else None
                if value is None:
                    continue
                halved = halve and key in rules.get("beverage_halved", [])
                factor = rules.get("beverage_factor", 0.5) if halved else 1.0
                # Strictest matching tier only.
                for tier in sorted(rules["nutrients"][key], key=lambda t: t["gt"], reverse=True):
                    if value > tier["gt"] * factor:
                        factors.append(HealthFactor(
                            key=tier["key"], type="nutrient", impact=tier["impact"], label=tier["label"],
                            detail=_detail(key, value, tier["detail"]) + (" Beverage threshold applied." if factor != 1.0 else ""),
                        ))
                        break
            for key, rule in rules["positive_nutrients"].items():
                value = getattr(nutrition, key) if usable else None
                if value is not None and value >= rule["gte"]:
                    factors.append(HealthFactor(
                        key=rule["key"], type="nutrient", impact=rule["impact"], label=rule["label"],
                        detail=_detail(key, value, rule["detail"]),
                    ))
        else:
            factors.extend(self._ingredient_factors(ingredients))
            warnings.append("LIMITED_NUTRITION_DATA")

        score = round(max(0, min(100, rules["base_score"] + sum(f.impact for f in factors))))
        assessment = self._band(score)
        if not present and assessment == TOP_BAND:
            assessment = CAPPED_BAND  # too little data to claim "fewer concerns"

        known = sum(1 for i in ingredients if i.known)
        nutrient_part = len(present) / len(scoring_keys) if scoring_keys else 0.0
        ingredient_part = known / len(ingredients) if ingredients else 0.0
        result = HealthResult(
            score=score,
            assessment=assessment,
            data_completeness=self._completeness(present),
            completeness_score=round(0.7 * nutrient_part + 0.3 * ingredient_part, 2),
            factors=factors,
            disclaimer=rules["disclaimer"],
        )
        return result, warnings

    def _is_beverage(self, nutrition: Nutrition, food_category: str | None) -> bool:
        return nutrition.basis == "per_100ml" or food_category in self.rules.get("beverage_categories", [])

    def _completeness(self, present: list[str]) -> str:
        if not present:
            return "ingredients_only"
        required = self.rules.get("completeness", {}).get("full_requires", [])
        return "full" if all(k in present for k in required) else "partial"

    def _band(self, score: int) -> str:
        for band in sorted(self.rules["bands"], key=lambda b: b["min_score"], reverse=True):
            if score >= band["min_score"]:
                return band["assessment"]
        return self.rules["bands"][-1]["assessment"]

    def _ingredient_factors(self, ingredients: list[Ingredient]) -> list[HealthFactor]:
        """Coarse fallback when there is no nutrition table. Each rule applies once."""
        fallbacks = self.rules["ingredient_fallbacks"]
        by_category, by_id = fallbacks["by_category"], fallbacks["by_ingredient_id"]
        factors: list[HealthFactor] = []
        seen: set[str] = set()
        for ing in ingredients:
            if not ing.known:
                continue
            matches = []
            if ing.category in by_category:
                matches.append(by_category[ing.category])
            rule_id = self.id_by_name.get((ing.normalized or "").lower())
            if rule_id in by_id:
                matches.append(by_id[rule_id])
            for rule in matches:
                if rule["key"] in seen:
                    continue
                seen.add(rule["key"])
                factors.append(HealthFactor(
                    key=rule["key"], type="ingredient", impact=rule["impact"], label=rule["label"],
                    detail=f"Based on the ingredient list ({ing.normalized}); no usable nutrition table was available.",
                ))
        return factors


_default_engine: HealthEngine | None = None


def assess_health(
    nutrition: Nutrition, ingredients: list[Ingredient], food_category: str | None = None
) -> tuple[HealthResult, list[str]]:
    """Convenience wrapper using the JSON rule files (engine is built once)."""
    global _default_engine
    if _default_engine is None:
        _default_engine = HealthEngine()
    return _default_engine.assess(nutrition, ingredients, food_category)
