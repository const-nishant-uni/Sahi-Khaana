"""Health engine tests, using a small made-up rule set (independent of the placeholder thresholds)."""
from app.engines.health_engine import HealthEngine
from app.rules import load_entries
from app.schemas import Ingredient, Nutrition

PH = "test"
RULES = {
    "base_score": 100,
    "nutrients": {
        "sugar_g": [
            {"key": "moderate_sugar", "label": "Moderate sugar", "gt": 5, "impact": -8, "detail": ">5 g", "source": PH},
            {"key": "high_sugar", "label": "High sugar", "gt": 15, "impact": -20, "detail": ">15 g", "source": PH},
        ],
        "sodium_mg": [{"key": "high_sodium", "label": "High sodium", "gt": 600, "impact": -20, "detail": ">600 mg", "source": PH}],
    },
    "positive_nutrients": {
        "protein_g": {"key": "good_protein", "label": "Protein", "gte": 10, "impact": 5, "detail": ">=10 g", "source": PH},
    },
    "ingredient_fallbacks": {
        "by_category": {"colour": {"key": "has_colour", "label": "Colour", "impact": -5, "source": PH}},
        "by_ingredient_id": {"palm_oil": {"key": "palm_oil", "label": "Palm oil", "impact": -5, "source": PH}},
    },
    "bands": [
        {"min_score": 70, "assessment": "FEWER CONCERNS"},
        {"min_score": 40, "assessment": "MODERATE"},
        {"min_score": 0, "assessment": "SEVERAL CONCERNS"},
    ],
    "disclaimer": "Not medical advice.",
}
ENTRIES = [{"id": "palm_oil", "name": "palm oil"}, {"id": "ins_102", "name": "tartrazine"}]
engine = HealthEngine(RULES, ENTRIES)


def ing(name, category=None, known=True):
    return Ingredient(id="ing_1", original=name, normalized=name if known else None, category=category,
                      match_confidence=1.0, known=known)


def nut(**kw):
    return Nutrition(basis=kw.pop("basis", "per_100g"), **kw)


def keys(result):
    return [f.key for f in result.factors]


# ------------------------------------------------------------------ scoring
def test_clean_product_scores_100():
    r = engine.assess(nut(sugar_g=1, sodium_mg=100), [ing("sugar")])
    assert r.score == 100 and r.assessment == "FEWER CONCERNS" and r.factors == []


def test_only_strictest_tier_applies():
    r = engine.assess(nut(sugar_g=20), [])
    assert keys(r) == ["high_sugar"] and r.score == 80


def test_moderate_tier():
    r = engine.assess(nut(sugar_g=10), [])
    assert keys(r) == ["moderate_sugar"] and r.score == 92


def test_threshold_is_strictly_greater_than():
    assert engine.assess(nut(sugar_g=5), []).factors == []
    assert keys(engine.assess(nut(sugar_g=5.1), [])) == ["moderate_sugar"]


def test_factors_add_up():
    r = engine.assess(nut(sugar_g=20, sodium_mg=1200), [])
    assert r.score == 60 and sorted(keys(r)) == ["high_sodium", "high_sugar"]


def test_positive_factor_raises_score_and_is_clamped_at_100():
    r = engine.assess(nut(protein_g=12, sugar_g=10), [])
    assert r.score == 97  # 100 - 8 + 5
    assert engine.assess(nut(protein_g=12, sugar_g=1), []).score == 100


def test_score_clamped_at_zero():
    rules = {**RULES, "base_score": 10}
    r = HealthEngine(rules, ENTRIES).assess(nut(sugar_g=20, sodium_mg=1200), [])
    assert r.score == 0


def test_factor_shape():
    (f,) = engine.assess(nut(sodium_mg=900), []).factors
    assert (f.key, f.type, f.impact, f.label) == ("high_sodium", "nutrient", -20, "High sodium")
    assert "900 mg" in f.detail


# ------------------------------------------------------------------ bands
def test_band_boundaries():
    def band(score):
        rules = {**RULES, "base_score": score}
        return HealthEngine(rules, ENTRIES).assess(nut(sugar_g=1), []).assessment
    assert band(100) == "FEWER CONCERNS" and band(70) == "FEWER CONCERNS"
    assert band(69) == "MODERATE" and band(40) == "MODERATE"
    assert band(39) == "SEVERAL CONCERNS" and band(0) == "SEVERAL CONCERNS"


# ------------------------------------------------------------------ ingredient fallbacks
def test_fallback_used_when_no_nutrition():
    r = engine.assess(Nutrition(), [ing("palm oil"), ing("tartrazine", "colour")])
    assert sorted(keys(r)) == ["has_colour", "palm_oil"] and r.score == 90
    assert all(f.type == "ingredient" for f in r.factors)


def test_fallback_applied_once_per_rule():
    r = engine.assess(Nutrition(), [ing("tartrazine", "colour"), ing("tartrazine", "colour")])
    assert keys(r) == ["has_colour"]


def test_fallback_not_used_when_nutrition_present():
    r = engine.assess(nut(sugar_g=1), [ing("palm oil"), ing("tartrazine", "colour")])
    assert r.factors == []


def test_unknown_ingredients_ignored_by_fallback():
    assert engine.assess(Nutrition(), [ing("palm oil", known=False)]).factors == []


def test_per_serving_table_is_not_scored():
    r = engine.assess(nut(basis="per_serving", sugar_g=50), [ing("palm oil")])
    assert keys(r) == ["palm_oil"]  # fell back to ingredients; sugar not compared to per-100g thresholds


def test_nutrition_without_scoring_fields_uses_fallback():
    r = engine.assess(nut(fiber_g=2), [ing("palm oil")])
    assert keys(r) == ["palm_oil"]


# ------------------------------------------------------------------ data completeness
def test_completeness_full_data():
    r = engine.assess(nut(sugar_g=1, sodium_mg=1), [ing("sugar")])
    assert r.data_completeness == 1.0


def test_completeness_partial_and_missing():
    assert engine.assess(nut(sugar_g=1), [ing("sugar")]).data_completeness == 0.65  # 0.7*0.5 + 0.3*1
    assert engine.assess(Nutrition(), [ing("sugar")]).data_completeness == 0.3
    assert engine.assess(Nutrition(), [ing("x", known=False)]).data_completeness == 0.0
    assert engine.assess(Nutrition(), []).data_completeness == 0.0


def test_disclaimer_included():
    assert engine.assess(Nutrition(), []).disclaimer == "Not medical advice."


# ------------------------------------------------------------------ the real rule file
def test_real_rules_work_end_to_end():
    r = HealthEngine().assess(nut(sugar_g=30, sodium_mg=1500, sat_fat_g=10, trans_fat_g=1, energy_kcal=500),
                              [ing("palm oil")])
    assert 0 <= r.score <= 100 and r.assessment == "SEVERAL CONCERNS" and r.disclaimer


def test_real_rules_reference_existing_entries():
    ids = {e["id"] for e in load_entries()}
    from app.rules import load_rules
    for rule_id in load_rules("nutrition_rules.json")["ingredient_fallbacks"]["by_ingredient_id"]:
        assert rule_id in ids
