"""Pydantic models for every request/response. This is the contract with Flutter."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Status = Literal["PASS", "FLAG", "REVIEW"]
Assessment = Literal["FEWER CONCERNS", "MODERATE", "SEVERAL CONCERNS"]


# ---------- OCR ----------
class OcrInfo(BaseModel):
    raw_text: str
    confidence: float = Field(ge=0, le=1)
    engine: str  # e.g. "rapidocr", "rapidocr-original", "tesseract"


# ---------- Extraction ----------
class Ingredient(BaseModel):
    id: str
    original: str  # text as printed / OCR'd
    normalized: str | None = None  # canonical name after normalisation
    category: str | None = None  # e.g. "preservative", "colour"
    ins_number: str | None = None  # e.g. "211", "102"
    percentage: float | None = None  # if printed, e.g. 72.0
    match_confidence: float = Field(ge=0, le=1)
    known: bool  # False => not found in our rule data


class Nutrition(BaseModel):
    basis: str | None = None  # e.g. "per_100g"
    energy_kcal: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    sat_fat_g: float | None = None
    trans_fat_g: float | None = None
    total_fat_g: float | None = None
    protein_g: float | None = None
    fiber_g: float | None = None


# ---------- FSSAI (deterministic rules) ----------
class FssaiSummary(BaseModel):
    scanned: int
    matched: int
    pass_: int = Field(alias="pass")  # "pass" is a Python keyword
    flag: int
    review: int

    model_config = {"populate_by_name": True}


class Finding(BaseModel):
    ingredient_id: str
    rule_id: str
    status: Status
    reason: str
    source: str


class FssaiResult(BaseModel):
    overall_status: Status
    summary: FssaiSummary
    confidence: float = Field(ge=0, le=1)
    findings: list[Finding]


# ---------- Health assessment ----------
class HealthFactor(BaseModel):
    key: str  # stable id, e.g. "high_sugar"
    type: Literal["nutrient", "ingredient"]  # what triggered the factor
    impact: float  # score points; negative = concern, positive = good
    label: str  # short title for the UI
    detail: str  # one-line explanation


class HealthResult(BaseModel):
    score: int = Field(ge=0, le=100)
    assessment: Assessment
    data_completeness: float = Field(ge=0, le=1)
    factors: list[HealthFactor]
    disclaimer: str


# ---------- Request for /analyze ----------
class AnalyzeRequest(BaseModel):
    """Text-only analysis (no image). Send `ingredients_text` OR `ingredients`."""

    ingredients_text: str | None = Field(default=None, max_length=5000)
    ingredients: list[str] | None = Field(default=None, max_length=100)
    nutrition_text: str | None = Field(default=None, max_length=3000)
    food_category: str | None = None

    @model_validator(mode="after")
    def _need_ingredients(self):
        has_text = bool(self.ingredients_text and self.ingredients_text.strip())
        has_list = bool(self.ingredients and any(i.strip() for i in self.ingredients))
        if not (has_text or has_list):
            raise ValueError("Provide ingredients_text or a non-empty ingredients list.")
        return self


# ---------- Full response for /scan and /analyze ----------
class ScanResponse(BaseModel):
    scan_id: str
    created_at: str  # ISO-8601 UTC
    status: Literal["ok"] = "ok"
    warnings: list[str] = []
    ocr: OcrInfo | None = None  # null for /analyze (no image)
    food_category: str | None = None
    ingredients: list[Ingredient]
    nutrition: Nutrition
    fssai_result: FssaiResult
    health_result: HealthResult


# ---------- History ----------
class ScanSummary(BaseModel):
    """One row of GET /scans (the full result is at GET /scans/{scan_id})."""

    scan_id: str
    created_at: str
    food_category: str | None
    overall_status: Status
    health_score: int
    assessment: Assessment
    ingredient_count: int


class ScanListResponse(BaseModel):
    items: list[ScanSummary]
    total: int  # all scans for this device (for paging)
    limit: int
    offset: int


# ---------- Small endpoints ----------
class HealthCheck(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class Category(BaseModel):
    id: str
    name: str


class CategoriesResponse(BaseModel):
    categories: list[Category]


# ---------- Errors ----------
class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
