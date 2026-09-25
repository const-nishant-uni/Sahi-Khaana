"""Health engine tests. Most use a small made-up rule set (independent of the real thresholds);
the last section checks the real nutrition_rules.json."""
import pytest
from pydantic import ValidationError

from app.engines.health_engine import HealthEngine
from app.pipeline.nutrition_parser import parse_nutrition
from app.rules import load_entries, load_rules
from app.schemas import HealthResult, Ingredient, Nutrition

PH = "test"
RULES = {
    "base_score": 100,
    "beverage_categories": ["beverages_non_alcoholic"],
    "beverage_factor": 0.5,
    "beverage_halved": ["sugar_g"],
    "completeness": {"full_requires": ["sugar_g", "sodium_mg"]},
    "nutrients": {
        "sugar_g": [
            {"key": "moderate_sugar", "label": "Moderate sugar", "gt": 5, "impact": -8, "detail": ">5 g", "source": PH},
            {"key": "high_sugar", "label": "High sugar", "gt": 15, "impact": -20, "detail": ">15 g", "source": PH},
        ],
        "sodium_mg": [{"key": "high_sodium", "label": "High sodium", "gt": 600, "impact": -20, "detail": ">600 mg", "source": PH}],
        "energy_kcal": [{"key": "high_energy", "label": "High energy", "gt": 400, "impact": -8, "detail": ">400 kcal", "source": PH}],
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


def assess(nutrition, ingredients=(), category=None, rules=RULES):
    return HealthEngine(rules, ENTRIES).assess(nutrition, list(ingredients), category)


def result_of(nutrition, ingredients=(), category=None):
    return assess(nutrition, ingredients, category)[0]


def keys(result):
    return [f.key for f in result.factors]


# ------------------------------------------------------------------ scoring
def test_clean_product_scores_100_and_is_not_capped():
    r, warnings = assess(nut(sugar_g=1, sodium_mg=100), [ing("sugar")])
    assert r.score == 100 and r.assessment == "FEWER CONCERNS" and r.factors == [] and warnings == []


def test_only_strictest_tier_applies():
    r = result_of(nut(sugar_g=20))
    assert keys(r) == ["high_sugar"] and r.score == 80


def test_threshold_is_strictly_greater_than():
    assert result_of(nut(sugar_g=5)).factors == []
    assert keys(result_of(nut(sugar_g=5.1))) == ["moderate_sugar"]


def test_factors_add_up():
    r = result_of(nut(sugar_g=20, sodium_mg=1200))
    assert r.score == 60 and sorted(keys(r)) == ["high_sodium", "high_sugar"]


def test_positive_factor_raises_score_and_is_clamped_at_100():
    assert result_of(nut(protein_g=12, sugar_g=10)).score == 97  # 100 - 8 + 5
    assert result_of(nut(protein_g=12, sugar_g=1)).score == 100


def test_score_clamped_at_zero():
    r = assess(nut(sugar_g=20, sodium_mg=1200), rules={**RULES, "base_score": 10})[0]
    assert r.score == 0


def test_factor_shape():
    (f,) = result_of(nut(sodium_mg=900)).factors
    assert (f.key, f.type, f.impact, f.label) == ("high_sodium", "nutrient", -20, "High sodium")
    assert "900 mg" in f.detail


def test_band_boundaries():
    def band(score):
        return assess(nut(sugar_g=1), rules={**RULES, "base_score": score})[0].assessment
    assert band(100) == "FEWER CONCERNS" and band(70) == "FEWER CONCERNS"
    assert band(69) == "MODERATE" and band(40) == "MODERATE"
    assert band(39) == "SEVERAL CONCERNS" and band(0) == "SEVERAL CONCERNS"


# ------------------------------------------------------------------ 1. no usable data caps the band + warning
def test_no_nutrition_caps_band_at_moderate_but_keeps_score():
    r, warnings = assess(Nutrition(), [ing("sugar")])
    assert r.score == 100  # the score is still computed...
    assert r.assessment == "MODERATE"  # ...but can't claim FEWER CONCERNS
    assert warnings == ["LIMITED_NUTRITION_DATA"]


def test_cap_only_lowers_the_top_band():
    r, warnings = assess(Nutrition(), [ing("palm oil")], rules={**RULES, "base_score": 30})
    assert r.assessment == "SEVERAL CONCERNS" and "LIMITED_NUTRITION_DATA" in warnings  # unchanged, not raised
    r, _ = assess(Nutrition(), [ing("palm oil")], rules={**RULES, "base_score": 60})
    assert r.assessment == "MODERATE"


def test_nutrition_without_scoring_fields_is_capped():
    r, warnings = assess(nut(fiber_g=2), [ing("palm oil")])
    assert r.assessment == "MODERATE" and "LIMITED_NUTRITION_DATA" in warnings


def test_per_serving_only_is_capped_too():
    r, warnings = assess(nut(basis="per_serving", sugar_g=1, sodium_mg=10))
    assert r.assessment == "MODERATE" and "LIMITED_NUTRITION_DATA" in warnings


def test_partial_nutrition_is_not_capped_and_has_no_warning():
    r, warnings = assess(nut(sugar_g=1))
    assert r.assessment == "FEWER CONCERNS" and warnings == []


def test_unspecified_basis_is_treated_as_usable():
    r, warnings = assess(Nutrition(basis=None, sugar_g=1))
    assert warnings == [] and r.data_completeness == "partial"


# ------------------------------------------------------------------ 3. per-serving warning
def test_per_serving_only_warns():
    _, warnings = assess(nut(basis="per_serving", sugar_g=50), [ing("palm oil")])
    assert "NUTRITION_PER_SERVING_ONLY" in warnings


def test_per_serving_values_are_not_scored():
    r, _ = assess(nut(basis="per_serving", sugar_g=50), [ing("palm oil")])
    assert keys(r) == ["palm_oil"]  # fell back to ingredients; 50 g was not compared to per-100 g thresholds


def test_no_per_serving_warning_for_per_100g_or_empty():
    assert "NUTRITION_PER_SERVING_ONLY" not in assess(nut(sugar_g=1))[1]
    assert "NUTRITION_PER_SERVING_ONLY" not in assess(Nutrition())[1]  # nothing was found at all


def test_per_serving_parsed_end_to_end():
    n, _ = parse_nutrition("Nutrition facts per serving (30 g): Energy 120 kcal, Total sugars 5 g")
    assert n.basis == "per_serving"
    assert "NUTRITION_PER_SERVING_ONLY" in assess(n)[1]


# ------------------------------------------------------------------ ingredient fallbacks
def test_fallback_used_when_no_nutrition():
    r = result_of(Nutrition(), [ing("palm oil"), ing("tartrazine", "colour")])
    assert sorted(keys(r)) == ["has_colour", "palm_oil"] and r.score == 90
    assert all(f.type == "ingredient" for f in r.factors)


def test_fallback_applied_once_per_rule():
    assert keys(result_of(Nutrition(), [ing("tartrazine", "colour"), ing("tartrazine", "colour")])) == ["has_colour"]


def test_fallback_not_used_when_nutrition_present():
    assert result_of(nut(sugar_g=1), [ing("palm oil"), ing("tartrazine", "colour")]).factors == []


def test_unknown_ingredients_ignored_by_fallback():
    assert result_of(Nutrition(), [ing("palm oil", known=False)]).factors == []


# ------------------------------------------------------------------ 2. data_completeness enum + completeness_score
def test_completeness_full():
    r = result_of(nut(sugar_g=1, sodium_mg=1, energy_kcal=10), [ing("sugar")])
    assert r.data_completeness == "full" and r.completeness_score == 1.0


def test_completeness_partial():
    r = result_of(nut(sugar_g=1), [ing("sugar")])
    assert r.data_completeness == "partial"
    assert r.completeness_score == 0.53  # 0.7 * 1/3 + 0.3 * 1


def test_completeness_ingredients_only():
    r = result_of(Nutrition(), [ing("sugar")])
    assert r.data_completeness == "ingredients_only" and r.completeness_score == 0.3
    assert result_of(Nutrition(), [ing("x", known=False)]).completeness_score == 0.0
    assert result_of(Nutrition(), []).completeness_score == 0.0


def test_completeness_per_serving_is_ingredients_only():
    assert result_of(nut(basis="per_serving", sugar_g=1, sodium_mg=1)).data_completeness == "ingredients_only"


def test_completeness_is_a_string_enum_not_a_float():
    r = result_of(nut(sugar_g=1))
    assert isinstance(r.data_completeness, str) and isinstance(r.completeness_score, float)
    dumped = r.model_dump()
    assert dumped["data_completeness"] in ("full", "partial", "ingredients_only")
    assert 0 <= dumped["completeness_score"] <= 1
    with pytest.raises(ValidationError):
        HealthResult(score=50, assessment="MODERATE", data_completeness=0.9, completeness_score=0.9,
                     factors=[], disclaimer="x")


def test_disclaimer_included():
    assert result_of(Nutrition()).disclaimer == "Not medical advice."


# ------------------------------------------------------------------ beverages use half thresholds
def test_beverage_category_halves_listed_nutrients():
    assert result_of(nut(sugar_g=8), category=None).factors[0].key == "moderate_sugar"  # food: 8 is only > 5
    # beverage: high threshold 15 -> 7.5, so 8 g is "high"
    assert keys(result_of(nut(sugar_g=8), category="beverages_non_alcoholic")) == ["high_sugar"]


def test_per_100ml_basis_is_treated_as_beverage():
    assert keys(result_of(nut(basis="per_100ml", sugar_g=8))) == ["high_sugar"]


def test_beverage_halving_only_applies_to_listed_nutrients():
    assert result_of(nut(energy_kcal=250), category="beverages_non_alcoholic").factors == []  # 250 < 400, not halved


def test_beverage_detail_mentions_it():
    (f,) = result_of(nut(sugar_g=8), category="beverages_non_alcoholic").factors
    assert "Beverage threshold" in f.detail


# ------------------------------------------------------------------ 6. the real rule file: UK FSA per-100 g "high" thresholds
REAL = HealthEngine()


def real(nutrition, category=None):
    return REAL.assess(nutrition, [], category)[0]


@pytest.mark.parametrize("field,at_threshold,above,key", [
    ("sugar_g", 22.5, 22.6, "high_sugar"),
    ("total_fat_g", 17.5, 17.6, "high_total_fat"),
    ("sat_fat_g", 5, 5.1, "high_sat_fat"),
    ("sodium_mg", 600, 601, "high_sodium"),
])
def test_fsa_high_thresholds(field, at_threshold, above, key):
    assert key not in keys(real(nut(**{field: at_threshold})))  # "more than", so equal is not high
    assert key in keys(real(nut(**{field: above})))


def test_salt_1_5_g_is_the_sodium_threshold():
    n, _ = parse_nutrition("per 100 g: Salt 1.5 g")
    assert n.sodium_mg == 600 and "high_sodium" not in keys(real(n))
    n, _ = parse_nutrition("per 100 g: Salt 1.6 g")
    assert "high_sodium" in keys(real(n))


def test_real_beverage_thresholds_are_half():
    bev = "beverages_non_alcoholic"
    assert "high_sugar" in keys(real(nut(sugar_g=11.3), bev)) and "high_sugar" not in keys(real(nut(sugar_g=11.2), bev))
    assert "high_sugar" not in keys(real(nut(sugar_g=11.3)))  # food category: 22.5 applies
    assert "high_sodium" in keys(real(nut(basis="per_100ml", sodium_mg=301)))
    assert "high_total_fat" in keys(real(nut(total_fat_g=9), bev)) and "high_sat_fat" in keys(real(nut(sat_fat_g=2.6), bev))


# ---- medium tier: FSA "low" cut-offs, -5 points, no double counting with the high tier
MEDIUM = [  # field, low cut-off, high cut-off, medium key, high key
    ("sugar_g", 5, 22.5, "medium_sugar", "high_sugar"),
    ("total_fat_g", 3, 17.5, "medium_total_fat", "high_total_fat"),
    ("sat_fat_g", 1.5, 5, "medium_sat_fat", "high_sat_fat"),
    ("sodium_mg", 120, 600, "medium_sodium", "high_sodium"),
]


@pytest.mark.parametrize("field,low,high,medium_key,high_key", MEDIUM)
def test_medium_tier_boundaries(field, low, high, medium_key, high_key):
    assert real(nut(**{field: low})).factors == []  # "more than": equal to the low cut-off is still low
    r = real(nut(**{field: low + 0.1 if low < 10 else low + 1}))
    assert keys(r) == [medium_key] and r.score == 95  # -5
    assert keys(real(nut(**{field: high}))) == [medium_key]  # equal to the high cut-off is still medium
    assert keys(real(nut(**{field: high + 1}))) == [high_key]  # above high: high penalty ONLY


@pytest.mark.parametrize("field,low,high,medium_key,high_key", MEDIUM)
def test_no_double_counting_between_medium_and_high(field, low, high, medium_key, high_key):
    r = real(nut(**{field: high * 2}))
    assert medium_key not in keys(r) and keys(r).count(high_key) == 1


def test_medium_penalty_is_5_and_high_penalties_are_unchanged():
    tiers = {t["key"]: t for ts in load_rules("nutrition_rules.json")["nutrients"].values() for t in ts}
    for key in ("medium_sugar", "medium_total_fat", "medium_sat_fat", "medium_sodium"):
        assert tiers[key]["impact"] == -5
    assert [tiers[k]["impact"] for k in ("high_sugar", "high_total_fat", "high_sat_fat", "high_sodium")] == [-20, -10, -15, -20]


def test_medium_penalties_add_up_across_nutrients():
    r = real(nut(sugar_g=10, total_fat_g=5, sat_fat_g=2, sodium_mg=200))
    assert sorted(keys(r)) == ["medium_sat_fat", "medium_sodium", "medium_sugar", "medium_total_fat"] and r.score == 80


def test_salt_0_3_g_is_the_medium_sodium_threshold():
    n, _ = parse_nutrition("per 100 g: Salt 0.3 g")
    assert n.sodium_mg == 120 and real(n).factors == []
    n, _ = parse_nutrition("per 100 g: Salt 0.4 g")
    assert keys(real(n)) == ["medium_sodium"]


def test_beverages_use_half_of_the_medium_thresholds_too():
    bev = "beverages_non_alcoholic"
    assert keys(real(nut(sugar_g=2.6), bev)) == ["medium_sugar"] and real(nut(sugar_g=2.5), bev).factors == []
    assert keys(real(nut(total_fat_g=1.6), bev)) == ["medium_total_fat"]
    assert keys(real(nut(sat_fat_g=0.8), bev)) == ["medium_sat_fat"]
    assert keys(real(nut(basis="per_100ml", sodium_mg=61))) == ["medium_sodium"]
    assert real(nut(sugar_g=2.6)).factors == []  # a food with 2.6 g sugar is still "low"
    assert keys(real(nut(sugar_g=11.3), bev)) == ["high_sugar"]  # bev high = 11.25: high only, no medium


def test_every_threshold_has_a_source():
    rules = load_rules("nutrition_rules.json")
    for nutrient, tiers in rules["nutrients"].items():
        for tier in tiers:
            assert tier["source"], f"{nutrient}/{tier['key']} has no source"
    for rule in rules["positive_nutrients"].values():
        assert rule["source"]


def test_fsa_sources_and_project_heuristics_are_labelled():
    tiers = {t["key"]: t for ts in load_rules("nutrition_rules.json")["nutrients"].values() for t in ts}
    for key in ("high_sugar", "high_total_fat", "high_sat_fat", "high_sodium"):
        assert "UK FSA" in tiers[key]["source"] and "'high'" in tiers[key]["source"]
    for key in ("medium_sugar", "medium_total_fat", "medium_sat_fat", "medium_sodium"):
        assert "UK FSA" in tiers[key]["source"] and "'low'" in tiers[key]["source"]
    assert tiers["high_energy"]["source"] == "project heuristic"
    assert tiers["trans_fat_present"]["source"] == "project heuristic"


def test_real_rules_work_end_to_end():
    r, warnings = REAL.assess(nut(sugar_g=30, sodium_mg=1500, sat_fat_g=10, total_fat_g=20, trans_fat_g=1, energy_kcal=500),
                              [ing("palm oil")], None)
    assert r.assessment == "SEVERAL CONCERNS" and r.data_completeness == "full" and warnings == []
    assert 0 <= r.score <= 100 and r.disclaimer


def test_real_rules_reference_existing_entries():
    ids = {e["id"] for e in load_entries()}
    for rule_id in load_rules("nutrition_rules.json")["ingredient_fallbacks"]["by_ingredient_id"]:
        assert rule_id in ids
