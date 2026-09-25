"""Unit tests for Phase 2: sections, ingredient parser, nutrition parser, normalizer, /analyze."""
import pytest

from app.config import BASE_INS_MATCH_CONFIDENCE
from app.pipeline.ingredient_parser import fix_ocr, parse_ingredients, split_top_level
from app.pipeline.normalizer import _vocabulary, extract_ingredients, segment_run_together, segment_words
from app.pipeline.nutrition_parser import parse_nutrition
from app.pipeline.sections import extract_sections
from tests.conftest import headers


# ------------------------------------------------------------------ splitting
def test_split_respects_brackets():
    text = "Wheat flour, Flavour enhancer (INS 627, INS 631), Salt; Sugar"
    assert split_top_level(text) == ["Wheat flour", "Flavour enhancer (INS 627, INS 631)", "Salt", "Sugar"]


def test_split_nested_brackets():
    assert split_top_level("Acidity regulator (INS 501(i), 500(ii)), Salt") == [
        "Acidity regulator (INS 501(i), 500(ii))", "Salt"]


def test_split_unbalanced_brackets_does_not_swallow_the_list():
    parts = split_top_level("Wheat flour (72%, Sugar, Salt")
    assert "Sugar" in parts and "Salt" in parts


# ------------------------------------------------------------------ percentages
@pytest.mark.parametrize("text,pct", [
    ("Wheat flour (72%)", 72.0),
    ("Sugar 12 %", 12.0),
    ("Milk solids (min. 20.5%)", 20.5),
    ("Cocoa (3,5%)", 3.5),
])
def test_percentage(text, pct):
    (item,) = parse_ingredients(text)
    assert item.percentage == pct


def test_no_percentage():
    assert parse_ingredients("Salt")[0].percentage is None


# ------------------------------------------------------------------ INS numbers
def test_ins_in_functional_class_bracket():
    items = parse_ingredients("Flavour enhancer (INS 627, INS 631)")
    assert [i.ins_number for i in items] == ["627", "631"]
    assert all(i.functional_class == "flavour_enhancer" for i in items)


def test_bare_numbers_in_class_bracket():
    items = parse_ingredients("Emulsifier (322, 471)")
    assert [i.ins_number for i in items] == ["322", "471"]


def test_ampersand_and_e_prefix():
    assert [i.ins_number for i in parse_ingredients("Preservative (E211 & E202)")] == ["211", "202"]


def test_roman_numeral_suffix():
    assert parse_ingredients("Acidity regulator (INS 501(i))")[0].ins_number == "501(i)"


def test_letter_suffix():
    assert parse_ingredients("Colour (INS 160a(i))")[0].ins_number == "160a(i)"


def test_name_with_ins_in_brackets():
    (item,) = parse_ingredients("Sodium benzoate (INS 211)")
    assert item.name == "Sodium benzoate" and item.ins_number == "211"


def test_ins_with_name_in_brackets():
    (item,) = parse_ingredients("INS 330 (citric acid)")
    assert item.ins_number == "330" and item.name == "citric acid"


def test_sub_ingredients_of_compound():
    items = parse_ingredients("Spices (chilli, turmeric)")
    assert [i.name for i in items] == ["Spices", "chilli", "turmeric"]
    assert items[1].parent_index == 0


# ------------------------------------------------------------------ OCR fixes
def test_ocr_ins_prefix():
    assert fix_ocr("Colour (lNS 102)") == "Colour (INS 102)"


def test_ocr_letter_o_in_number():
    assert fix_ocr("INS 1O2") == "INS 102"
    assert fix_ocr("E2O2") == "E202"


def test_ocr_roman_suffix():
    assert fix_ocr("INS 501(l)") == "INS 501(i)"


def test_ocr_fix_does_not_touch_normal_words():
    text = "Oil, Edible oil, Eggs, Sugar"
    assert fix_ocr(text) == text


