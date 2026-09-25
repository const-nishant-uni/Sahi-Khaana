"""OpenCV preprocessing: make a phone photo of a label easier for OCR.

Steps: resize -> blur check -> grayscale -> CLAHE -> denoise -> deskew -> (upscale small text).
The upscale comes last so the expensive denoising runs on the normal-size image.
"""
from dataclasses import dataclass
from statistics import median

import cv2
import numpy as np

from app.config import get_settings
from app.errors import invalid_file, poor_image


@dataclass
class PreprocessResult:
    processed: np.ndarray  # grayscale, enhanced, deskewed (main OCR input)
    original_resized: np.ndarray  # BGR, only resized (fallback OCR input)
    blur_score: float  # Laplacian variance (higher = sharper)
    deskew_angle: float  # degrees applied (0.0 if skipped)
    text_height_px: float = 0.0  # estimated median text-line height before any upscaling (0 = no text found)
    upscaled: bool = False  # True if both images were enlarged 2x because the text was small


def decode_image(data: bytes) -> np.ndarray:
    """Decode bytes into a BGR image. OpenCV applies EXIF rotation for us."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise invalid_file("The file could not be decoded as an image.")
    return img


def _resize_long_edge(img: np.ndarray, target: int) -> np.ndarray:
    """Downscale so the long edge is `target` px. Small images are left alone
    (upscaling adds no detail and would make the blur check misleading)."""
    h, w = img.shape[:2]
    long_edge = max(h, w)
    if long_edge <= target:
        return img
    scale = target / long_edge
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)


UPSCALE_FACTOR = 2


def _upscale(img: np.ndarray) -> np.ndarray:
    return cv2.resize(img, None, fx=UPSCALE_FACTOR, fy=UPSCALE_FACTOR, interpolation=cv2.INTER_CUBIC)


def estimate_text_height(gray: np.ndarray) -> float:
    """Cheap estimate of the median text-line height in pixels (0.0 if no text-like blobs).

    Binarise, smear the letters horizontally so each word/line becomes one blob (vertical
    gaps between lines stay open), and take the median height of the wide blobs.
    """
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel_width = max(5, int(0.02 * gray.shape[1]))
    merged = cv2.dilate(bw, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, 1)))
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    heights = []
    for contour in contours:
        _, _, w, h = cv2.boundingRect(contour)
        if h >= 4 and w >= 2 * h:  # ignore specks and tall/narrow shapes (not text lines)
            heights.append(h)
    return float(median(heights)) if heights else 0.0


def _estimate_skew(gray: np.ndarray) -> float:
    """Estimate text skew in degrees using minAreaRect over the dark (text) pixels.

    Returns the correction in degrees, in (-45, 45], using OpenCV's convention
    (positive = rotate counter-clockwise) - pass it straight to `_rotate`.
    """
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    points = cv2.findNonZero(bw)  # (x, y) coordinates of text pixels
    if points is None or len(points) < 100:
        return 0.0
    (_, _), (w, h), angle = cv2.minAreaRect(points)
    # Normalise to (-45, 45]. Also handle a swapped width/height.
    if w < h:
        angle = angle - 90 if angle > 0 else angle + 90
    while angle > 45:
        angle -= 90
    while angle <= -45:
        angle += 90
    return float(angle)


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess(image_bgr: np.ndarray) -> PreprocessResult:
    """Run the full pipeline. Raises POOR_IMAGE if the photo is too blurry."""
    cfg = get_settings()

    resized = _resize_long_edge(image_bgr, cfg.target_long_edge)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # Blur check: sharp text has strong edges => high Laplacian variance.
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < cfg.blur_threshold:
        raise poor_image(
            "The photo is too blurry to read. Hold the phone steady and retake it."
        )

    # Small text? (decided now, on the photo as taken; applied after the cleanup below)
    text_height = estimate_text_height(gray)
    upscaled = 0 < text_height < cfg.min_text_height_px

    # CLAHE evens out uneven lighting / glare; then remove noise.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.fastNlMeansDenoising(enhanced, None, h=10, templateWindowSize=7, searchWindowSize=21)

    # Deskew only for small, believable angles (large ones are usually a bad estimate).
    angle = _estimate_skew(denoised)
    if 0.5 <= abs(angle) <= cfg.max_deskew_degrees:
        denoised = _rotate(denoised, angle)
    else:
        angle = 0.0

    # OCR loses word spaces on small text, so enlarge both images before recognition.
    if upscaled:
        denoised = _upscale(denoised)
        resized = _upscale(resized)

    return PreprocessResult(
        processed=denoised,
        original_resized=resized,
        blur_score=blur_score,
        deskew_angle=angle,
        text_height_px=text_height,
        upscaled=upscaled,
    )
