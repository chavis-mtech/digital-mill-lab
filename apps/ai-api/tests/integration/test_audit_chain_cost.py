"""QA-10: the work-order audit endpoint must not re-walk the whole global hash chain on every request at large sizes,
and the incremental path must still catch tampering at or after its checkpoint. Threshold lowered so the seeded table
(~580 rows) exercises the incremental path."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

from app.db.session import get_sessionmaker
from app.services import audit
from tests.integration.conftest import PRESS, PRS03
from tests.security.support import make_client, prepare_db


@pytest.fixture
def env(request, monkeypatch):
    # one DB copy per test (engines are cached per URL, so each test gets its own file name)
    url = prepare_db(f"qa-audit-{request.node.name[5:30]}")
    path = Path(url.removeprefix("sqlite:///"))
    monkeypatch.setattr(audit, "FULL_VERIFY_MAX_ROWS", 100)
    audit._checkpoints.clear()
    yield make_client(url), path, url
    audit._checkpoints.clear()
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _wo(client, sess):
    h = {"X-Demo-Role": "maintenance_engineer", "X-Demo-Session": sess}
    r = client.post("/api/v1/work-orders", params={"as_of": PRESS}, headers=h,
                    json={"equipment_id": PRS03, "title": "Audit cost probe", "priority": "low", "confirm": True})
    assert r.status_code == 201, r.text
    return r.json()["id"], h


def test_incremental_verification_detects_edits_after_the_checkpoint(env):
    client, path, url = env
    wo, h = _wo(client, str(uuid.uuid4()))
    trail = client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()
    assert trail["chain_verified"] is True
    key = next(iter(audit._checkpoints))
    cp_id, _ = audit._checkpoints[key]
    # new activity after the checkpoint is verified incrementally
    tech = client.get("/api/v1/maintenance/technicians", params={"as_of": PRESS}, headers=h).json()["items"][0]["id"]
    assert client.post(f"/api/v1/work-orders/{wo}/assign", params={"as_of": PRESS}, headers=h, json={"technician_id": tech}).status_code == 200
    assert client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()["chain_verified"] is True
    assert audit._checkpoints[key][0] > cp_id
    # tamper with the newest row (after the old checkpoint) -> detected
    con = sqlite3.connect(path)
    con.execute("update audit_logs set after_json = '{\"status\":\"forged\"}' where id = (select max(id) from audit_logs)")
    con.commit()
    con.close()
    assert client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()["chain_verified"] is False


def test_editing_the_checkpoint_row_forces_a_full_walk(env):
    client, path, url = env
    wo, h = _wo(client, str(uuid.uuid4()))
    assert client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()["chain_verified"] is True
    cp_id, _ = next(iter(audit._checkpoints.values()))
    con = sqlite3.connect(path)
    con.execute("update audit_logs set role = 'system_admin' where id = ?", (cp_id,))
    con.commit()
    con.close()
    assert client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()["chain_verified"] is False


def test_documented_trade_off_an_old_row_edit_needs_a_full_walk(env):
    client, path, url = env
    wo, h = _wo(client, str(uuid.uuid4()))
    assert client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()["chain_verified"] is True
    con = sqlite3.connect(path)
    con.execute("update audit_logs set role = 'system_admin' where id = (select min(id) + 5 from audit_logs)")
    con.commit()
    con.close()
    # incremental endpoint does not see an edit before its checkpoint (pinned limitation) ...
    assert client.get(f"/api/v1/work-orders/{wo}/audit", params={"as_of": PRESS}, headers=h).json()["chain_verified"] is True
    # ... the full walk does
    with get_sessionmaker(url)() as db:
        ok, broken = audit.verify_chain(db)
    assert ok is False and broken is not None
