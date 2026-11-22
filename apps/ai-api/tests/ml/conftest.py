"""ML test fixtures. Uses data/dev/ml.db (a copy of the seeded demo DB after `python -m app.ml.train`); tests that need it skip
when it is absent. Never touches data/demo.db."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT
from app.main import create_app
from tests.conftest import make_settings

ML_DB = REPO_ROOT / "data" / "dev" / "ml.db"


def _ready() -> bool:
    if not ML_DB.exists() or ML_DB.stat().st_size == 0:
        return False
    try:
        con = sqlite3.connect(f"file:{ML_DB}?mode=ro", uri=True)
        n = con.execute("SELECT COUNT(*) FROM model_registry").fetchone()[0]
        con.close()
        return n >= 8 and (REPO_ROOT / "data" / "models" / "oer_forecast").exists()
    except sqlite3.Error:
        return False


needs_ml_db = pytest.mark.skipif(not _ready(), reason="run: cp data/demo.db data/dev/ml.db && DATABASE_URL=sqlite:///data/dev/ml.db python -m app.ml.train")


@pytest.fixture
def ml_client() -> TestClient:
    return TestClient(create_app(make_settings(database_url=f"sqlite:///{ML_DB}")))


@pytest.fixture
def ml_url() -> str:
    return f"sqlite:///{ML_DB}"
