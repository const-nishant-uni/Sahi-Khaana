"""API tests for saving and reading scan history."""
import cv2
import numpy as np
from sqlmodel import Session, select

from app.config import get_settings
from app.models import FindingRow, IngredientRow, Scan
from tests.conftest import DEVICE_A, DEVICE_B, headers

BODY = {"ingredients_text": "Wheat flour (72%), Salt, Preservative (INS 211)", "nutrition_text": "Sodium 900 mg"}


def analyze(client, device=DEVICE_A, **extra):
    r = client.post("/api/v1/analyze", headers=headers(device), json={**BODY, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_analyze_response_has_real_engine_output(client):
    body = analyze(client, food_category="bakery")
    assert "MOCK_DATA" not in body["warnings"]
    assert body["fssai_result"]["summary"]["scanned"] == 3
    assert body["fssai_result"]["summary"]["pass"] == 2  # wheat flour, salt
    assert body["fssai_result"]["overall_status"] == "REVIEW"  # additive rule is a placeholder
    assert 0 <= body["health_result"]["score"] <= 100 and body["health_result"]["disclaimer"]


def test_no_nutrition_gives_capped_band_and_warning(client):
    body = analyze(client, nutrition_text=None)
    h = body["health_result"]
    assert "LIMITED_NUTRITION_DATA" in body["warnings"] and "NO_NUTRITION_FOUND" in body["warnings"]
    assert h["assessment"] != "FEWER CONCERNS" and h["data_completeness"] == "ingredients_only"


def test_per_serving_only_warns(client):
    body = analyze(client, nutrition_text="Nutrition per serving (30 g): Energy 120 kcal, Total sugars 5 g")
    assert "NUTRITION_PER_SERVING_ONLY" in body["warnings"] and "LIMITED_NUTRITION_DATA" in body["warnings"]
    assert body["health_result"]["data_completeness"] == "ingredients_only"


def test_health_completeness_fields_in_response(client):
    h = analyze(client, nutrition_text="per 100 g: Total sugars 3 g, Total fat 5 g, Saturated fat 1 g, Sodium 100 mg")["health_result"]
    assert h["data_completeness"] == "full" and isinstance(h["completeness_score"], float)
    assert analyze(client)["health_result"]["data_completeness"] == "partial"  # BODY has only sodium


def test_beverage_category_uses_half_thresholds(client):
    def factor_keys(**extra):
        body = analyze(client, nutrition_text="per 100 g: Total sugars 12 g", **extra)
        return [f["key"] for f in body["health_result"]["factors"]]

    assert "high_sugar" in factor_keys(food_category="beverages_non_alcoholic")  # 12 > 11.25
    assert "high_sugar" not in factor_keys(food_category="bakery")  # 12 < 22.5
    assert "high_sugar" not in factor_keys()  # no category: food thresholds


def test_label_level_finding_roundtrips_with_null_ingredient_id(client, db_engine):
    created = analyze(client, ingredients_text="Sugar, Colour (INS 102)")
    nulls = [f for f in created["fssai_result"]["findings"] if f["ingredient_id"] is None]
    assert len(nulls) == 1 and nulls[0]["status"] == "REVIEW"
    assert nulls[0]["reason"] == "Declaration not found in the scanned area"
    stored = client.get(f"/api/v1/scans/{created['scan_id']}", headers=headers()).json()
    assert stored == created
    with Session(db_engine) as s:
        assert [r.ingredient_id for r in s.exec(select(FindingRow)) if r.ingredient_id is None] == [None]


def test_device_header_required_and_validated(client):
    for url, kwargs in [("/api/v1/analyze", {"json": BODY}), ("/api/v1/scans", {}), ("/api/v1/scans/x", {})]:
        method = client.post if "analyze" in url else client.get
        r = method(url, **kwargs)
        assert r.status_code == 400 and r.json()["error"]["code"] == "MISSING_DEVICE_ID"
        r = method(url, headers={"X-Device-Id": "not-a-uuid"}, **kwargs)
        assert r.json()["error"]["code"] == "INVALID_DEVICE_ID"


def test_scan_is_saved_and_retrievable(client):
    created = analyze(client)
    r = client.get(f"/api/v1/scans/{created['scan_id']}", headers=headers())
    assert r.status_code == 200 and r.json() == created
    assert r.json()["fssai_result"]["summary"]["pass"] == created["fssai_result"]["summary"]["pass"]  # "pass" alias kept


def test_history_lists_only_own_scans_newest_first(client):
    first, second = analyze(client), analyze(client)
    analyze(client, device=DEVICE_B)
    body = client.get("/api/v1/scans", headers=headers()).json()
    assert body["total"] == 2 and [i["scan_id"] for i in body["items"]] == [second["scan_id"], first["scan_id"]]
    item = body["items"][0]
    assert item["overall_status"] == second["fssai_result"]["overall_status"]
    assert item["health_score"] == second["health_result"]["score"] and item["ingredient_count"] == 3
    assert client.get("/api/v1/scans", headers=headers("33333333-3333-4333-8333-333333333333")).json()["total"] == 0


def test_history_paging(client):
    ids = [analyze(client)["scan_id"] for _ in range(3)]
    page = client.get("/api/v1/scans?limit=2&offset=1", headers=headers()).json()
    assert page["total"] == 3 and page["limit"] == 2 and page["offset"] == 1
    assert [i["scan_id"] for i in page["items"]] == [ids[1], ids[0]]
    assert client.get("/api/v1/scans?limit=0", headers=headers()).status_code == 422


def test_other_devices_scan_is_404(client):
    created = analyze(client)
    for method in (client.get, client.delete):
        r = method(f"/api/v1/scans/{created['scan_id']}", headers=headers(DEVICE_B))
        assert r.status_code == 404 and r.json()["error"]["code"] == "SCAN_NOT_FOUND"
    assert client.get(f"/api/v1/scans/{created['scan_id']}", headers=headers()).status_code == 200


def test_unknown_scan_is_404(client):
    r = client.get("/api/v1/scans/does-not-exist", headers=headers())
    assert r.status_code == 404 and r.json()["error"]["code"] == "SCAN_NOT_FOUND"


def test_rows_written_to_all_three_tables(client, db_engine):
    created = analyze(client, food_category="bakery")
    with Session(db_engine) as s:
        scan = s.get(Scan, created["scan_id"])
        assert scan.device_id == DEVICE_A and scan.food_category == "bakery" and scan.explanation is None
        assert len(s.exec(select(IngredientRow)).all()) == 3
        assert len(s.exec(select(FindingRow)).all()) == len(created["fssai_result"]["findings"])


def test_delete_removes_rows_and_image(client, db_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", tmp_path)
    created = analyze(client)
    (tmp_path / "photo.jpg").write_bytes(b"x")
    with Session(db_engine) as s:  # pretend this scan came from a photo
        scan = s.get(Scan, created["scan_id"])
        scan.image_name = "photo.jpg"
        s.add(scan)
        s.commit()

    r = client.delete(f"/api/v1/scans/{created['scan_id']}", headers=headers())
    assert r.status_code == 204 and r.content == b""
    assert not (tmp_path / "photo.jpg").exists()
    assert client.get(f"/api/v1/scans/{created['scan_id']}", headers=headers()).status_code == 404
    with Session(db_engine) as s:
        assert s.exec(select(Scan)).all() == []
        assert s.exec(select(IngredientRow)).all() == [] and s.exec(select(FindingRow)).all() == []


def test_delete_leaves_other_scans_alone(client):
    keep, drop = analyze(client), analyze(client)
    client.delete(f"/api/v1/scans/{drop['scan_id']}", headers=headers())
    assert [i["scan_id"] for i in client.get("/api/v1/scans", headers=headers()).json()["items"]] == [keep["scan_id"]]


def test_mock_scan_needs_no_device_header_and_matches_the_schema(client):
    r = client.get("/api/v1/mock/scan")
    body = r.json()
    assert r.status_code == 200 and body["fssai_result"]["summary"]["pass"] == 6
    assert body["health_result"]["data_completeness"] in ("full", "partial", "ingredients_only")
    assert isinstance(body["health_result"]["completeness_score"], float)
    assert any(f["ingredient_id"] is None for f in body["fssai_result"]["findings"])  # shows the label-level shape


def test_scan_photo_end_to_end(client, tmp_path, monkeypatch):
    """Real OCR on a synthetic label: photo in, saved result out."""
    monkeypatch.setattr(get_settings(), "upload_dir", tmp_path)
    img = np.full((300, 1500, 3), 255, np.uint8)  # compact: RapidOCR's detector skips lines on sparse images
    for i, line in enumerate(["INGREDIENTS: Wheat flour (72%), Sugar, Salt, Preservative (INS 211).",
                              "NUTRITION per 100 g: Energy 400 kcal, Sodium 800 mg"]):
        cv2.putText(img, line, (30, 60 + i * 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
    ok, png = cv2.imencode(".png", img)
    r = client.post("/api/v1/scan", headers=headers(), files={"image": ("label.png", png.tobytes(), "image/png")},
                    data={"food_category": "bakery"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ocr"]["engine"].startswith("rapidocr")
    assert [i["normalized"] for i in body["ingredients"]][:3] == ["wheat flour", "sugar", "salt"]
    assert body["nutrition"]["sodium_mg"] == 800
    assert len(list(tmp_path.iterdir())) == 1  # the photo was saved
    assert client.get(f"/api/v1/scans/{body['scan_id']}", headers=headers()).json() == body
    client.delete(f"/api/v1/scans/{body['scan_id']}", headers=headers())
    assert list(tmp_path.iterdir()) == []  # ...and removed again on delete
