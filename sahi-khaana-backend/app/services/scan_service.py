"""Orchestrates one scan: validate upload -> preprocess -> OCR -> extraction.

Phase 2: `ocr`, `ingredients` and `nutrition` are real. `fssai_result` and
`health_result` are still placeholders (TODO Phase 3) and every response says
so with the MOCK_DATA warning.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from app.config import BASE_DIR, get_settings
from app.errors import AppError, file_too_large, invalid_file, no_ingredients_section
from app.pipeline.normalizer import extract_ingredients
from app.pipeline.nutrition_parser import parse_nutrition
from app.pipeline.ocr import run_ocr
from app.pipeline.preprocessing import decode_image, preprocess
from app.pipeline.sections import extract_sections
from app.schemas import AnalyzeRequest, Ingredient, Nutrition, ScanResponse

log = logging.getLogger(__name__)

CATEGORIES_FILE = BASE_DIR / "app" / "rules" / "food_categories.json"


# ---------- categories ----------
def load_categories() -> list[dict]:
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        return [{"id": c["id"], "name": c["name"]} for c in json.load(f)["categories"]]


def validate_category(food_category: str | None) -> str | None:
    """Empty -> None. Unknown ids are rejected so typos don't silently pass."""
    if not food_category or not food_category.strip():
        return None
    food_category = food_category.strip()
    if food_category not in {c["id"] for c in load_categories()}:
        raise AppError("INVALID_CATEGORY", f"Unknown food_category '{food_category}'.", 400)
    return food_category


