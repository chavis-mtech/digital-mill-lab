"""Fixtures for the cross-module integration suite (owner: qa-docs).

Uses a private writable copy of the seeded + ML snapshot (data/dev/qa-integ.db); data/demo.db is never opened.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.security.support import make_client, prepare_db

PRESS = "2026-11-20T08:00:00Z"  # PRESS_VIBRATION_ANOMALY focus_ts
NORMAL = "2026-10-21T08:00:00Z"  # NORMAL_DAY focus_ts
OER_FOCUS = "2026-10-02T09:00:00Z"  # OER_DEGRADATION focus_ts
TRUCK_FOCUS = "2026-11-14T03:00:00Z"  # TRUCK_QUEUE_CONGESTION focus_ts (queue forming)
TRUCK_PEAK = "2026-11-14T06:00:00Z"  # observed peak of the congestion episode
PRS03 = 18


@pytest.fixture(scope="session")
def integ_db_url() -> str:
    return prepare_db("qa-integ")


@pytest.fixture(scope="session")
def client(integ_db_url) -> TestClient:
    return make_client(integ_db_url)


@pytest.fixture(scope="session")
def sql(integ_db_url):
    path = Path(integ_db_url.removeprefix("sqlite:///"))

    def run(q: str, *args):
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return con.execute(q, args).fetchall()
        finally:
            con.close()

    return run
