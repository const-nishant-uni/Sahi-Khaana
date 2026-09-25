"""App settings, loaded from environment variables / a .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# Confidence given to an INS number that matched only the broader base entry
# (e.g. "331(i)" -> "331 sodium citrates"). Deliberately below the default
# MATCH_CONFIDENCE_CUTOFF (0.90) so a PASS on such a match is downgraded to REVIEW.
BASE_INS_MATCH_CONFIDENCE = 0.85


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # --- Secrets (only ever come from .env / environment) ---
    groq_api_key: str | None = None
    # Small Llama on Groq (see https://console.groq.com/docs/models); override with GROQ_MODEL.
    groq_model: str = "llama-3.1-8b-instant"

    # --- Database ---
    database_url: str = f"sqlite:///{BASE_DIR / 'sahi_khaana.db'}"

    # --- Uploads ---
    upload_dir: Path = BASE_DIR / "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB
    image_retention_days: int = 7  # photos older than this are deleted at startup

    # --- Image preprocessing ---
    target_long_edge: int = 1600  # images larger than this are downscaled
    blur_threshold: float = 60.0  # Laplacian variance below this => POOR_IMAGE
    max_deskew_degrees: float = 15.0  # ignore skew estimates larger than this

    # --- Rule engine ---
    # A PASS whose ingredient match confidence is below this becomes REVIEW.
    match_confidence_cutoff: float = 0.90

    # --- OCR ---
    ocr_retry_confidence: float = 0.6  # below this, try the other engines too
    ocr_warn_confidence: float = 0.75  # below this, add LOW_OCR_CONFIDENCE


@lru_cache
def get_settings() -> Settings:
    return Settings()