# ---------- upload handling ----------
def _detect_image_type(head: bytes) -> str | None:
    """Identify the file by its magic bytes (never trust the filename/content-type)."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def read_and_save_upload(file: UploadFile) -> tuple[bytes, Path]:
    """Validate the upload (type + size) and save it under a random UUID name."""
    cfg = get_settings()
    data = file.file.read(cfg.max_upload_bytes + 1)  # +1 so we can detect "too big"
    if len(data) > cfg.max_upload_bytes:
        raise file_too_large(cfg.max_upload_bytes)
    if not data:
        raise invalid_file("The uploaded file is empty.")

    ext = _detect_image_type(data[:12])
    if ext is None:
        raise invalid_file("Only JPG, PNG or WEBP images are accepted.")

    cfg.upload_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.upload_dir / f"{uuid.uuid4()}.{ext}"
    path.write_bytes(data)
    return data, path


# ---------- the scan itself ----------
def process_scan(file: UploadFile, food_category: str | None) -> ScanResponse:
    cfg = get_settings()
    food_category = validate_category(food_category)
    data, path = read_and_save_upload(file)

    t0 = time.perf_counter()
    image = decode_image(data)
    pre = preprocess(image)  # may raise POOR_IMAGE
    t1 = time.perf_counter()
    ocr = run_ocr(pre.processed, pre.original_resized)  # may raise NO_TEXT_FOUND
    t2 = time.perf_counter()
    log.info(
        "scan %s: preprocess %.2fs (blur=%.0f, deskew=%.1f°), ocr %.2fs (%s, conf=%.2f)",
        path.name, t1 - t0, pre.blur_score, pre.deskew_angle, t2 - t1, ocr.engine, ocr.confidence,
    )

    sections = extract_sections(ocr.raw_text)
    if not sections.ingredients_text:
        raise no_ingredients_section()
    ingredients = extract_ingredients(sections.ingredients_text)
    if not ingredients:
        raise no_ingredients_section()
    # No "Nutrition" heading found? Fall back to everything outside the ingredient list.
    nutrition, nutrition_warnings = parse_nutrition(sections.nutrition_text or sections.rest_text)
    t3 = time.perf_counter()
    log.info("scan %s: extraction %.2fs, %d ingredients", path.name, t3 - t2, len(ingredients))

    warnings = []
    if ocr.confidence < cfg.ocr_warn_confidence:
        warnings.append("LOW_OCR_CONFIDENCE")
    warnings += _extraction_warnings(nutrition, nutrition_warnings)
    return build_response(
        ingredients, nutrition, food_category, warnings,
        ocr={"raw_text": ocr.raw_text, "confidence": round(ocr.confidence, 4), "engine": ocr.engine},
    )


def analyze_text(req: AnalyzeRequest) -> ScanResponse:
    """Text-only version of a scan (POST /analyze)."""
    food_category = validate_category(req.food_category)
    text = ", ".join(i.strip() for i in req.ingredients if i.strip()) if req.ingredients else req.ingredients_text

    # Someone may paste a whole label ("Ingredients: ... Nutrition: ..."): use the sections if present.
    sections = extract_sections(text)
    ingredients_text = sections.ingredients_text or text
    nutrition_text = req.nutrition_text or sections.nutrition_text

    ingredients = extract_ingredients(ingredients_text)
    if not ingredients:
        raise no_ingredients_section()
    nutrition, nutrition_warnings = parse_nutrition(nutrition_text)
    warnings = _extraction_warnings(nutrition, nutrition_warnings)
    return build_response(ingredients, nutrition, food_category, warnings, ocr=None)


def _extraction_warnings(nutrition: Nutrition, nutrition_warnings: list[str]) -> list[str]:
    warnings = list(nutrition_warnings)
    if not any(v is not None for k, v in nutrition.model_dump().items() if k != "basis"):
        warnings.append("NO_NUTRITION_FOUND")
    return warnings


def build_response(
    ingredients: list[Ingredient], nutrition: Nutrition, food_category: str | None,
    warnings: list[str], ocr: dict | None,
) -> ScanResponse:
    """Assemble the full response. FSSAI + health parts are placeholders until Phase 3."""
    known = sum(1 for i in ingredients if i.known)
    return ScanResponse(
        scan_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        warnings=warnings + ["MOCK_DATA"],  # TODO(Phase 3): drop once the engines exist
        ocr=ocr,
        food_category=food_category,
        ingredients=ingredients,
        nutrition=nutrition,
        # TODO(Phase 3): replace with fssai_engine / health_engine output.
        fssai_result={
            "overall_status": "REVIEW",
            "summary": {"scanned": len(ingredients), "matched": known, "pass": 0, "flag": 0, "review": len(ingredients)},
            "confidence": 0.0,
            "findings": [],
        },
        health_result={
            "score": 50, "assessment": "MODERATE", "data_completeness": 0.0, "factors": [],
            "disclaimer": "General information only. Not medical or dietary advice.",
        },
    )


# ---------- MOCK sample for GET /mock/scan ----------
def build_mock_analysis(food_category: str | None = None) -> dict:
    """A realistic, fixed sample result for an instant-noodles style product.

    Only used by GET /mock/scan, so the Flutter developer can see a full response.
    The values are illustrative, NOT real regulatory decisions.
    """
    mock_source = "MOCK: illustrative only, not a real rule"
    return {
        "scan_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "warnings": ["MOCK_DATA"],
        "ocr": {
            "raw_text": (
                "INGREDIENTS: Refined wheat flour (72%), Palm oil, Salt, Sugar, "
                "Acidity regulator (INS 501(i)), Flavour enhancer (INS 627, INS 631), "
                "Colour (INS 102), Preservative (INS 211).\n"
                "NUTRITION INFORMATION per 100 g: Energy 452 kcal, Total fat 17.5 g, "
                "Saturated fat 8.2 g, Trans fat 0.1 g, Carbohydrate 62 g, Total sugars 3.4 g, "
                "Protein 9.1 g, Sodium 1240 mg"
            ),
            "confidence": 0.93,
            "engine": "rapidocr",
        },
        "food_category": food_category,
        "ingredients": [
            {"id": "ing_1", "original": "Refined wheat flour (72%)", "normalized": "wheat flour", "category": "cereal", "ins_number": None, "percentage": 72.0, "match_confidence": 1.0, "known": True},
            {"id": "ing_2", "original": "Palm oil", "normalized": "palm oil", "category": "fat_oil", "ins_number": None, "percentage": None, "match_confidence": 1.0, "known": True},
            {"id": "ing_3", "original": "Salt", "normalized": "salt", "category": "seasoning", "ins_number": None, "percentage": None, "match_confidence": 1.0, "known": True},
            {"id": "ing_4", "original": "Sugar", "normalized": "sugar", "category": "sweetener", "ins_number": None, "percentage": None, "match_confidence": 1.0, "known": True},
            {"id": "ing_5", "original": "Acidity regulator (INS 501(i))", "normalized": "potassium carbonate", "category": "acidity_regulator", "ins_number": "501(i)", "percentage": None, "match_confidence": 0.98, "known": True},
            {"id": "ing_6", "original": "Flavour enhancer (INS 627)", "normalized": "disodium guanylate", "category": "flavour_enhancer", "ins_number": "627", "percentage": None, "match_confidence": 0.98, "known": True},
            {"id": "ing_7", "original": "Flavour enhancer (INS 631)", "normalized": "disodium inosinate", "category": "flavour_enhancer", "ins_number": "631", "percentage": None, "match_confidence": 0.98, "known": True},
            {"id": "ing_8", "original": "Colour (INS 102)", "normalized": "tartrazine", "category": "colour", "ins_number": "102", "percentage": None, "match_confidence": 0.95, "known": True},
            {"id": "ing_9", "original": "Preservative (INS 211)", "normalized": "sodium benzoate", "category": "preservative", "ins_number": "211", "percentage": None, "match_confidence": 0.95, "known": True},
            {"id": "ing_10", "original": "Spice extractives", "normalized": None, "category": None, "ins_number": None, "percentage": None, "match_confidence": 0.41, "known": False},
        ],
        "nutrition": {
            "basis": "per_100g", "energy_kcal": 452.0, "sugar_g": 3.4, "sodium_mg": 1240.0,
            "sat_fat_g": 8.2, "trans_fat_g": 0.1, "total_fat_g": 17.5, "protein_g": 9.1, "fiber_g": None,
        },
        "fssai_result": {
            "overall_status": "REVIEW",
            "summary": {"scanned": 10, "matched": 9, "pass": 6, "flag": 1, "review": 3},
            "confidence": 0.84,
            "findings": [
                {"ingredient_id": "ing_8", "rule_id": "MOCK-COLOUR-001", "status": "FLAG", "reason": "Mock: colour not permitted in this food category.", "source": mock_source},
                {"ingredient_id": "ing_9", "rule_id": "MOCK-PRES-001", "status": "PASS", "reason": "Mock: preservative permitted in this food category.", "source": mock_source},
                {"ingredient_id": "ing_6", "rule_id": "MOCK-FLAV-001", "status": "REVIEW", "reason": "Mock: permission depends on the food category; please verify.", "source": mock_source},
                {"ingredient_id": "ing_10", "rule_id": "UNKNOWN", "status": "REVIEW", "reason": "Ingredient not recognised; needs manual review.", "source": mock_source},
            ],
        },
        "health_result": {
            "score": 46,
            "assessment": "MODERATE",
            "data_completeness": 0.89,
            "factors": [
                {"key": "high_sodium", "type": "nutrient", "impact": -20.0, "label": "High sodium", "detail": "1240 mg sodium per 100 g is high."},
                {"key": "high_sat_fat", "type": "nutrient", "impact": -12.0, "label": "High saturated fat", "detail": "8.2 g saturated fat per 100 g."},
                {"key": "artificial_colour", "type": "ingredient", "impact": -8.0, "label": "Contains synthetic colour", "detail": "Tartrazine (INS 102) is listed."},
                {"key": "protein_ok", "type": "nutrient", "impact": 4.0, "label": "Some protein", "detail": "9.1 g protein per 100 g."},
            ],
            "disclaimer": "General information only. Not medical or dietary advice.",
        },
    }
