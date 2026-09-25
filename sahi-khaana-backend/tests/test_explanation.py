"""Explanation: template fallback, LLM path (httpx mocked), caching, device check.
No test here makes a real API call (see the autouse fixture in conftest.py)."""
import json

import httpx
import pytest
from sqlmodel import Session

from app.config import get_settings
from app.models import Scan
from app.schemas import Finding, FssaiResult, FssaiSummary, HealthFactor, HealthResult
from app.services import explanation as ex
from tests.conftest import DEVICE_A, DEVICE_B, headers

GOOD_TEXT = "The rule check needs review for some ingredients. The health view is moderate."


# ------------------------------------------------------------------ helpers
def fssai(findings=None, overall="REVIEW", counts=(4, 0, 3)):
    p, f, r = counts
    return FssaiResult(overall_status=overall, confidence=0.9, findings=findings or [],
                       summary=FssaiSummary(scanned=p + f + r, matched=p + f + r, pass_=p, flag=f, review=r))


def health(score=57, assessment="MODERATE", factors=()):
    return HealthResult(score=score, assessment=assessment, data_completeness="full", completeness_score=0.9,
                        factors=list(factors), disclaimer="d")


def finding(ing, status, reason, rule="R"):
    return Finding(ingredient_id=ing, rule_id=rule, status=status, reason=reason, source="s")


class FakeResponse:
    def __init__(self, content=GOOD_TEXT, status=200, raw=None):
        self.status, self._raw = status, raw if raw is not None else {"choices": [{"message": {"content": content}}]}

    def raise_for_status(self):
        if self.status >= 400:
            raise httpx.HTTPStatusError("boom", request=httpx.Request("POST", ex.GROQ_URL),
                                        response=httpx.Response(self.status))

    def json(self):
        return self._raw


@pytest.fixture
def groq(monkeypatch):
    """Configure a key and record calls to the mocked httpx.post. Set groq.response / groq.error."""
    monkeypatch.setattr(get_settings(), "groq_api_key", "test-key")
    monkeypatch.setattr(get_settings(), "groq_model", "test-model")

    class Groq:
        calls: list = []
        response = FakeResponse()
        error: Exception | None = None

    Groq.calls = []

    def fake_post(url, **kwargs):
        Groq.calls.append({"url": url, **kwargs})
        if Groq.error:
            raise Groq.error
        return Groq.response

    monkeypatch.setattr(ex.httpx, "post", fake_post)
    return Groq


# ------------------------------------------------------------------ template
def test_template_used_without_api_key():
    r = ex.generate_explanation(fssai(), health(), [])
    assert r.source == "template" and r.text  # httpx.post is blocked by conftest: proves no call was made


def test_template_content_from_reasons_and_factors():
    findings = [finding("ing_1", "FLAG", "Ponceau 4R is not permitted."),
                finding("ing_2", "REVIEW", "No verified rule for tartrazine in category 'bakery'."),
                finding("ing_3", "PASS", "Sugar is permitted.")]
    text = ex.template_explanation(
        fssai(findings, "FLAG", (1, 1, 1)),
        health(57, "MODERATE", [HealthFactor(key="k", type="nutrient", impact=-20, label="High sodium", detail="d")]), [])
    assert "FLAG" in text and "1 were flagged" in text and "1 need review" in text
    assert "Ponceau 4R is not permitted" in text and "No verified rule for tartrazine" in text
    assert "Sugar is permitted" not in text  # passing reasons are not listed
    assert "57/100" in text and "moderate" in text and "High sodium" in text
    assert "not medical or compliance advice" in text


def test_template_explains_label_level_review():
    text = ex.template_explanation(fssai([finding(None, "REVIEW", "Declaration not found in the scanned area")]), health(), [])
    assert "declaration was not found in the scanned area" in text
    assert "declaration" not in ex.template_explanation(fssai([finding("ing_1", "PASS", "ok")]), health(), [])


def test_template_mentions_limited_nutrition_data_only_when_warned():
    assert "Nutrition data was limited" in ex.template_explanation(fssai(), health(), ["LIMITED_NUTRITION_DATA"])
    assert "Nutrition data was limited" not in ex.template_explanation(fssai(), health(), [])
    assert "per-serving" in ex.template_explanation(fssai(), health(), ["NUTRITION_PER_SERVING_ONLY"])


def test_template_caps_long_reason_lists():
    findings = [finding(f"ing_{i}", "REVIEW", f"Reason {i}.") for i in range(6)]
    text = ex.template_explanation(fssai(findings, "REVIEW", (0, 0, 6)), health(), [])
    assert "Reason 0" in text and "Reason 1" in text and "Reason 2" not in text and "and 4 more" in text