def test_ocr_mangled_list_parses():
    items = parse_ingredients("Acidity regulator (lNS 5O1(l)), Colour (lNS 1O2)")
    assert [i.ins_number for i in items] == ["501(i)", "102"]


def test_ocr_fullwidth_brackets():
    assert fix_ocr("Colour （INS 102）") == "Colour (INS 102)"


def test_full_stop_read_as_comma():
    names = [i.name for i in parse_ingredients("Refined wheat flour (72%).Palm oil. Salt")]
    assert names == ["Refined wheat flour", "Palm oil", "Salt"]


def test_full_stop_rule_leaves_decimals_alone():
    (item,) = parse_ingredients("Milk solids (min. 20.5%)")
    assert item.percentage == 20.5


# ------------------------------------------------------------------ normalizer
def test_normalize_by_ins():
    (ing,) = extract_ingredients("Preservative (INS 211)")
    assert ing.normalized == "sodium benzoate" and ing.known and ing.match_confidence == 1.0
    assert ing.category == "preservative" and ing.ins_number == "211"


def test_normalize_exact_alias():
    (ing,) = extract_ingredients("Maida")
    assert ing.normalized == "wheat flour" and ing.match_confidence == 1.0


def test_normalize_fuzzy_typo():
    (ing,) = extract_ingredients("Sodum benzoate")  # OCR typo
    assert ing.normalized == "sodium benzoate" and 0.88 <= ing.match_confidence < 1.0


def test_normalize_unknown():
    (ing,) = extract_ingredients("Zzyzx gum")
    assert ing.known is False and ing.normalized is None and ing.match_confidence < 0.88


def test_unknown_ins_keeps_number_and_class():
    (ing,) = extract_ingredients("Colour (INS 999)")
    assert ing.known is False and ing.ins_number == "999" and ing.category == "colour"


def test_ins_variant_falls_back_to_base_with_lower_confidence():
    (ing,) = extract_ingredients("Acidity regulator (331(i))")
    assert ing.known and ing.match_confidence == BASE_INS_MATCH_CONFIDENCE == 0.85  # below the 0.90 engine cutoff


def test_synonym_in_brackets_not_duplicated():
    names = [i.original for i in extract_ingredients("Refined wheat flour (Maida)")]
    assert len(names) == 1


def test_descriptor_in_brackets_dropped():
    assert len(extract_ingredients("Salt (iodised)")) == 1


def test_ids_are_sequential():
    ings = extract_ingredients("Sugar, Salt, Emulsifier (322, 471)")
    assert [i.id for i in ings] == ["ing_1", "ing_2", "ing_3", "ing_4"]


# ------------------------------------------------------------------ run-together words
def test_segment_run_together_example_from_the_spec():
    assert segment_run_together("Refinedwheatflour") == "Refined Wheat Flour"


@pytest.mark.parametrize("token,expected", [
    ("Sodiumbenzoate", "Sodium Benzoate"),
    ("Potassiumsorbate", "Potassium Sorbate"),
    ("REFINEDWHEATFLOUR", "Refined Wheat Flour"),  # case does not matter
    ("Hydrogenatedvegetablefat", "Hydrogenated Vegetable Fat"),
])
def test_segment_run_together_more_examples(token, expected):
    assert segment_run_together(token) == expected


@pytest.mark.parametrize("token", [
    "Palmoil",  # shorter than 12 characters: not attempted
    "Refined wheat flour",  # already has spaces
    "Refinedwheat-flour1",  # not letters only
    "Zzyzxbloopglorbq",  # cannot be covered by known words
    "Maltodextrin",  # a single known word, nothing to split
    "Maltodextrinsx",  # known word + leftover letters: no partial splits
    "",
])
def test_segment_run_together_refuses(token):
    assert segment_run_together(token) is None


