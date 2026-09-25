"""Startup cleanup: photos older than 7 days are deleted and cleared from history."""
import os
import time

import pytest
from sqlmodel import Session

from app.config import get_settings
from app.models import Scan
from app.services.scan_service import delete_old_images

DAY = 86400


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", tmp_path)
    return tmp_path


def photo(folder, name, age_days):
    path = folder / name
    path.write_bytes(b"x")
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def add_scan(session, scan_id, image_name):
    session.add(Scan(id=scan_id, device_id="d", created_at="2026-01-01T00:00:00+00:00", overall_status="PASS",
                     health_score=80, assessment="MODERATE", ingredient_count=1, image_name=image_name,
                     result_json="{}"))
    session.commit()


def test_old_images_deleted_and_image_name_cleared(uploads, db_engine):
    old, fresh = photo(uploads, "old.jpg", 8), photo(uploads, "fresh.jpg", 6)
    with Session(db_engine) as s:
        add_scan(s, "s-old", "old.jpg")
        add_scan(s, "s-fresh", "fresh.jpg")
        assert delete_old_images(s) == 1
        s.expire_all()
        assert s.get(Scan, "s-old").image_name is None  # history row kept, photo reference cleared
        assert s.get(Scan, "s-fresh").image_name == "fresh.jpg"
    assert not old.exists() and fresh.exists()


def test_retention_period_is_seven_days(uploads, db_engine):
    exactly_old = photo(uploads, "a.jpg", 7.01)
    just_inside = photo(uploads, "b.jpg", 6.99)
    with Session(db_engine) as s:
        delete_old_images(s)
    assert not exactly_old.exists() and just_inside.exists()


def test_retention_days_is_configurable(uploads, db_engine, monkeypatch):
    monkeypatch.setattr(get_settings(), "image_retention_days", 30)
    p = photo(uploads, "a.jpg", 20)
    with Session(db_engine) as s:
        assert delete_old_images(s) == 0
    assert p.exists()


def test_orphan_files_without_a_scan_are_deleted_too(uploads, db_engine):
    orphan = photo(uploads, "failed-scan.jpg", 30)
    with Session(db_engine) as s:
        assert delete_old_images(s) == 1
    assert not orphan.exists()


def test_gitkeep_and_hidden_files_and_folders_are_left_alone(uploads, db_engine):
    keep = photo(uploads, ".gitkeep", 100)
    (uploads / "subdir").mkdir()
    with Session(db_engine) as s:
        assert delete_old_images(s) == 0
    assert keep.exists() and (uploads / "subdir").exists()


def test_missing_upload_folder_is_not_an_error(tmp_path, db_engine, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", tmp_path / "does-not-exist")
    with Session(db_engine) as s:
        assert delete_old_images(s) == 0


def test_nothing_to_delete_leaves_db_untouched(uploads, db_engine):
    photo(uploads, "fresh.jpg", 1)
    with Session(db_engine) as s:
        add_scan(s, "s", "fresh.jpg")
        assert delete_old_images(s) == 0
        assert s.get(Scan, "s").image_name == "fresh.jpg"


def test_startup_runs_the_cleanup(uploads, db_engine, monkeypatch):
    """The lifespan hook calls delete_old_images (checked without loading the OCR models)."""
    import app.main as main
    from fastapi.testclient import TestClient

    old = photo(uploads, "old.jpg", 9)
    monkeypatch.setattr(main, "get_rapidocr", lambda: None)
    monkeypatch.setattr(main, "engine", db_engine)
    monkeypatch.setattr(main, "init_db", lambda: None)
    with TestClient(main.app):  # entering the context runs the startup code
        pass
    assert not old.exists()