def test_template_never_contradicts_the_status():
    text = ex.template_explanation(fssai(overall="FLAG", counts=(0, 2, 0)), health(), [])
    assert "FLAG" in text and "PASS." not in text


# ------------------------------------------------------------------ LLM path (mocked)
def test_llm_text_is_used_when_the_call_works(groq):
    r = ex.generate_explanation(fssai(), health(), [])
    assert (r.text, r.source, r.cacheable) == (GOOD_TEXT, "llm", True) and len(groq.calls) == 1


def test_template_without_key_is_cacheable():
    r = ex.generate_explanation(fssai(), health(), [])
    assert r.source == "template" and r.cacheable is True


def test_request_shape_key_model_timeout(groq):
    ex.generate_explanation(fssai(), health(), [])
    call = groq.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer test-key"
    assert call["timeout"] == 10.0
    assert call["json"]["max_completion_tokens"] == 250
    assert call["json"]["model"] == "test-model"  # from settings/env, not hard-coded
    assert [m["role"] for m in call["json"]["messages"]] == ["system", "user"]


def test_model_comes_from_settings(groq, monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_model", "another-model")
    ex.generate_explanation(fssai(), health(), [])
    assert groq.calls[0]["json"]["model"] == "another-model"


def test_llm_receives_only_fssai_health_and_warnings(groq):
    ex.generate_explanation(fssai([finding("ing_1", "REVIEW", "why")]), health(), ["LIMITED_NUTRITION_DATA"])
    user = groq.calls[0]["json"]["messages"][1]["content"]
    data = json.loads(user.split("\n", 1)[1])
    assert set(data) == {"fssai_result", "health_result", "warnings"}
    assert data["warnings"] == ["LIMITED_NUTRITION_DATA"]
    assert data["fssai_result"]["summary"]["pass"] == 4  # serialised with the API's field names
    assert "raw_text" not in user and "ingredients" not in data  # nothing else leaks in


def test_system_prompt_carries_the_required_rules():
    p = ex.SYSTEM_PROMPT
    assert "under 120 words" in p and "plain English" in p
    assert "NEVER change" in p and "contradict any status" in p
    assert "medical" in p and "compliance" in p
    assert "ingredient_id is null" in p and "declaration was not found in the scanned area" in p
    assert "LIMITED_NUTRITION_DATA" in p


@pytest.mark.parametrize("failure", [
    httpx.ReadTimeout("slow"), httpx.ConnectError("no network"), RuntimeError("anything"),
])
def test_exceptions_fall_back_to_template(groq, failure):
    groq.error = failure
    r = ex.generate_explanation(fssai(), health(), [])
    assert r.source == "template" and "FSSAI rule check" in r.text and r.cacheable is False


@pytest.mark.parametrize("response", [
    FakeResponse(status=401), FakeResponse(status=429), FakeResponse(status=500),  # API errors
    FakeResponse(raw={"error": "x"}),  # unexpected JSON shape
    FakeResponse(raw={"choices": []}),
    FakeResponse(content=""), FakeResponse(content="   "),  # empty answer
    FakeResponse(content="word " * 121),  # over the word limit
])
def test_bad_responses_fall_back_to_template(groq, response):
    groq.response = response
    r = ex.generate_explanation(fssai(), health(), [])
    assert r.source == "template" and r.cacheable is False


def test_answer_of_exactly_120_words_is_accepted(groq):
    groq.response = FakeResponse(content="word " * 120)
    assert ex.generate_explanation(fssai(), health(), []).source == "llm"


def test_api_key_never_appears_in_the_prompt(groq):
    ex.generate_explanation(fssai(), health(), [])
    assert "test-key" not in json.dumps(groq.calls[0]["json"])


# ------------------------------------------------------------------ endpoint: caching + device check
BODY = {"ingredients_text": "Wheat flour (72%), Salt, Colour (INS 102)", "nutrition_text": "Sodium 900 mg"}


def make_scan(client, device=DEVICE_A):
    r = client.post("/api/v1/analyze", headers=headers(device), json=BODY)
    assert r.status_code == 200
    return r.json()["scan_id"]


def fetch(client, scan_id, device=DEVICE_A):
    return client.get(f"/api/v1/scans/{scan_id}/explanation", headers=headers(device))


def test_endpoint_returns_template_without_key(client):
    r = fetch(client, make_scan(client))
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"explanation", "source"} and body["source"] == "template" and "FSSAI rule check" in body["explanation"]


