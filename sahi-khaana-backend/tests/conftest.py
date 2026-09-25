"""Shared fixtures: an API client backed by a throw-away in-memory SQLite database."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app

DEVICE_A = "11111111-1111-4111-8111-111111111111"
DEVICE_B = "22222222-2222-4222-8222-222222222222"


def headers(device_id: str = DEVICE_A) -> dict:
    return {"X-Device-Id": device_id}


@pytest.fixture
def db_engine():
    from app import models  # noqa: F401  (registers the tables)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine):
    def override_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    yield TestClient(app)  # no `with`: skips startup (no OCR model loading / real DB file)
    app.dependency_overrides.clear()
