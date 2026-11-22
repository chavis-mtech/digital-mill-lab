"""Fixtures for backend-b tests: a fresh writable copy of the canonical demo DB (never the canonical file itself)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.session import get_sessionmaker
from app.main import create_app

REPO = Path(__file__).resolve().parents[4]
# seed-only semantics (see tests/backend_a/conftest.py): prefer the copy `make demo-data` keeps before training
SRC = REPO / "data" / "dev" / "seed-only.db" if (REPO / "data" / "dev" / "seed-only.db").exists() else REPO / "data" / "demo.db"
DST = REPO / "data" / "dev" / "backend-b-test.db"

FOCUS = "2026-11-20T08:00:00Z"  # PRESS_VIBRATION_ANOMALY focus_ts (2026-11-20 15:00 mill time)
BASELINE = "2026-11-05T08:00:00Z"  # PRESS_VIBRATION_ANOMALY baseline_ts: PRS-03 healthy
EARLY = "2026-11-10T08:00:00Z"  # before the PRS-03 vibration alerts and before seeded WO 117 exists


@pytest.fixture(scope="session")
def db_url() -> str:
    if not SRC.exists():
        pytest.skip("data/demo.db is not built (run `make seed`)")
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, DST)  # writes go to the copy; data/demo.db stays untouched
    return f"sqlite:///{DST}"


@pytest.fixture(scope="session")
def settings(db_url) -> Settings:
    return Settings(database_url=db_url, rate_limit_enabled=False, app_env="test", log_level="ERROR")


@pytest.fixture(scope="session")
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def db(db_url):
    with get_sessionmaker(db_url)() as s:
        yield s


def hdr(role: str = "maintenance_engineer", session: str | None = "new") -> dict[str, str]:
    h = {"X-Demo-Role": role}
    if session == "new":
        h["X-Demo-Session"] = str(uuid.uuid4())
    elif session:
        h["X-Demo-Session"] = session
    return h


@pytest.fixture
def me():
    """Maintenance engineer with a fresh sandbox session."""
    return hdr("maintenance_engineer")


@pytest.fixture
def fm():
    return hdr("factory_manager")


def err(r) -> str:
    return r.json()["error"]["code"]
