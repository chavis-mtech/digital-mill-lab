"""backend-a fixtures: read tests use the canonical seeded data/demo.db WITHOUT writing (mtime checked);
write tests (alert status changes) use a private copy data/dev/backend-a.db."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT
from app.main import create_app
from tests.conftest import make_settings

# Seed-only database: these tests pin seed-only semantics (no ML alerts/anomalies). `make demo-data` keeps a seed-only copy at
# data/dev/seed-only.db before training writes ML rows into data/demo.db; fall back to data/demo.db (pure seed after `make seed`).
_SEED_ONLY = REPO_ROOT / "data" / "dev" / "seed-only.db"
DEMO_DB = _SEED_ONLY if _SEED_ONLY.exists() else REPO_ROOT / "data" / "demo.db"
WRITE_DB = REPO_ROOT / "data" / "dev" / "backend-a.db"

needs_db = pytest.mark.skipif(not DEMO_DB.exists() or DEMO_DB.stat().st_size < 1_000_000, reason="seeded data/demo.db not present (run make seed)")


@pytest.fixture(scope="session")
def demo_settings():
    return make_settings(database_url=f"sqlite:///{DEMO_DB}")


@pytest.fixture(scope="session")
def demo_client(demo_settings):
    before = DEMO_DB.stat().st_mtime_ns if DEMO_DB.exists() else None
    yield TestClient(create_app(demo_settings))
    if before is not None:
        assert DEMO_DB.stat().st_mtime_ns == before, "data/demo.db was modified by backend-a tests"


@pytest.fixture(scope="session")
def demo_db(demo_settings):
    from app.db.session import get_sessionmaker

    s = get_sessionmaker(demo_settings.database_url)()
    yield s
    s.close()


@pytest.fixture(scope="session")
def write_client():
    if not WRITE_DB.exists() or WRITE_DB.stat().st_size < 1_000_000 or os.environ.get("BACKEND_A_FRESH_COPY"):
        WRITE_DB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEMO_DB, WRITE_DB)
    return TestClient(create_app(make_settings(database_url=f"sqlite:///{Path(WRITE_DB)}")))


def ctx_at(settings, as_of: str | None = None, session_id: str | None = None):
    from app.services.demo_context import DemoContext, parse_as_of

    ts = parse_as_of(as_of, settings) if as_of else settings.default_as_of
    return DemoContext(as_of=ts, as_of_explicit=True, session_id=session_id, window_start=settings.window_start, window_end=settings.window_end)


# scenario focus times (mill-local) - read from scenario_runs in tests where possible
FOCUS = {
    "NORMAL_DAY": "2026-10-21T15:00",
    "OER_DEGRADATION": "2026-10-02T16:00",
    "TRUCK_QUEUE_CONGESTION": "2026-11-14T10:00",
    "PRESS_VIBRATION_ANOMALY": "2026-11-20T15:00",
    "STEAM_PRESSURE_DEVIATION": "2026-10-29T12:00",
    "ENERGY_EFFICIENCY_DROP": "2026-09-10T15:00",
}
