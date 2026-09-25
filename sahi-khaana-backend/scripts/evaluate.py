"""Evaluate the pipeline on labelled label photos.

Usage (from the sahi-khaana-backend folder):
    python scripts/evaluate.py [--dir tests/fixtures/eval] [--out eval_report.md]

For every  <dir>/<name>.json  that has a photo  <dir>/<name>.jpg  (.jpeg/.png/.webp also work)
it runs the same steps as POST /scan (preprocess -> OCR -> extraction -> engines), directly and
without the API or database, then prints a markdown report and writes it to --out.

Fixture JSON fields:
    ground_truth_text     the label text exactly as printed (for CER/WER)
    expected_ingredients  list of ingredient names, as the normalizer should output them
                          (e.g. "wheat flour", "sodium benzoate"; unknown ones: the printed text)
    expected_statuses     {"<ingredient name>": "PASS|FLAG|REVIEW", ..., "overall": "PASS|FLAG|REVIEW"}
    food_category         a category id from GET /categories, or null

Metrics: CER/WER (jiwer, lower-cased with whitespace collapsed), ingredient precision/recall
(micro-averaged over all fixtures), status agreement (expected statuses matched / expected
statuses given) and the mean time of each pipeline stage.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jiwer  # noqa: E402

from app.engines.fssai_engine import evaluate_fssai  # noqa: E402
from app.engines.health_engine import assess_health  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.pipeline.normalizer import clean_name, extract_ingredients  # noqa: E402
from app.pipeline.nutrition_parser import parse_nutrition  # noqa: E402
from app.pipeline.ocr import run_ocr  # noqa: E402
from app.pipeline.preprocessing import decode_image, preprocess  # noqa: E402
from app.pipeline.sections import extract_sections  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
STAGES = ("preprocess", "ocr", "extraction", "engines")


# ---------------------------------------------------------------- metrics (pure functions)
def normalise_text(text: str) -> str:
    return " ".join(text.lower().split())


def text_errors(reference: str, hypothesis: str) -> tuple[float, float]:
    """(CER, WER) as fractions. `reference` must not be empty."""
    ref, hyp = normalise_text(reference), normalise_text(hypothesis)
    return jiwer.cer(ref, hyp), jiwer.wer(ref, hyp)


def ingredient_name(ing) -> str:
    return clean_name(ing.normalized or ing.original)


def ingredient_counts(expected: list[str], predicted: set[str]) -> tuple[int, int, int]:
    """(true positives, predicted count, expected count)."""
    expected_set = {clean_name(n) for n in expected}
    return len(expected_set & predicted), len(predicted), len(expected_set)


def status_agreement(expected: dict[str, str], ingredients, fssai) -> tuple[int, int]:
    """(matches, expected entries). Keys are ingredient names, or "overall"."""
    name_by_id = {i.id: ingredient_name(i) for i in ingredients}
    predicted: dict[str, str] = {}
    order = {"PASS": 0, "REVIEW": 1, "FLAG": 2}
    for f in fssai.findings:
        if f.ingredient_id is None:
            continue
        name = name_by_id[f.ingredient_id]
        if name not in predicted or order[f.status] > order[predicted[name]]:
            predicted[name] = f.status
    matches = 0
    for key, want in expected.items():
        got = fssai.overall_status if key == "overall" else predicted.get(clean_name(key))
        matches += got == want
    return matches, len(expected)


def pct(numerator: float, denominator: float) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "n/a"


# ---------------------------------------------------------------- one fixture
def find_image(directory: Path, name: str) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        candidate = directory / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    return None


def run_fixture(name: str, image: Path, spec: dict) -> dict:
    row = {"name": name, "error": None, "cer": None, "wer": None, "tp": 0, "pred": 0, "exp": 0,
           "agree": 0, "agree_total": 0, "times": {}}
    expected = spec.get("expected_ingredients", [])
    statuses = spec.get("expected_statuses", {})
    row["exp"] = len({clean_name(n) for n in expected})
    row["agree_total"] = len(statuses)

    def timed(stage, fn, *args):
        start = time.perf_counter()
        try:
            return fn(*args)
        finally:
            row["times"][stage] = time.perf_counter() - start

    try:
        pre = timed("preprocess", lambda: preprocess(decode_image(image.read_bytes())))
        ocr = timed("ocr", run_ocr, pre.processed, pre.original_resized)
        if spec.get("ground_truth_text", "").strip():
            row["cer"], row["wer"] = text_errors(spec["ground_truth_text"], ocr.raw_text)

        def extract():
            sections = extract_sections(ocr.raw_text)
            if not sections.ingredients_text:
                raise AppError("NO_INGREDIENTS_SECTION", "no ingredients section", 422)
            ingredients = extract_ingredients(sections.ingredients_text)
            nutrition, _ = parse_nutrition(sections.nutrition_text or sections.rest_text)
            return ingredients, nutrition

        ingredients, nutrition = timed("extraction", extract)

        def engines():
            food_category = spec.get("food_category")
            fssai = evaluate_fssai(ingredients, food_category, ocr.raw_text, ocr.confidence)
            health, _ = assess_health(nutrition, ingredients, food_category)
            return fssai, health

        fssai, _health = timed("engines", engines)
    except AppError as exc:
        row["error"] = exc.code  # counted as "found nothing" for the ingredient/status metrics
        return row

    predicted = {ingredient_name(i) for i in ingredients}
    row["tp"], row["pred"], row["exp"] = ingredient_counts(expected, predicted)
    row["agree"], row["agree_total"] = status_agreement(statuses, ingredients, fssai)
    return row


# ---------------------------------------------------------------- report
def build_report(rows: list[dict], skipped: list[str], directory: Path) -> str:
    ok = [r for r in rows if not r["error"]]
    cers = [r["cer"] for r in rows if r["cer"] is not None]
    wers = [r["wer"] for r in rows if r["wer"] is not None]
    tp, pred, exp = (sum(r[k] for r in rows) for k in ("tp", "pred", "exp"))
    agree, agree_total = sum(r["agree"] for r in rows), sum(r["agree_total"] for r in rows)

    def mean_ms(stage):
        values = [r["times"][stage] for r in rows if stage in r["times"]]
        return f"{1000 * sum(values) / len(values):.0f} ms" if values else "n/a"

    lines = [
        "# Evaluation report", "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} from `{directory}`. "
        f"Fixtures: {len(rows)} run, {len(rows) - len(ok)} failed, {len(skipped)} skipped (no photo).", "",
        "## Summary", "",
        "| Metric | Value |", "|---|---|",
        f"| Character error rate (CER), mean | {pct(sum(cers), len(cers))} |",
        f"| Word error rate (WER), mean | {pct(sum(wers), len(wers))} |",
        f"| Ingredient precision | {pct(tp, pred)} ({tp}/{pred}) |",
        f"| Ingredient recall | {pct(tp, exp)} ({tp}/{exp}) |",
        f"| Status agreement | {pct(agree, agree_total)} ({agree}/{agree_total}) |",
    ]
    lines += [f"| Mean time: {stage} | {mean_ms(stage)} |" for stage in STAGES]
    lines += ["", "## Per fixture", "",
              "| Fixture | CER | WER | Precision | Recall | Status agreement | Total time | Note |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        total = f"{1000 * sum(r['times'].values()):.0f} ms" if r["times"] else "n/a"
        cer = pct(r["cer"], 1) if r["cer"] is not None else "n/a"
        wer = pct(r["wer"], 1) if r["wer"] is not None else "n/a"
        lines.append(
            f"| {r['name']} | {cer} | {wer} | {pct(r['tp'], r['pred'])} | {pct(r['tp'], r['exp'])} | "
            f"{pct(r['agree'], r['agree_total'])} | {total} | {r['error'] or ''} |")
    if skipped:
        lines += ["", "Skipped (JSON without a photo): " + ", ".join(skipped)]
    lines += ["", "Notes: a fixture that fails (e.g. `POOR_IMAGE`) counts as zero ingredients found and zero "
              "statuses matched, and is left out of CER/WER. Precision/recall are micro-averaged over all fixtures."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, default=ROOT / "tests" / "fixtures" / "eval")
    parser.add_argument("--out", type=Path, default=ROOT / "eval_report.md")
    args = parser.parse_args(argv)

    specs = sorted(args.dir.glob("*.json"))
    if not specs:
        print(f"No fixtures (*.json) found in {args.dir}", file=sys.stderr)
        return 1

    rows, skipped = [], []
    for spec_path in specs:
        image = find_image(args.dir, spec_path.stem)
        if image is None:
            skipped.append(spec_path.stem)
            continue
        rows.append(run_fixture(spec_path.stem, image, json.loads(spec_path.read_text(encoding="utf-8"))))
    if not rows:
        print("Found fixture JSON files but no matching photos (name.jpg next to name.json).", file=sys.stderr)
        return 1

    report = build_report(rows, skipped, args.dir)
    print(report)
    args.out.write_text(report, encoding="utf-8")
    print(f"Written to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
