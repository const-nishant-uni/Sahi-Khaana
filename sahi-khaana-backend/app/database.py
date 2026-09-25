"""SQLite engine + session dependency."""
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_url = get_settings().database_url
# check_same_thread=False: FastAPI runs sync endpoints in worker threads.
engine = create_engine(_url, connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})


def init_db() -> None:
    """Create the tables if they don't exist yet."""
    from app import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: one session per request."""
    with Session(engine) as session:
        yield session
