"""Plain-English explanation of a scan result.

The LLM (Groq) only PHRASES what the rule engines already decided. It receives just
`fssai_result`, `health_result` and `warnings`, is told never to change a status, and
its answer is thrown away (template used instead) if the call fails, times out, or
comes back empty or over the word limit. With no API key the template is always used.

Caching (done by the caller, see `Explanation.cacheable`): an LLM answer is cached, and so is
the template when no key is configured (there is nothing to retry). A template that is only
a FALLBACK after a failed LLM call is not cached, so the next request tries the LLM again.
"""
import json
import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.schemas import FssaiResult, HealthResult

log = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_SECONDS = 10.0
MAX_WORDS = 120
MAX_TOKENS = 250

SYSTEM_PROMPT = """You explain the result of a packaged-food label check to an ordinary shopper.
You receive JSON with `fssai_result`, `health_result` and `warnings`, all produced by a rule engine.

Rules:
- Write plain English in under 120 words. Plain text only: no markdown, no headings.
- NEVER change, soften or contradict any status (PASS, FLAG, REVIEW), score or assessment. Report them exactly as given.
- Do NOT make medical claims or give dietary advice. Do NOT make legal or compliance claims: never say a product is legal, illegal, safe, unsafe, compliant or non-compliant.
- A finding whose ingredient_id is null is about the label as a whole. A REVIEW one means the required declaration was not found in the scanned area of the label (the pack itself may still carry it). Explain that in one sentence.
- If `warnings` contains LIMITED_NUTRITION_DATA, say the health view is limited because little or no usable nutrition data was read.
- Use only facts present in the JSON. Do not invent ingredients, numbers or rules."""


@dataclass
class Explanation:
    text: str
    source: str  # "llm" | "template"
    cacheable: bool = True  # False for a template returned only because the LLM call failed


# ---------------------------------------------------------------- template (no AI)
def _shorten(reason: str) -> str:
    return reason.strip().rstrip(".")


def template_explanation(fssai: FssaiResult, health: HealthResult, warnings: list[str]) -> str:
    """Deterministic explanation built from the finding reasons and factor labels."""
    s = fssai.summary
    parts = [
        f"FSSAI rule check: {fssai.overall_status}. Of {s.scanned} ingredients, "
        f"{s.pass_} passed, {s.flag} were flagged and {s.review} need review."
    ]

    ingredient_findings = [f for f in fssai.findings if f.ingredient_id is not None]
    for status, intro in (("FLAG", "Flagged"), ("REVIEW", "Needs review")):
        reasons = [_shorten(f.reason) for f in ingredient_findings if f.status == status]
        if reasons:
            shown = "; ".join(reasons[:2])
            more = f" (and {len(reasons) - 2} more)" if len(reasons) > 2 else ""
            parts.append(f"{intro}: {shown}{more}.")

    if any(f.ingredient_id is None for f in fssai.findings):
        parts.append("A required declaration was not found in the scanned area, so check the pack itself.")

    line = f"Health view: score {health.score}/100, {health.assessment.lower()}."
    if health.factors:
        line += " Main factors: " + ", ".join(f.label for f in health.factors[:4]) + "."
    parts.append(line)

    if "LIMITED_NUTRITION_DATA" in warnings:
        parts.append("Nutrition data was limited, so the health view rests mostly on the ingredient list.")
    if "NUTRITION_PER_SERVING_ONLY" in warnings:
        parts.append("Only a per-serving nutrition table was found, so it was not scored.")
    if "LOW_OCR_CONFIDENCE" in warnings:
        parts.append("The photo was hard to read, so please double-check the text.")

    parts.append("This is general information, not medical or compliance advice.")
    return " ".join(parts)


# ---------------------------------------------------------------- LLM
def _llm_input(fssai: FssaiResult, health: HealthResult, warnings: list[str]) -> dict:
    """The ONLY data the model sees."""
    return {
        "fssai_result": fssai.model_dump(by_alias=True),
        "health_result": health.model_dump(),
        "warnings": warnings,
    }


def _call_groq(api_key: str, model: str, data: dict) -> str:
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.2,
            "max_completion_tokens": MAX_TOKENS,  # Groq's name for the (older) max_tokens
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Explain this result:\n" + json.dumps(data)},
            ],
        },
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def generate_explanation(fssai: FssaiResult, health: HealthResult, warnings: list[str]) -> Explanation:
    """LLM wording when a key is configured and the call works, otherwise the template."""
    cfg = get_settings()
    text_template = template_explanation(fssai, health, warnings)
    if not cfg.groq_api_key:
        return Explanation(text_template, "template", cacheable=True)  # no key: nothing to retry
    fallback = Explanation(text_template, "template", cacheable=False)  # LLM was expected: retry next time

    try:
        text = _call_groq(cfg.groq_api_key, cfg.groq_model, _llm_input(fssai, health, warnings))
    except Exception as exc:  # timeout, network, HTTP error, unexpected JSON... all handled the same
        log.warning("Groq explanation failed (%s); using template", type(exc).__name__)
        return fallback

    if not text or len(text.split()) > MAX_WORDS:
        log.warning("Groq explanation empty or over %d words; using template", MAX_WORDS)
        return fallback
    return Explanation(text, "llm", cacheable=True)
