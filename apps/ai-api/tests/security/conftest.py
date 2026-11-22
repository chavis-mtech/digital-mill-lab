"""Fixtures for the QA/security suite: a private writable copy of the seeded + ML snapshot (data/dev/qa.db)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .support import Op, discover_path_ids, focus_times, load_ops, make_client, prepare_db


@pytest.fixture(scope="session")
def qa_db_url() -> str:
    return prepare_db("qa")


@pytest.fixture(scope="session")
def client(qa_db_url) -> TestClient:
    return make_client(qa_db_url)


@pytest.fixture(scope="session")
def spec(client) -> dict:
    return client.app.openapi()


@pytest.fixture(scope="session")
def ops(spec) -> list[Op]:
    return load_ops(spec)


@pytest.fixture(scope="session")
def path_ids(client) -> dict:
    return discover_path_ids(client)


@pytest.fixture(scope="session")
def focus(qa_db_url) -> dict:
    return focus_times(qa_db_url)
