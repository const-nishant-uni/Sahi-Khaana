"""FSSAI engine tests. Uses small made-up rule sets so the tests don't depend on the
placeholder data in rules/*.json (which the project owner is still verifying)."""
from app.engines.fssai_engine import FssaiEngine
from app.rules import load_entries, load_rules
from app.schemas import Ingredient

SRC = "test rule"
ENTRIES = [
    {"id": "sugar", "name": "sugar", "category": "sweetener", "status": "PERMITTED", "source": SRC},
    {"id": "ins_124", "name": "ponceau 4r", "category": "colour", "status": "NOT_PERMITTED", "source": SRC},
    {"id": "ins_211", "name": "sodium benzoate", "category": "preservative", "status": "CONDITIONAL", "source": SRC,
     "conditions": [
         {"food_categories": ["beverages_non_alcoholic"], "result": "PASS"},
         {"food_categories": ["dairy"], "result": "FLAG", "note": "Not for dairy."},
     ]},
    {"id": "ins_330", "name": "citric acid", "category": "acidity_regulator", "status": "CONDITIONAL", "source": SRC,
     "conditions": [{"food_categories": ["*"], "result": "PASS"}]},
    {"id": "ins_102", "name": "tartrazine", "category": "colour", "status": "CONDITIONAL", "source": SRC,
     "conditions": []},
]
DECLARATIONS = [
    {"id": "DECL-COLOUR", "applies_to_category": "colour",
     "accepted_phrases": ["contains permitted synthetic food colour"], "status_if_missing": "REVIEW", "source": SRC},
]


def ing(n, normalized, category=None, known=True, conf=1.0):
    return Ingredient(id=f"ing_{n}", original=normalized or "?", normalized=normalized if known else None,
                      category=category, match_confidence=conf, known=known)


engine = FssaiEngine(ENTRIES, DECLARATIONS)


def one(ingredient, category=None, label_text="", ocr=1.0):
    result = engine.evaluate([ingredient], category, label_text, ocr)
    return result, result.findings[0]


# ------------------------------------------------------------------ per-ingredient rules
def test_unknown_ingredient_is_review():
    _, f = one(ing(1, None, known=False, conf=0.5))
    assert f.status == "REVIEW" and f.rule_id == "UNKNOWN_INGREDIENT"


def test_not_permitted_is_flag():
    _, f = one(ing(1, "ponceau 4r", "colour"), label_text="contains permitted synthetic food colour")
    assert f.status == "FLAG" and f.rule_id == "ins_124" and f.source == SRC


def test_permitted_is_pass():
    result, f = one(ing(1, "sugar", "sweetener"))
    assert f.status == "PASS" and result.overall_status == "PASS"


def test_conditional_without_food_category_is_review():
    _, f = one(ing(1, "sodium benzoate", "preservative"), category=None)
    assert f.status == "REVIEW" and "category" in f.reason


def test_conditional_pass_for_matching_category():
    _, f = one(ing(1, "sodium benzoate", "preservative"), category="beverages_non_alcoholic",
               label_text="contains preservative")
    assert f.status == "PASS"


def test_conditional_flag_for_prohibited_category():
    _, f = one(ing(1, "sodium benzoate", "preservative"), category="dairy", label_text="contains preservative")
    assert f.status == "FLAG" and "Not for dairy" in f.reason


def test_conditional_uncovered_category_is_review():
    _, f = one(ing(1, "sodium benzoate", "preservative"), category="bakery")
    assert f.status == "REVIEW"


def test_conditional_wildcard_category():
    _, f = one(ing(1, "citric acid", "acidity_regulator"), category="bakery")
    assert f.status == "PASS"


def test_conditional_with_no_conditions_is_review():
    """The state of every additive in the seed data until the owner fills in conditions."""
    _, f = one(ing(1, "citric acid", "acidity_regulator"), category=None)
    assert f.status == "REVIEW"
    _, f = one(ing(1, "tartrazine", "colour"), category="bakery", label_text="contains permitted synthetic food colour")
    assert f.status == "REVIEW"


def test_low_match_confidence_downgrades_pass_to_review():
    _, f = one(ing(1, "sugar", "sweetener", conf=0.9))
    assert f.status == "REVIEW" and "0.90" in f.reason


def test_low_match_confidence_does_not_hide_a_flag():
    _, f = one(ing(1, "ponceau 4r", "colour", conf=0.9), label_text="contains permitted synthetic food colour")
    assert f.status == "FLAG"


def test_slightly_imperfect_match_still_passes():
    _, f = one(ing(1, "sugar", "sweetener", conf=0.97))
    assert f.status == "PASS"


# ------------------------------------------------------------------ declarations
def test_missing_declaration_downgrades_to_review():
    result, _ = one(ing(1, "tartrazine", "colour"), category="bakery", label_text="")
    assert any(f.rule_id == "DECL-COLOUR" and f.status == "REVIEW" for f in result.findings)


