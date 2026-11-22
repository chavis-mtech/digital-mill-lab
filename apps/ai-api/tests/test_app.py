from __future__ import annotations

from app.services.rbac import Permission


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers.get("x-request-id")


def test_request_id_is_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_meta_has_disclaimers_and_window(client):
    r = client.get("/api/v1/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["product"] == "Digital Mill Lab"
    keys = {d["key"] for d in body["disclaimers"]}
    assert {"independent_concept", "synthetic_data", "roi_illustrative"} <= keys
    assert body["anchor_date"] == "2026-11-20"
    assert body["data_window"]["days"] == 120
    assert body["data_window"]["start_date"] == "2026-07-24"
    assert body["copilot_mode"] == "deterministic"


def test_docs_and_openapi_served(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["openapi"].startswith("3.")
    assert len(spec["paths"]) > 80


def test_every_api_operation_has_contract_metadata(client):
    spec = client.get("/openapi.json").json()
    perms = {p.value for p in Permission}
    for path, item in spec["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, op in item.items():
            assert op.get("x-owner"), f"{method} {path} missing x-owner"
            assert op.get("x-status") in {"stub", "implemented", "partial", "prototype"}, path
            assert op.get("x-roles"), path
            assert op.get("x-permission") is None or op["x-permission"] in perms, path
            ok = [c for c in op["responses"] if c.startswith("2")]
            assert ok, f"{method} {path} has no 2xx response"
            schema = op["responses"][ok[0]].get("content", {}).get("application/json", {}).get("schema")
            assert schema and "$ref" in schema, f"{method} {path} must declare an explicit response model"


def test_unknown_route_uses_error_envelope(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_ready_reports_unseeded_db(client):
    r = client.get("/ready")
    body = r.json()
    assert r.status_code in (200, 503)
    assert any(c["name"] == "database" for c in body["checks"])
