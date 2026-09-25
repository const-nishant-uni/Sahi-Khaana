"""All HTTP endpoints, mounted under /api/v1 in main.py."""
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from sqlmodel import Session

from app.database import get_session
from app.errors import AppError
from app.schemas import (
    AnalyzeRequest, CategoriesResponse, ErrorResponse, ExplanationResponse, HealthCheck, ScanListResponse, ScanResponse,
)
from app.services import scan_service

router = APIRouter()

# Error shapes, so /docs shows them for the Flutter developer.
_ERRORS = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def get_device_id(x_device_id: str | None = Header(default=None)) -> str:
    """Every Flutter request sends X-Device-Id (a UUID) instead of a login.

    It scopes scan history, so it is required on every endpoint that creates or reads scans.
    """
    if not x_device_id:
        raise AppError("MISSING_DEVICE_ID", "The X-Device-Id header is required.", 400)
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
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
):
    """Photo -> preprocessing -> OCR -> extraction -> FSSAI check + health assessment. Saved to history.

    (Plain `def`, so FastAPI runs this CPU-heavy work in a worker thread.)
    """
    return scan_service.process_scan(session, device_id, image, food_category)


@router.post("/analyze", response_model=ScanResponse, responses=_ERRORS)
def analyze(
    body: AnalyzeRequest,
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
):
    """Same analysis as /scan but from typed/pasted text (no image, `ocr` is null). Saved to history."""
    return scan_service.analyze_text(session, device_id, body)


@router.get("/scans", response_model=ScanListResponse, responses=_ERRORS)
def list_scans(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
):
    """This device's scan history, newest first."""
    return scan_service.list_scans(session, device_id, limit, offset)


@router.get("/scans/{scan_id}", response_model=ScanResponse, responses=_ERRORS)
def get_scan(
    scan_id: str,
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
):
    """The full stored result of one scan."""
    return scan_service.get_scan(session, device_id, scan_id)


@router.get("/scans/{scan_id}/explanation", response_model=ExplanationResponse, responses=_ERRORS)
def get_explanation(
    scan_id: str,
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
):
    """Plain-English explanation of a scan. Generated on first request, then cached.

    `source` is "llm" (worded by an AI from the rule results) or "template" (built directly
    from them: no API key, or the AI call failed). Neither ever changes a status.
    """
    return scan_service.get_explanation(session, device_id, scan_id)


@router.delete("/scans/{scan_id}", status_code=204, response_class=Response, responses=_ERRORS)
def delete_scan(
    scan_id: str,
    device_id: str = Depends(get_device_id),
    session: Session = Depends(get_session),
):
    """Delete a scan, its stored data and its image."""
    scan_service.delete_scan(session, device_id, scan_id)
    return Response(status_code=204)


@router.get("/mock/scan", response_model=ScanResponse)
def mock_scan():
    """A fixed, realistic sample response so the Flutter app can be built now."""
    return ScanResponse.model_validate(scan_service.build_mock_analysis())
