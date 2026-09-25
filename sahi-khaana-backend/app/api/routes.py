"""All HTTP endpoints, mounted under /api/v1 in main.py."""
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile

from app.errors import AppError
from app.schemas import AnalyzeRequest, CategoriesResponse, ErrorResponse, HealthCheck, ScanResponse
from app.services import scan_service

router = APIRouter()

# Error shapes, so /docs shows them for the Flutter developer.
_ERRORS = {
    400: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def get_device_id(x_device_id: str | None = Header(default=None)) -> str | None:
    """Every Flutter request sends X-Device-Id (a UUID) instead of a login.

    Phase 1: optional (so curl/Swagger testing is easy), but validated if present.
    TODO(Phase 3): make it required on the history endpoints.
    """
    if x_device_id is None:
        return None
    try:
        uuid.UUID(x_device_id)
    except ValueError:
        raise AppError("INVALID_DEVICE_ID", "X-Device-Id must be a UUID.", 400)
    return x_device_id


@router.get("/health", response_model=HealthCheck)
def health():
    return HealthCheck(version="0.1.0")


@router.get("/categories", response_model=CategoriesResponse)
def categories():
    """Food categories for the dropdown in the app."""
    return {"categories": scan_service.load_categories()}


@router.post("/scan", response_model=ScanResponse, responses=_ERRORS)
def scan(
    image: UploadFile = File(..., description="JPG/PNG/WEBP photo of the ingredient label, max 5 MB"),
    food_category: str | None = Form(default=None, description="A category id from GET /categories"),
    device_id: str | None = Depends(get_device_id),
):
    """Photo -> preprocessing -> OCR -> analysis.

    Phase 2: `ocr`, `ingredients` and `nutrition` are real.
    `fssai_result` / `health_result` are still placeholders (MOCK_DATA warning).
    (Plain `def`, so FastAPI runs this CPU-heavy work in a worker thread.)
    """
    return scan_service.process_scan(image, food_category)


@router.post("/analyze", response_model=ScanResponse, responses=_ERRORS)
def analyze(body: AnalyzeRequest, device_id: str | None = Depends(get_device_id)):
    """Same analysis as /scan but from typed/pasted text (no image, `ocr` is null).

    Handy for testing the parser and for a "type the ingredients" screen in the app.
    """
    return scan_service.analyze_text(body)


@router.get("/mock/scan", response_model=ScanResponse)
def mock_scan():
    """A fixed, realistic sample response so the Flutter app can be built now."""
    return ScanResponse.model_validate(scan_service.build_mock_analysis())
