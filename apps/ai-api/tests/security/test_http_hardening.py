"""HTTP-level hardening (QA item 5): security headers, body-size cap, CORS, request-id handling, content-type fuzzing,
error-envelope hygiene.

Findings that drove code changes (see the QA log (kept private)):
  QA-02  no response carried any security header (no nosniff / CSP / cache policy), incl. the raw-HTML report endpoint
  QA-03  no request-body size limit: 60 MB JSON bodies were fully read and parsed before being rejected by the handler
"""

from __future__ import annotations

import json
import re

import pytest

from .support import assert_clean_error, collect_ops, hdr, leaks_in, make_client, new_session, prepare_db

OPS, SPEC = collect_ops()
P = {"as_of": "2026-11-20T08:00:00Z"}
ALLOWED = "http://localhost:3000"


@pytest.fixture(scope="module")
def hc():
    return make_client(prepare_db("qa-http"))


# ---------------------------------------------------------------------------------------------------- security headers


API_SAMPLES = ["/api/v1/meta", "/api/v1/executive/kpis", "/api/v1/demo/roles", "/api/v1/nope", "/api/v1/work-orders/999999"]


@pytest.mark.parametrize("path", API_SAMPLES)
def test_api_responses_carry_security_headers(hc, path):
    r = hc.get(path, headers=hdr("public_viewer"))
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("referrer-policy") == "no-referrer"
    assert "no-store" in r.headers.get("cache-control", "")
    csp = r.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp and "frame-ancestors" in csp
    assert r.headers.get("x-frame-options") in ("DENY", "SAMEORIGIN")
    assert "x-request-id" in r.headers


def test_error_and_rate_limited_responses_also_carry_the_headers():
    c = make_client(prepare_db("qa-http-rl"), rate_limit_enabled=True, rate_limit_per_ip_per_minute=1, rate_limit_burst=1)
    assert c.get("/api/v1/meta").status_code == 200
    r = c.get("/api/v1/meta")
    assert r.status_code == 429
    assert r.headers.get("x-content-type-options") == "nosniff" and "no-store" in r.headers.get("cache-control", "")


def test_html_report_endpoint_is_locked_down(hc):
    """Raw HTML from the API (print view): no scripts can run in it even if text were ever injected."""
    r = hc.get("/api/v1/reports/executive/html", params={**P, "raw": "true"}, headers=hdr("public_viewer"))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src" not in csp.replace("default-src 'none'", "") or "script-src 'none'" in csp
    assert "unsafe-eval" not in csp and "<script" not in r.text.lower()
    assert r.headers["x-content-type-options"] == "nosniff"


def test_swagger_docs_still_load(hc):
    """The CSP must not break the interactive docs (they load their own assets)."""
    assert hc.get("/docs").status_code == 200
    assert hc.get("/openapi.json").status_code == 200
    assert "content-security-policy" not in hc.get("/docs").headers


# ---------------------------------------------------------------------------------------------------- body size cap


def _post_json(client, path, payload: bytes, **kw):
    return client.post(path, params=P, content=payload, headers={**hdr("maintenance_engineer", new_session()), "content-type": "application/json", **kw})


@pytest.mark.parametrize("size_kib", [300, 2048, 20_000])
def test_oversized_json_bodies_are_rejected_with_413_before_parsing(hc, size_kib):
    body = json.dumps({"equipment_id": 18, "title": "t" * (size_kib * 1024), "confirm": True}).encode()
    for path in ("/api/v1/work-orders", "/api/v1/scenarios/saved", "/api/v1/roi/calculate", "/api/v1/copilot/chat", "/api/v1/demo/tick"):
        r = _post_json(hc, path, body)
        assert_clean_error(r, status=413, code="payload_too_large")


def test_body_cap_is_enforced_on_chunked_bodies_without_content_length(hc):
    def gen():
        for _ in range(64):
            yield b'{"a":"' + b"x" * 8192 + b'"}'

    r = hc.post("/api/v1/work-orders", params=P, content=gen(), headers={**hdr("maintenance_engineer", new_session()), "content-type": "application/json"})
    assert r.status_code == 413, r.text[:200]