def test_segmentation_prefers_fewer_longer_words():
    vocab = {"ab", "cd", "abcd", "a", "b", "c", "d"}
    assert segment_words("abcd", vocab) == ["abcd"]
    assert segment_words("abcdab", vocab) == ["abcd", "ab"]
    assert segment_words("wheatflour", _vocabulary()) == ["wheat", "flour"]


def test_segmentation_needs_a_complete_cover():
    assert segment_words("wheatxyz", _vocabulary()) is None


def test_vocabulary_comes_from_the_rule_files():
    words = _vocabulary()
    assert {"wheat", "flour", "sodium", "benzoate", "refined", "palm", "regulator"} <= words
    assert all(w.isalpha() and w == w.lower() for w in words)


def test_run_together_ingredient_is_repaired_and_matched():
    (ing,) = extract_ingredients("Refinedwheatflour")
    assert ing.normalized == "wheat flour" and ing.known and ing.match_confidence == 1.0
    assert ing.original == "Refinedwheatflour"  # the raw OCR token is kept as read
    assert ing.repaired is True


def test_run_together_keeps_percentage_and_brackets():
    (ing,) = extract_ingredients("Refinedwheatflour (72%)")
    assert ing.normalized == "wheat flour" and ing.percentage == 72.0
    assert ing.original == "Refinedwheatflour (72%)" and ing.repaired is True


def test_run_together_additive_keeps_its_details():
    (ing,) = extract_ingredients("Sodiumbenzoate")
    assert (ing.normalized, ing.ins_number, ing.category) == ("sodium benzoate", "211", "preservative")
    assert ing.original == "Sodiumbenzoate" and ing.repaired is True


def test_run_together_inside_a_full_list():
    ings = extract_ingredients("Refinedwheatflour (72%), Palm oil, Sodiumbenzoate, Salt")
    assert [i.normalized for i in ings] == ["wheat flour", "palm oil", "sodium benzoate", "salt"]
    assert [i.repaired for i in ings] == [True, False, True, False]  # only the repaired ones are flagged


def test_run_together_inside_a_class_bracket():
    (ing,) = extract_ingredients("Flavour enhancer (Monosodiumglutamate)")
    assert ing.normalized == "monosodium glutamate" and ing.ins_number == "621"
    assert ing.original == "Flavour enhancer (Monosodiumglutamate)" and ing.repaired is True


def test_a_run_together_token_the_fuzzy_match_already_accepts_is_not_rewritten():
    """"Potassiumsorbate" scores >= 88 in the normal lookup, so the fallback never runs."""
    (ing,) = extract_ingredients("Preservative (Potassiumsorbate)")
    assert ing.normalized == "potassium sorbate" and ing.original == "Preservative (Potassiumsorbate)"
    assert ing.repaired is False  # matched without the split, so not "repaired"


def test_split_text_that_does_not_match_is_rejected():
    """Splits into known words, but "salt water palm sugar" is not an ingredient: stay unknown, text unchanged."""
    assert segment_run_together("Saltwaterpalmsugar") == "Salt Water Palm Sugar"
    (ing,) = extract_ingredients("Saltwaterpalmsugar")
    assert ing.known is False and ing.normalized is None and ing.original == "Saltwaterpalmsugar"
    assert ing.repaired is False


def test_unknown_long_chemical_name_is_not_forced_into_a_match():
    (ing,) = extract_ingredients("Hydroxypropylmethylcellulose")
    assert ing.known is False and ing.original == "Hydroxypropylmethylcellulose" and ing.repaired is False


def test_short_run_together_tokens_are_not_touched():
    (ing,) = extract_ingredients("Palmoil")  # 7 characters, below the minimum length
    assert ing.known is False and ing.original == "Palmoil" and ing.repaired is False


def test_already_matching_tokens_are_left_alone():
    (ing,) = extract_ingredients("Maltodextrin")
    assert ing.original == "Maltodextrin" and ing.known and ing.repaired is False
    (ing,) = extract_ingredients("Sodum benzoate")  # fuzzy match: no repair either
    assert ing.original == "Sodum benzoate" and ing.known and ing.repaired is False


