"""FastAPI entry point.

Run:  uvicorn app.main:app --reload --host 0.0.0.0
Docs: http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.config import get_settings
from app.database import init_db
from app.errors import AppError
from app.pipeline.ocr import get_rapidocr

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sahi-khaana")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    get_rapidocr()  # load OCR models now so the first scan isn't slow
    log.info("Startup complete")
    yield


app = FastAPI(title="Sahi Khaana API", version="0.1.0", lifespan=lifespan)

# CORS: allow everything. DEV ONLY. Restrict before any real deployment.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(router, prefix="/api/v1")


# ---------- global error handlers: always {"error": {"code", "message"}} ----------
def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError):
    return _error(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    if field == "image":  # missing upload field
        return _error(400, "INVALID_FILE", "No image was uploaded (form field 'image').")
    msg = first["msg"].removeprefix("Value error, ")
    return _error(422, "VALIDATION_ERROR", f"{field}: {msg}" if field else msg)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(_: Request, exc: StarletteHTTPException):
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def handle_unexpected(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return _error(500, "INTERNAL_ERROR", "Something went wrong on the server.")