def test_declaration_present_adds_no_finding():
    label = "Ingredients: sugar. CONTAINS PERMITTED SYNTHETIC FOOD COLOUR (INS 102)"
    result, _ = one(ing(1, "tartrazine", "colour"), category="bakery", label_text=label)
    assert all(f.rule_id != "DECL-COLOUR" for f in result.findings)


def test_declaration_found_despite_ocr_noise():
    label = "CONTAINS PERMITTED SYNTHETlC FOOD C0L0UR"  # 3 OCR slips
    result, _ = one(ing(1, "tartrazine", "colour"), category="bakery", label_text=label)
    assert all(f.rule_id != "DECL-COLOUR" for f in result.findings)


def test_a_different_declaration_does_not_count():
    """"natural colour" must not satisfy the "synthetic food colour" requirement."""
    result, _ = one(ing(1, "tartrazine", "colour"), category="bakery", label_text="Contains permitted natural colour")
    assert any(f.rule_id == "DECL-COLOUR" for f in result.findings)


def test_declaration_can_downgrade_a_pass():
    entries = ENTRIES + [{"id": "ins_x", "name": "good colour", "category": "colour",
                          "status": "PERMITTED", "source": SRC}]
    eng = FssaiEngine(entries, DECLARATIONS)
    result = eng.evaluate([ing(1, "good colour", "colour")], None, "no declaration here")
    assert result.summary.review == 1 and result.summary.pass_ == 0
    assert result.overall_status == "REVIEW"


def test_declaration_does_not_soften_a_flag():
    result, _ = one(ing(1, "ponceau 4r", "colour"), label_text="nothing")
    assert result.summary.flag == 1 and result.overall_status == "FLAG"


def test_declaration_not_checked_when_category_absent():
    result, _ = one(ing(1, "sugar", "sweetener"), label_text="")
    assert len(result.findings) == 1


# ------------------------------------------------------------------ overall + summary
def test_overall_status_precedence():
    ings = [ing(1, "sugar", "sweetener"), ing(2, None, known=False, conf=0.4), ing(3, "ponceau 4r", "colour")]
    result = engine.evaluate(ings, None, "contains permitted synthetic food colour")
    assert result.overall_status == "FLAG"
    assert (result.summary.pass_, result.summary.flag, result.summary.review) == (1, 1, 1)


def test_review_beats_pass():
    result = engine.evaluate([ing(1, "sugar", "sweetener"), ing(2, None, known=False, conf=0.4)], None, "")
    assert result.overall_status == "REVIEW"


def test_summary_counts_and_confidence():
    ings = [ing(1, "sugar", "sweetener"), ing(2, "sugar", "sweetener"), ing(3, None, known=False, conf=0.3),
            ing(4, None, known=False, conf=0.3)]
    result = engine.evaluate(ings, None, "", ocr_confidence=0.8)
    assert (result.summary.scanned, result.summary.matched) == (4, 2)
    assert result.confidence == 0.4  # 0.8 * 2/4


def test_summary_counts_each_ingredient_once():
    """An ingredient with two findings (rule + declaration) is counted once, at its worst status."""
    result, _ = one(ing(1, "tartrazine", "colour"), category="bakery", label_text="")
    assert len(result.findings) == 2
    s = result.summary
    assert s.pass_ + s.flag + s.review == s.scanned == 1


def test_no_ingredients_is_review_with_zero_confidence():
    result = engine.evaluate([], None, "", 0.9)
    assert result.overall_status == "REVIEW" and result.confidence == 0.0


def test_summary_serialises_pass_key():
    dumped = engine.evaluate([ing(1, "sugar", "sweetener")], None, "").model_dump(by_alias=True)
    assert dumped["summary"]["pass"] == 1


# ------------------------------------------------------------------ the real rule files
def test_rule_files_are_well_formed():
    entries = load_entries()
    names = [e["name"].lower() for e in entries]
    assert len(names) == len(set(names)), "entry names must be unique (the engine looks rules up by name)"
    for e in entries:
        assert e["status"] in ("PERMITTED", "NOT_PERMITTED", "CONDITIONAL"), e["id"]
        assert e.get("source"), f"{e['id']} has no source"
        for cond in e.get("conditions", []):
            assert cond["result"] in ("PASS", "FLAG") and cond["food_categories"]
    for d in load_rules("declarations.json")["declarations"]:
        assert d["source"] and d["accepted_phrases"] and d["status_if_missing"] in ("REVIEW", "FLAG")


def test_seed_additives_are_review_until_verified():
    """Placeholder data must never produce a confident PASS/FLAG for an additive."""
    from app.pipeline.normalizer import extract_ingredients
    ings = extract_ingredients("Preservative (INS 211), Colour (INS 102)")
    result = FssaiEngine().evaluate(ings, "bakery", "")
    assert all(f.status == "REVIEW" for f in result.findings)