def test_repaired_is_false_for_every_ordinary_match():
    text = "Wheat flour (72%), Salt, Preservative (INS 211), Emulsifier (322, 471), Maida, Sodum benzoate, Zzyzx gum"
    assert [i.repaired for i in extract_ingredients(text)] == [False] * 8


def test_repaired_field_defaults_to_false_and_old_data_still_loads():
    from app.schemas import Ingredient
    assert Ingredient(id="i", original="x", match_confidence=0.5, known=False).repaired is False
    assert "repaired" in Ingredient.model_fields


def test_repaired_match_uses_the_normal_cutoff():
    """The split text goes through the same exact/fuzzy lookup, so a typo inside still needs >= 88."""
    (ing,) = extract_ingredients("Refinedwheatfluor")  # "fluor" is not a known word: cannot be split at all
    assert ing.known is False


# ------------------------------------------------------------------ nutrition
def test_nutrition_full_table():
    n, warnings = parse_nutrition(
        "NUTRITION INFORMATION per 100 g: Energy 452 kcal, Total fat 17.5 g, Saturated fat 8.2 g, "
        "Trans fat 0.1 g, Carbohydrate 62 g, Total sugars 3.4 g, Protein 9.1 g, Sodium 1240 mg")
    assert (n.basis, n.energy_kcal, n.total_fat_g, n.sat_fat_g, n.trans_fat_g) == ("per_100g", 452, 17.5, 8.2, 0.1)
    assert (n.sugar_g, n.protein_g, n.sodium_mg, n.fiber_g) == (3.4, 9.1, 1240, None)
    assert warnings == []


def test_nutrition_kj_converted():
    n, _ = parse_nutrition("Energy 1000 kJ")
    assert n.energy_kcal == pytest.approx(239.01, abs=0.01)


def test_nutrition_prefers_printed_kcal():
    n, _ = parse_nutrition("Energy 1890 kJ (452 kcal)")
    assert n.energy_kcal == 452


def test_nutrition_salt_to_sodium():
    n, _ = parse_nutrition("Salt 1.5 g")
    assert n.sodium_mg == 600


def test_nutrition_sodium_wins_over_salt():
    n, _ = parse_nutrition("Sodium 500 mg, Salt 1.5 g")
    assert n.sodium_mg == 500


def test_nutrition_sodium_in_grams():
    n, _ = parse_nutrition("Sodium 0.5 g")
    assert n.sodium_mg == 500


def test_nutrition_missing_gives_none():
    n, _ = parse_nutrition("Protein 5 g")
    assert n.protein_g == 5 and n.sugar_g is None and n.energy_kcal is None


def test_nutrition_empty():
    n, _ = parse_nutrition(None)
    assert n.basis is None and n.energy_kcal is None


def test_nutrition_decimal_comma_and_ocr_o():
    n, _ = parse_nutrition("Total sugars 3,4 g  Protein 1O g")
    assert n.sugar_g == 3.4 and n.protein_g == 10


def test_nutrition_per_100g_header_not_read_as_value():
    n, _ = parse_nutrition("Energy per 100 g 452 kcal")
    assert n.energy_kcal == 452


def test_nutrition_implausible_value_dropped_with_warning():
    n, warnings = parse_nutrition("per 100 g: Total fat 175 g")
    assert n.total_fat_g is None and "IMPLAUSIBLE_NUTRIENT_IGNORED:total_fat_g" in warnings


def test_nutrition_ignores_added_sugars_line_and_percentages():
    n, _ = parse_nutrition("Total sugars 3.4 g Added sugars 1 g")
    assert n.sugar_g == 3.4
    n, _ = parse_nutrition("Sugar (12%)")
    assert n.sugar_g is None


