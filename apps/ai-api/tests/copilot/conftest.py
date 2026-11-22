"""Copilot fixtures: a private copy of the seeded+ML snapshot (data/dev/copilot-test.db). Never data/demo.db; never a network LLM."""

from __future__ import annotations

import shutil
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT
from app.main import create_app
from tests.conftest import make_settings

SNAPSHOT = REPO_ROOT / "data" / "dev" / "snapshot-with-ml.db"
TEST_DB = REPO_ROOT / "data" / "dev" / "copilot-test.db"

needs_snapshot = pytest.mark.skipif(not SNAPSHOT.exists() or SNAPSHOT.stat().st_size < 1_000_000, reason="data/dev/snapshot-with-ml.db not present")

FOCUS_OER = "2026-10-02T09:00:00Z"  # OER_DEGRADATION (16:00 mill time)
NORMAL = "2026-10-21T08:00:00Z"  # NORMAL_DAY
PRESS = "2026-11-20T08:00:00Z"  # PRESS_VIBRATION_ANOMALY
QUEUE = "2026-11-14T03:00:00Z"  # TRUCK_QUEUE_CONGESTION
ENERGY = "2026-09-10T08:00:00Z"  # ENERGY_EFFICIENCY_DROP
STEAM = "2026-10-29T05:00:00Z"  # STEAM_PRESSURE_DEVIATION


@pytest.fixture(scope="session")
def cp_settings():
    if not SNAPSHOT.exists():
        pytest.skip("snapshot missing")
    shutil.copyfile(SNAPSHOT, TEST_DB)
    # explicit: tests never use an LLM provider even if a developer .env sets one
    return make_settings(database_url=f"sqlite:///{TEST_DB}", llm_provider="none", llm_api_key="")


@pytest.fixture(scope="session")
def cp_client(cp_settings):
    return TestClient(create_app(cp_settings))


@pytest.fixture(scope="session")
def cp_db(cp_settings):
    from app.db.session import get_sessionmaker

    s = get_sessionmaker(cp_settings.database_url)()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _reset_rate():
    from app.copilot import engine

    engine._rate.clear()
    yield


def ask(client, message: str, as_of: str = FOCUS_OER, role: str = "public_viewer", session: str | None = None, conv: str | None = None, lang: str = "en"):
    headers = {"X-Demo-Role": role}
    if session:
        headers["X-Demo-Session"] = session
    body = {"message": message, "lang": lang}
    if conv:
        body["copilot_session_id"] = conv
    r = client.post("/api/v1/copilot/chat", params={"as_of": as_of}, json=body, headers=headers)
    return r


def new_session() -> str:
    return str(uuid.uuid4())


def make_ctx(settings, as_of: str, role: str = "public_viewer", session: str | None = None):
    from app.models.enums import Role
    from app.services.demo_context import DemoContext, parse_as_of

    return DemoContext(as_of=parse_as_of(as_of, settings), as_of_explicit=True, window_start=settings.window_start, window_end=settings.window_end,
                       role=Role(role), session_id=session)  # fmt: skip