def test_normal_sized_bodies_still_work(hc):
    r = hc.post("/api/v1/scenarios/saved", params=P, headers=hdr("executive", new_session()), json={"kind": "production", "name": "ok", "inputs": {"x": "y" * 60_000}, "outputs": {}})
    assert r.status_code == 201, r.text[:200]  # 64 KiB per field is the documented maximum and fits the cap


def test_upload_route_has_its_own_larger_cap(hc):
    big_ok = b"\x89PNG\r\n\x1a\n" + b"\x00" * (200 * 1024)  # > JSON cap, < upload cap: reaches the upload validator, not the body cap
    r = hc.post("/api/v1/cv/ffb-assessment", params=P, files={"file": ("a.png", big_ok, "image/png")}, headers=hdr("ai_analyst"))
    assert r.status_code != 413 or r.json()["error"]["details"].get("max_bytes"), r.text[:200]
    huge = b"\x89PNG\r\n\x1a\n" + b"\x00" * (8 * 1024 * 1024)
    r = hc.post("/api/v1/cv/ffb-assessment", params=P, files={"file": ("a.png", huge, "image/png")}, headers=hdr("ai_analyst"))
    assert_clean_error(r, status=413, code="payload_too_large")


# ---------------------------------------------------------------------------------------------------- CORS


def test_cors_allows_only_configured_origins(hc):
    ok = hc.get("/api/v1/meta", headers={"Origin": ALLOWED})
    assert ok.headers.get("access-control-allow-origin") == ALLOWED
    assert "access-control-allow-credentials" not in ok.headers  # credentials are never allowed
    for evil in ("http://evil.example", "http://localhost:3000.evil.example", "https://localhost:3000", "http://localhost:3001", "null", "http://LOCALHOST:3000", "*", ""):
        r = hc.get("/api/v1/meta", headers={"Origin": evil})
        assert r.headers.get("access-control-allow-origin") is None, (evil, dict(r.headers))
        assert r.status_code == 200  # CORS is enforced by the browser; the server just does not grant access


