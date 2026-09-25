"""Preprocessing tests: small-text upscaling (MIN_TEXT_HEIGHT_PX) and the spacing it protects."""
import cv2
import numpy as np
import pytest

from app.config import get_settings
from app.errors import AppError
from app.pipeline.ocr import run_ocr
from app.pipeline.preprocessing import UPSCALE_FACTOR, estimate_text_height, preprocess

LINES = ["INGREDIENTS: Refined wheat flour (72%), Palm oil, Salt, Sugar,",
         "Acidity regulator (INS 501(i)), Flavour enhancer (INS 627,",
         "INS 631), Colour (INS 102), Preservative (INS 211)."]


def label(scale: float, width: int = 1500) -> np.ndarray:
    """A synthetic ingredient label; `scale` sets the font size (0.9 gives ~27 px text lines)."""
    line_height = int(50 * scale) + 30
    img = np.full((line_height * len(LINES) + 40, width, 3), 255, np.uint8)
    for i, text in enumerate(LINES):
        cv2.putText(img, text, (30, line_height * (i + 1)), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0),
                    max(1, round(scale * 2)), cv2.LINE_AA)
    return img


def gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# ------------------------------------------------------------------ estimate
def test_text_height_grows_with_font_size():
    small, medium, large = (estimate_text_height(gray(label(s))) for s in (0.6, 0.9, 1.5))
    assert 0 < small < medium < large


def test_text_height_is_in_the_expected_ballpark():
    assert 22 <= estimate_text_height(gray(label(0.9))) <= 32
    assert 40 <= estimate_text_height(gray(label(1.5)))


def test_text_height_of_a_blank_image_is_zero():
    assert estimate_text_height(np.full((300, 600), 255, np.uint8)) == 0.0


def test_text_height_ignores_specks_and_tall_shapes():
    img = np.full((400, 800), 255, np.uint8)
    cv2.rectangle(img, (100, 50), (110, 350), 0, -1)  # a tall thin bar: not a text line
    img[10:12, 10:12] = 0  # a speck
    assert estimate_text_height(img) == 0.0


# ------------------------------------------------------------------ upscaling decision
def test_small_text_is_upscaled_2x_for_both_images():
    r = preprocess(label(0.9))
    assert r.upscaled is True and 22 <= r.text_height_px <= 32
    h, w = label(0.9).shape[:2]
    assert r.original_resized.shape[:2] == (h * UPSCALE_FACTOR, w * UPSCALE_FACTOR)
    assert r.processed.shape == r.original_resized.shape[:2]


def test_large_text_is_left_alone():
    r = preprocess(label(1.5))
    assert r.upscaled is False and r.original_resized.shape[:2] == label(1.5).shape[:2]


def test_threshold_is_config_driven(monkeypatch):
    monkeypatch.setattr(get_settings(), "min_text_height_px", 0)  # feature off
    assert preprocess(label(0.9)).upscaled is False
    monkeypatch.setattr(get_settings(), "min_text_height_px", 1000)  # everything counts as small
    assert preprocess(label(1.5)).upscaled is True


def test_default_threshold_is_30(monkeypatch):
    from app.config import Settings
    monkeypatch.delenv("MIN_TEXT_HEIGHT_PX", raising=False)
    assert Settings(_env_file=None).min_text_height_px == 30.0
    monkeypatch.setenv("MIN_TEXT_HEIGHT_PX", "20")
    assert Settings(_env_file=None).min_text_height_px == 20.0


def test_no_text_no_upscale(monkeypatch):
    monkeypatch.setattr(get_settings(), "blur_threshold", 0)  # let a featureless image through
    r = preprocess(np.full((300, 600, 3), 255, np.uint8))
    assert r.text_height_px == 0.0 and r.upscaled is False


def test_blur_check_still_judges_the_photo_as_taken():
    with pytest.raises(AppError) as err:
        preprocess(cv2.GaussianBlur(label(0.9), (0, 0), 8))
    assert err.value.code == "POOR_IMAGE"


def test_upscaling_uses_cubic_interpolation(monkeypatch):
    calls = []
    real_resize = cv2.resize
    monkeypatch.setattr(cv2, "resize", lambda *a, **k: (calls.append(k.get("interpolation")), real_resize(*a, **k))[1])
    preprocess(label(0.9))
    assert cv2.INTER_CUBIC in calls


# ------------------------------------------------------------------ what it is for
def read(img):
    pre = preprocess(img)
    return run_ocr(pre.processed, pre.original_resized).raw_text


def test_small_text_keeps_its_word_spaces_after_upscaling():
    text = read(label(0.9))
    assert "Refined wheat flour" in text and "Palm oil" in text  # the spaces survived


@pytest.mark.parametrize("scale", [0.7, 0.9])
def test_upscaling_cuts_the_word_error_rate_on_small_text(monkeypatch, scale):
    """Measured on rendered labels: WER 0.96 -> 0.28 (scale 0.7) and 0.52 -> 0.12 (scale 0.9)."""
    from jiwer import wer

    def norm(text):
        return " ".join(text.lower().split())

    truth = norm("\n".join(LINES))
    with_upscaling = wer(truth, norm(read(label(scale))))
    monkeypatch.setattr(get_settings(), "min_text_height_px", 0)
    without = wer(truth, norm(read(label(scale))))
    assert with_upscaling < without / 2