def test_nutrition_energy_unit_in_label():
    n, _ = parse_nutrition("Energy (kcal) 452")
    assert n.energy_kcal == 452


# ---- OCR that dropped the spaces
@pytest.mark.parametrize("text,field,value", [
    ("Energy452kcal", "energy_kcal", 452),
    ("Sodium1240mg", "sodium_mg", 1240),
    ("Protein9.1g", "protein_g", 9.1),
    ("Total fat17.5g", "total_fat_g", 17.5),
    ("Saturated fat8.2g", "sat_fat_g", 8.2),
    ("Trans fat0.1g", "trans_fat_g", 0.1),
    ("Total sugars3.4g", "sugar_g", 3.4),
    ("Salt1.5g", "sodium_mg", 600),
    ("Dietary fibre3g", "fiber_g", 3),
    ("Energy1890kJ", "energy_kcal", 451.72),
])
def test_nutrition_value_glued_to_its_label(text, field, value):
    n, _ = parse_nutrition("per 100 g: " + text)
    assert getattr(n, field) == pytest.approx(value, abs=0.01)


@pytest.mark.parametrize("text,field,value", [
    ("Totalfat17.5g", "total_fat_g", 17.5),
    ("Saturatedfat8.2g", "sat_fat_g", 8.2),
    ("Transfat0.1g", "trans_fat_g", 0.1),
    ("Totalsugars3.4g", "sugar_g", 3.4),
    ("Dietaryfibre3g", "fiber_g", 3),
    ("Total fat 17.5 g", "total_fat_g", 17.5),  # normal spacing still works
])
def test_nutrition_labels_with_dropped_spaces(text, field, value):
    n, _ = parse_nutrition("per 100 g: " + text)
    assert getattr(n, field) == pytest.approx(value)


def test_nutrition_actual_ocr_output_from_the_example_label():
    """Real OCR text (space lost after "Energy") that used to give energy_kcal = None."""
    n, warnings = parse_nutrition(
        "NUTRITION INFORMATION per 100g: Energy452kcal,\nTotal fat 17.5 g, Saturated fat 8.2 g, Trans fat 0.1 g.\n"
        "Total sugars 3.4 g, Protein 9.1 g, Sodium 1240 mg")
    assert (n.basis, n.energy_kcal, n.total_fat_g, n.sat_fat_g, n.trans_fat_g) == ("per_100g", 452, 17.5, 8.2, 0.1)
    assert (n.sugar_g, n.protein_g, n.sodium_mg) == (3.4, 9.1, 1240) and warnings == []


def test_nutrition_everything_run_together():
    n, _ = parse_nutrition("per 100 g: Energy452kcalTotalfat17.5gSaturatedfat8.2gSodium1240mg")
    assert (n.energy_kcal, n.total_fat_g, n.sat_fat_g, n.sodium_mg) == (452, 17.5, 8.2, 1240)


@pytest.mark.parametrize("text", [
    "Salted peanuts 5 g", "Sugarcane juice 5 g", "Fatty acids 5 g", "Proteinbar 5 g",
    "Energydrink 5 g", "Sodiumbenzoate 5 g", "Brownsugar 5 g", "Unsalted 5 g",
])
def test_labels_inside_longer_words_are_not_nutrients(text):
    n, _ = parse_nutrition("per 100 g: " + text)
    assert all(getattr(n, f) is None for f in ("energy_kcal", "sugar_g", "sodium_mg", "sat_fat_g",
                                                "trans_fat_g", "total_fat_g", "protein_g", "fiber_g"))


def test_gluing_does_not_break_the_percent_and_added_sugar_guards():
    assert parse_nutrition("Sugar(12%)")[0].sugar_g is None
    assert parse_nutrition("Total sugars3.4g Added sugars1g")[0].sugar_g == 3.4


