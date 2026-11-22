"""Shared fixtures. Tests never touch data/demo.db: they use data/dev/architect*.db or tmp files."""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///data/dev/architect.db")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401
from app.config import Settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402


def make_settings(**overrides) -> Settings:
    base = {"database_url": "sqlite:///data/dev/architect.db", "rate_limit_enabled": False, "app_env": "test", "log_level": "WARNING"}
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def db_session(tmp_path) -> Session:
    """Fresh schema via create_all on a temp SQLite file with FK enforcement on."""
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()
