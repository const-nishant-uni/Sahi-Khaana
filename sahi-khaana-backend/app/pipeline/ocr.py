"""OCR with RapidOCR (PaddleOCR models on ONNX) and a Tesseract fallback."""
import logging
from dataclasses import dataclass
from functools import lru_cache
from statistics import median

import numpy as np

from app.config import get_settings
from app.errors import no_text_found

log = logging.getLogger(__name__)


@dataclass
class OcrResult:
    raw_text: str
    confidence: float  # 0..1, weighted by text length
    engine: str


@lru_cache(maxsize=1)
def get_rapidocr():
    """Load the RapidOCR models once (takes a second or two)."""
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _weighted_confidence(items: list[tuple[str, float]]) -> float:
    """Mean confidence where long lines count more than short noisy ones."""
    total = sum(len(text) for text, _ in items)
    if total == 0:
        return 0.0
    return sum(len(text) * conf for text, conf in items) / total


def _run_rapidocr(img: np.ndarray, engine_name: str) -> OcrResult | None:
    result, _ = get_rapidocr()(img)
    if not result:
        return None

    # Each item: [4 corner points, text, score]. Reduce to (x_left, y_center, height, text, score).
    lines = []
    for box, text, score in result:
        text = str(text).strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append((min(xs), sum(ys) / 4, max(ys) - min(ys), text, float(score)))
    if not lines:
        return None

    # Group boxes into visual rows (similar y-center), then read each row left->right.
    row_tolerance = 0.5 * median(h for _, _, h, _, _ in lines)
    lines.sort(key=lambda l: l[1])
    rows: list[list[tuple]] = []
    for line in lines:
        if rows and abs(line[1] - median(r[1] for r in rows[-1])) <= row_tolerance:
            rows[-1].append(line)
        else:
            rows.append([line])

    text_rows = [" ".join(l[3] for l in sorted(row, key=lambda l: l[0])) for row in rows]
    confidence = _weighted_confidence([(l[3], l[4]) for l in lines])
    return OcrResult("\n".join(text_rows), confidence, engine_name)


def _run_tesseract(img: np.ndarray) -> OcrResult | None:
    """Fallback engine. Returns None if Tesseract isn't installed."""
    try:
        import pytesseract
        from pytesseract import Output

        data = pytesseract.image_to_data(img, lang="eng", config="--psm 6", output_type=Output.DICT)
    except Exception as exc:  # binary missing, bad language data, ...
        log.warning("Tesseract fallback unavailable: %s", exc)
        return None

    # Group words into lines using Tesseract's own block/paragraph/line numbers.
    grouped: dict[tuple, list[tuple[str, float]]] = {}
    for i, word in enumerate(data["text"]):
        word = word.strip()
        conf = float(data["conf"][i])
        if not word or conf < 0:  # conf -1 = not a word
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        grouped.setdefault(key, []).append((word, conf / 100))
    if not grouped:
        return None

    text_rows = [" ".join(w for w, _ in words) for _, words in sorted(grouped.items())]
    confidence = _weighted_confidence([w for words in grouped.values() for w in words])
    return OcrResult("\n".join(text_rows), confidence, "tesseract")


def run_ocr(processed: np.ndarray, original_resized: np.ndarray) -> OcrResult:
    """OCR the preprocessed image; if that's weak, try other options and keep the best.

    Raises NO_TEXT_FOUND if nothing readable comes out of any engine.
    """
    cfg = get_settings()
    candidates: list[OcrResult] = []

    first = _run_rapidocr(processed, "rapidocr")
    if first:
        candidates.append(first)

    if first is None or first.confidence < cfg.ocr_retry_confidence:
        # Preprocessing can hurt as well as help, so also try the untouched image,
        # and Tesseract on the preprocessed one.
        for attempt in (
            _run_rapidocr(original_resized, "rapidocr-original"),
            _run_tesseract(processed),
        ):
            if attempt:
                candidates.append(attempt)

    candidates = [c for c in candidates if c.raw_text.strip()]
    if not candidates:
        raise no_text_found()
    return max(candidates, key=lambda c: c.confidence)