# ------------------------------------------------------------------ sections
LABEL = (
    "INGREDIENTS: Refined wheat flour (72%), Palm oil, Salt,\nSugar, Acidity regulator (INS 501(i)).\n"
    "NUTRITION INFORMATION per 100 g: Energy 452 kcal\nSodium 1240 mg\n"
    "Manufactured by ABC Foods Pvt Ltd"
)


def test_sections_split():
    s = extract_sections(LABEL)
    assert s.ingredients_text == "Refined wheat flour (72%), Palm oil, Salt, Sugar, Acidity regulator (INS 501(i))"
    assert "Energy 452 kcal" in s.nutrition_text
    assert "Palm oil" not in s.rest_text


def test_sections_ocr_mangled_headings():
    s = extract_sections("lNGREDlENTS: Sugar, Salt\nNUTRITI0N INFORMATION Energy 10 kcal")
    assert s.ingredients_text == "Sugar, Salt" and s.nutrition_text.startswith("NUTRITI0N")


def test_sections_stop_at_allergen_and_mfg():
    s = extract_sections("Ingredients: Sugar, Salt. Allergen information: contains milk")
    assert s.ingredients_text == "Sugar, Salt"


def test_sections_nutrition_before_ingredients():
    s = extract_sections("Nutrition Information Energy 100 kcal\nIngredients: Sugar, Salt")
    assert s.ingredients_text == "Sugar, Salt" and "Sugar" not in s.nutrition_text


def test_sections_hyphenated_line_break_rejoined():
    s = extract_sections("Ingredients: Sugar, Emulsi-\nfier (322)")
    assert "Emulsifier (322)" in s.ingredients_text


def test_sections_no_ingredients_heading():
    assert extract_sections("Energy 100 kcal Protein 3 g").ingredients_text is None


# ------------------------------------------------------------------ /analyze
def test_analyze_text(client):
    r = client.post("/api/v1/analyze", headers=headers(), json={
        "ingredients_text": "Wheat flour (72%), Salt, Preservative (INS 211)",
        "nutrition_text": "Sodium 900 mg, Protein 8 g",
        "food_category": "bakery",
    })
    body = r.json()
    assert r.status_code == 200
    assert body["ocr"] is None and body["food_category"] == "bakery"
    assert [i["normalized"] for i in body["ingredients"]] == ["wheat flour", "salt", "sodium benzoate"]
    assert body["nutrition"]["sodium_mg"] == 900 and body["nutrition"]["sugar_g"] is None


def test_analyze_list_and_pasted_label(client):
    r = client.post("/api/v1/analyze", headers=headers(), json={"ingredients": ["Sugar", "Emulsifier (322, 471)"]})
    assert [i["ins_number"] for i in r.json()["ingredients"]] == [None, "322", "471"]
    r = client.post("/api/v1/analyze", headers=headers(), json={"ingredients_text": LABEL})
    body = r.json()
    assert len(body["ingredients"]) == 5 and body["nutrition"]["energy_kcal"] == 452


def test_analyze_repairs_run_together_words(client):
    r = client.post("/api/v1/analyze", headers=headers(), json={"ingredients_text": "Refinedwheatflour (72%), Sodiumbenzoate, Salt"})
    ings = r.json()["ingredients"]
    assert [i["normalized"] for i in ings] == ["wheat flour", "sodium benzoate", "salt"]
    assert ings[0]["original"] == "Refinedwheatflour (72%)"  # raw OCR token
    assert [i["repaired"] for i in ings] == [True, True, False]


def test_analyze_validation_errors(client):
    r = client.post("/api/v1/analyze", headers=headers(), json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = client.post("/api/v1/analyze", headers=headers(), json={"ingredients_text": "Sugar", "food_category": "nope"})
    assert r.json()["error"]["code"] == "INVALID_CATEGORY"
    r = client.post("/api/v1/analyze", headers=headers(), json={"ingredients_text": "   ,  ; "})
    assert r.status_code == 422