def test_endpoint_returns_llm_text_and_caches_it(client, groq, db_engine):
    sid = make_scan(client)
    first, second, third = fetch(client, sid).json(), fetch(client, sid).json(), fetch(client, sid).json()
    assert first == second == third == {"explanation": GOOD_TEXT, "source": "llm"}
    assert len(groq.calls) == 1  # the LLM is called once, ever
    with Session(db_engine) as s:
        scan = s.get(Scan, sid)
        assert scan.explanation == GOOD_TEXT and scan.explanation_source == "llm"


FAILURES = {
    "timeout": lambda g: setattr(g, "error", httpx.ReadTimeout("slow")),
    "connection error": lambda g: setattr(g, "error", httpx.ConnectError("down")),
    "http 500": lambda g: setattr(g, "response", FakeResponse(status=500)),
    "http 429": lambda g: setattr(g, "response", FakeResponse(status=429)),
    "empty answer": lambda g: setattr(g, "response", FakeResponse(content="")),
    "over 120 words": lambda g: setattr(g, "response", FakeResponse(content="word " * 121)),
}


@pytest.mark.parametrize("failure", list(FAILURES))
def test_llm_failure_returns_template_but_is_not_cached(client, groq, db_engine, failure):
    FAILURES[failure](groq)
    sid = make_scan(client)
    r = fetch(client, sid)
    assert r.status_code == 200 and r.json()["source"] == "template" and "FSSAI rule check" in r.json()["explanation"]
    with Session(db_engine) as s:
        scan = s.get(Scan, sid)
        assert scan.explanation is None and scan.explanation_source is None  # nothing cached
    assert len(groq.calls) == 1


def test_next_request_retries_the_llm_after_a_failure_and_then_caches(client, groq, db_engine):
    groq.error = httpx.ReadTimeout("slow")
    sid = make_scan(client)
    assert fetch(client, sid).json()["source"] == "template"
    assert fetch(client, sid).json()["source"] == "template"  # still failing: retried, still not cached
    assert len(groq.calls) == 2

    groq.error = None  # the API recovers
    recovered = fetch(client, sid).json()
    assert recovered == {"explanation": GOOD_TEXT, "source": "llm"} and len(groq.calls) == 3
    assert fetch(client, sid).json() == recovered and len(groq.calls) == 3  # now cached: no more calls
    with Session(db_engine) as s:
        assert s.get(Scan, sid).explanation_source == "llm"


def test_a_cached_llm_answer_is_never_replaced(client, groq):
    sid = make_scan(client)
    first = fetch(client, sid).json()
    groq.error = httpx.ReadTimeout("slow")  # would fail if it were called again
    assert fetch(client, sid).json() == first and len(groq.calls) == 1


def test_each_scan_gets_its_own_explanation_call(client, groq):
    fetch(client, make_scan(client))
    fetch(client, make_scan(client))
    assert len(groq.calls) == 2


def test_no_key_means_no_llm_call_and_template_is_cached(client, db_engine):
    sid = make_scan(client)
    assert fetch(client, sid).json() == fetch(client, sid).json()
    with Session(db_engine) as s:
        scan = s.get(Scan, sid)
        assert scan.explanation_source == "template" and scan.explanation  # cached: there is nothing to retry


def test_adding_a_key_later_does_not_replace_a_cached_no_key_template(client, groq, monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", None)
    sid = make_scan(client)
    first = fetch(client, sid).json()
    monkeypatch.setattr(get_settings(), "groq_api_key", "test-key")
    assert fetch(client, sid).json() == first and groq.calls == []


def test_other_device_gets_404_and_no_llm_call(client, groq):
    sid = make_scan(client)
    r = fetch(client, sid, device=DEVICE_B)
    assert r.status_code == 404 and r.json()["error"]["code"] == "SCAN_NOT_FOUND"
    assert groq.calls == []  # the check happens before anything is generated
    assert fetch(client, sid).status_code == 200  # the owner is unaffected


def test_other_device_cannot_read_a_cached_explanation(client, groq):
    sid = make_scan(client)
    fetch(client, sid)
    assert fetch(client, sid, device=DEVICE_B).status_code == 404


def test_unknown_scan_and_missing_header(client, groq):
    r = fetch(client, "does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "SCAN_NOT_FOUND"
    r = client.get("/api/v1/scans/x/explanation")
    assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_DEVICE_ID"
    assert groq.calls == []


def test_deleting_a_scan_removes_its_explanation(client, groq):
    """Deleting a scan removes its explanation too (it lives on the scan row)."""
    sid = make_scan(client)
    fetch(client, sid)
    client.delete(f"/api/v1/scans/{sid}", headers=headers())
    assert fetch(client, sid).status_code == 404