def test_cors_preflight_is_restrictive(hc):
    def preflight(origin, method="POST", headers="content-type,x-demo-role"):
        return hc.options("/api/v1/work-orders", headers={"Origin": origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": headers})

    ok = preflight(ALLOWED)
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == ALLOWED
    allowed_methods = set(re.split(r",\s*", ok.headers["access-control-allow-methods"]))
    assert allowed_methods == {"GET", "POST", "OPTIONS"}, allowed_methods
    assert "access-control-allow-credentials" not in ok.headers
    bad_origin = preflight("http://evil.example")
    assert bad_origin.status_code == 400 and "access-control-allow-origin" not in bad_origin.headers
    for method in ("DELETE", "PUT", "PATCH"):
        assert preflight(ALLOWED, method).status_code == 400
    assert preflight(ALLOWED, headers="authorization").status_code == 400
    assert preflight(ALLOWED, headers="x-forwarded-for").status_code == 400


# ---------------------------------------------------------------------------------------------------- request id + headers


def test_request_id_is_never_reflected_unsanitised(hc):
    for hostile in ("a\r\nSet-Cookie: x=1", "x" * 200, "<script>", "../../etc", "a b", "'; DROP", "ก" * 5, ""):
        r = hc.get("/api/v1/meta", headers={"X-Request-ID": hostile.encode()})
        rid = r.headers["x-request-id"]
        assert re.fullmatch(r"[0-9a-f]{32}", rid), (hostile, rid)  # replaced by a server-generated id
    assert hc.get("/api/v1/meta", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"


@pytest.mark.parametrize("ctype", ["text/plain", "application/x-www-form-urlencoded", "application/xml", "multipart/form-data", "multipart/form-data; boundary=", "application/json; charset=utf-16", "application/jsonx", "", "*/*", "application/json\x00", "ก"])
def test_wrong_content_types_on_json_endpoints_are_client_errors(hc, ctype):
    body = json.dumps({"equipment_id": 18, "title": "ctype probe", "confirm": True}).encode()
    h = {**hdr("maintenance_engineer", new_session()), "content-type": ctype.encode()}
    r = hc.post("/api/v1/work-orders", params=P, content=body, headers=h)
    assert r.status_code in (201, 400, 415, 422), (ctype, r.status_code, r.text[:200])  # 201 only if the type is a JSON variant
    if r.status_code != 201:
        assert_clean_error(r)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"null",
        b"[]",
        b'"string"',
        b"{",
        b'{"equipment_id": 18, "title": "x", "confirm": true',
        b'{"equipment_id": NaN, "title": "abc", "confirm": true}',
        b'{"equipment_id": Infinity, "title": "abc", "confirm": true}',
        b'{"equipment_id": 1' + b"0" * 5000 + b', "title": "abc", "confirm": true}',  # 5000-digit integer
        b"[" * 50_000 + b"]" * 50_000,  # deep nesting
        b'{"a":' * 20_000 + b"1" + b"}" * 20_000,
        b"\xff\xfe\x00\x00",  # invalid UTF-8
        b'{"title": "\xed\xa0\x80"}',  # lone surrogate in UTF-8
        b"\x00" * 1000,
    ],
    ids=lambda b: repr(b[:24]),
)
def test_malformed_json_bodies_never_cause_a_server_error(hc, raw):
    r = _post_json(hc, "/api/v1/work-orders", raw)
    assert r.status_code in (400, 413, 422), (r.status_code, r.text[:200])
    assert_clean_error(r)


def test_duplicate_json_keys_are_last_wins_not_an_error(hc):
    r = _post_json(hc, "/api/v1/work-orders", b'{"equipment_id": 18, "equipment_id": 19, "title": "dup", "confirm": true}')
    assert r.status_code == 201 and r.json()["equipment"]["id"] == 19


def test_error_envelope_never_leaks_internals_on_any_error_status(hc):
    probes = [
        ("GET", "/api/v1/work-orders/abc", {}),
        ("GET", "/api/v1/alerts/99999999999999999999999", {}),
        ("GET", "/api/v1/executive/kpis", {"params": {"period": "'; select 1;--"}}),
        ("GET", "/api/v1/kb/documents/..%2f..%2fetc%2fpasswd", {}),
        ("POST", "/api/v1/roi/calculate", {"json": {"nope": 1}}),
        ("GET", "/api/v1/%00", {}),
        ("GET", "/api/v1/" + "a" * 5000, {}),
    ]
    for method, path, kw in probes:
        r = hc.request(method, path, headers=hdr("system_admin", new_session()), **kw)
        assert 400 <= r.status_code < 500, (path, r.status_code, r.text[:200])
        assert_clean_error(r)
        assert not leaks_in(r.text)
        assert "root:" not in r.text


def test_server_errors_use_the_envelope_and_hide_the_cause(hc, monkeypatch):
    """Force an unexpected exception inside a handler: the client must see a generic 500 envelope only."""
    import app.services.kpi as kpi  # noqa: PLC0415

    def boom(*a, **k):
        raise RuntimeError("secret internal detail /home/user/secret.py SELECT * FROM audit_logs")

    monkeypatch.setattr(kpi, "executive_kpis", boom)
    r = hc.get("/api/v1/executive/kpis", params=P, headers=hdr("public_viewer"))
    err = assert_clean_error(r, status=500, code="internal_error")
    assert "secret" not in json.dumps(err) and err["details"] is None and "Traceback" not in r.text


def test_reset_all_is_disabled_on_a_public_deployment_unless_explicitly_allowed():
    """The simulated role header is not authentication: on APP_ENV=demo the all-visitors reset must be refused.
    (The default test database is empty, so the permitted cases are checked as "not refused with 403", not as 200.)"""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import make_settings

    hdr = {"X-Demo-Role": "system_admin", "X-Demo-Session": "11111111-1111-4111-8111-111111111111"}
    public = TestClient(create_app(make_settings(app_env="demo")), raise_server_exceptions=False)
    r = public.post("/api/v1/demo/reset-all", headers=hdr)
    assert r.status_code == 403 and "disabled" in r.text
    for settings in (make_settings(app_env="demo", allow_reset_all=True), make_settings(app_env="development"), make_settings(app_env="test")):
        c = TestClient(create_app(settings), raise_server_exceptions=False)
        assert c.post("/api/v1/demo/reset-all", headers=hdr).status_code != 403
    assert make_settings(app_env="production").reset_all_allowed is False
    assert make_settings(app_env="production", allow_reset_all=True).reset_all_allowed is True
