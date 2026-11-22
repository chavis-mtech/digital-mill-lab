"""DemoContext parsing and strict validation."""

from __future__ import annotations

import uuid


def _ctx(client, params=None, headers=None):
    return client.get("/api/v1/demo/context", params=params or {}, headers=headers or {})


def test_defaults(client):
    r = _ctx(client)
    assert r.status_code == 200
    c = r.json()["context"]
    assert c["role"] == "public_viewer"
    assert c["session_id"] is None
    assert c["as_of_explicit"] is False
    assert c["as_of"].startswith("2026-11-20T11:00:00")  # 18:00 Asia/Bangkok
    assert c["business_date"] == "2026-11-20"


def test_date_only_as_of_means_18h_mill_time(client):
    c = _ctx(client, {"as_of": "2026-10-01"}).json()["context"]
    assert c["as_of"].startswith("2026-10-01T11:00:00")
    assert c["as_of_explicit"] is True


def test_naive_datetime_is_mill_local(client):
    c = _ctx(client, {"as_of": "2026-10-01T07:30:00"}).json()["context"]
    assert c["as_of"].startswith("2026-10-01T00:30:00")


def test_offset_datetime_respected(client):
    c = _ctx(client, {"as_of": "2026-10-01T07:30:00Z"}).json()["context"]
    assert c["as_of"].startswith("2026-10-01T07:30:00")


def test_as_of_outside_window_rejected(client):
    for bad in ("2026-07-23", "2026-11-21T00:00:00+07:00", "2027-01-01"):
        r = _ctx(client, {"as_of": bad})
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "as_of_out_of_window"


def test_window_edges_accepted(client):
    assert _ctx(client, {"as_of": "2026-07-24T00:00:00+07:00"}).status_code == 200
    assert _ctx(client, {"as_of": "2026-11-20T23:59:59+07:00"}).status_code == 200


def test_garbage_as_of_rejected(client):
    r = _ctx(client, {"as_of": "yesterday"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_as_of"


def test_invalid_role_rejected(client):
    r = _ctx(client, headers={"X-Demo-Role": "ceo"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_role"


def test_role_header_case_insensitive(client):
    assert _ctx(client, headers={"X-Demo-Role": "AI_Analyst"}).json()["context"]["role"] == "ai_analyst"


def test_invalid_session_rejected(client):
    r = _ctx(client, headers={"X-Demo-Session": "not-a-uuid"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_session"


def test_valid_session_normalised(client):
    sid = str(uuid.uuid4())
    c = _ctx(client, headers={"X-Demo-Session": sid.upper()}).json()["context"]
    assert c["session_id"] == sid


def test_invalid_scenario_rejected(client):
    r = _ctx(client, {"scenario_id": "MELTDOWN"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_scenario"


def test_scenario_without_seed_falls_back_to_default_clock(client):
    c = _ctx(client, {"scenario_id": "press_vibration_anomaly"}).json()["context"]
    assert c["scenario_id"] == "PRESS_VIBRATION_ANOMALY"
    assert c["as_of_explicit"] is False


def test_session_issue(client):
    r = client.post("/api/v1/demo/session")
    assert r.status_code == 201
    uuid.UUID(r.json()["session_id"])
