"""Tests for scripts/evaluate.py (metrics + a run over the shipped example fixtures)."""
import importlib.util
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("evaluate", ROOT / "scripts" / "evaluate.py")
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)

from app.schemas import Finding, FssaiResult, FssaiSummary, Ingredient  # noqa: E402


def ing(n, normalized, original=None):
    return Ingredient(id=f"ing_{n}", original=original or normalized, normalized=normalized, category=None,
                      match_confidence=1.0, known=normalized is not None)


def result(findings, overall="REVIEW"):
    return FssaiResult(overall_status=overall, confidence=1.0, findings=findings,
                       summary=FssaiSummary(scanned=1, matched=1, pass_=0, flag=0, review=1))


def f(ing_id, status):
    return Finding(ingredient_id=ing_id, rule_id="r", status=status, reason="x", source="s")


# ------------------------------------------------------------------ metrics
def test_text_errors_identical_and_case_and_whitespace_insensitive():
    assert evaluate.text_errors("Sugar, Salt", "sugar,   salt") == (0.0, 0.0)


def test_text_errors_counts_mistakes():
    cer, wer = evaluate.text_errors("sugar salt", "sugar sait")
    assert cer == pytest.approx(0.1) and wer == pytest.approx(0.5)


def test_ingredient_counts_precision_recall():
    tp, pred, exp = evaluate.ingredient_counts(["Wheat flour", "salt", "tartrazine"], {"wheat flour", "salt", "sugar", "oil"})
    assert (tp, pred, exp) == (2, 4, 3)  # precision 2/4, recall 2/3


def test_ingredient_names_prefer_normalized_and_are_cleaned():
    assert evaluate.ingredient_name(ing(1, "Sodium Benzoate")) == "sodium benzoate"
    assert evaluate.ingredient_name(ing(2, None, original="Zzyzx-Gum (X)")) == "zzyzx gum x"


def test_status_agreement_matches_names_and_overall():
    ings = [ing(1, "salt"), ing(2, "tartrazine")]
    fssai = result([f("ing_1", "PASS"), f("ing_2", "REVIEW")], overall="REVIEW")
    assert evaluate.status_agreement({"salt": "PASS", "Tartrazine": "REVIEW", "overall": "REVIEW"}, ings, fssai) == (3, 3)
    assert evaluate.status_agreement({"salt": "FLAG", "overall": "PASS"}, ings, fssai) == (0, 2)


def test_status_agreement_missing_ingredient_is_a_disagreement():
    fssai = result([f("ing_1", "PASS")])
    assert evaluate.status_agreement({"sugar": "PASS"}, [ing(1, "salt")], fssai) == (0, 1)


def test_status_agreement_takes_the_worst_status_and_ignores_label_level_findings():
    fssai = result([f("ing_1", "PASS"), f("ing_1", "FLAG"), f(None, "REVIEW")])
    assert evaluate.status_agreement({"salt": "FLAG"}, [ing(1, "salt")], fssai) == (1, 1)


def test_pct_handles_zero_denominator():
    assert evaluate.pct(1, 4) == "25.0%" and evaluate.pct(0, 0) == "n/a"


# ------------------------------------------------------------------ whole run
def test_runs_on_the_shipped_example_fixtures(tmp_path, capsys):
    out = tmp_path / "report.md"
    assert evaluate.main(["--out", str(out)]) == 0
    report = out.read_text(encoding="utf-8")
    assert capsys.readouterr().out.strip() == report.strip()  # what is printed is what is written
    for expected in ("# Evaluation report", "Character error rate", "Word error rate", "Ingredient precision",
                     "Ingredient recall", "Status agreement", "Mean time: preprocess", "Mean time: ocr",
                     "Mean time: extraction", "Mean time: engines", "example_1", "example_2"):
        assert expected in report
    assert "2 run, 0 failed, 0 skipped" in report


def test_example_fixture_json_files_have_the_documented_fields():
    files = sorted((ROOT / "tests" / "fixtures" / "eval").glob("*.json"))
    assert len(files) >= 2
    for path in files:
        spec_ = json.loads(path.read_text(encoding="utf-8"))
        assert {"ground_truth_text", "expected_ingredients", "expected_statuses", "food_category"} <= set(spec_)
        assert isinstance(spec_["expected_ingredients"], list) and isinstance(spec_["expected_statuses"], dict)
        assert set(spec_["expected_statuses"].values()) <= {"PASS", "FLAG", "REVIEW"}
        assert (path.with_suffix(".jpg")).exists()


def test_json_without_a_photo_is_skipped_and_reported(tmp_path):
    src = ROOT / "tests" / "fixtures" / "eval"
    shutil.copy(src / "example_1.json", tmp_path / "lonely.json")
    shutil.copy(src / "example_2.json", tmp_path / "example_2.json")
    shutil.copy(src / "example_2.jpg", tmp_path / "example_2.jpg")
    out = tmp_path / "r.md"
    assert evaluate.main(["--dir", str(tmp_path), "--out", str(out)]) == 0
    assert "1 run, 0 failed, 1 skipped" in out.read_text() and "lonely" in out.read_text()


def test_unreadable_photo_counts_as_failure_not_a_crash(tmp_path):
    (tmp_path / "blurry.json").write_text(json.dumps({
        "ground_truth_text": "x", "expected_ingredients": ["sugar", "salt"],
        "expected_statuses": {"sugar": "PASS"}, "food_category": None}))
    cv2.imwrite(str(tmp_path / "blurry.jpg"), np.full((300, 600, 3), 200, np.uint8))  # flat grey: no detail
    out = tmp_path / "r.md"
    assert evaluate.main(["--dir", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text()
    assert "1 run, 1 failed" in text and "POOR_IMAGE" in text
    assert "Ingredient recall | 0.0% (0/2)" in text and "Status agreement | 0.0% (0/1)" in text


def test_no_fixtures_is_an_error_exit(tmp_path, capsys):
    assert evaluate.main(["--dir", str(tmp_path), "--out", str(tmp_path / "r.md")]) == 1
    assert "No fixtures" in capsys.readouterr().err
