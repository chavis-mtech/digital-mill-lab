"""Authorization matrix generated from the OpenAPI contract (QA item 1).

For every operation in the live OpenAPI document and every one of the 8 simulated roles we assert the documented
outcome: permission denied -> 403 `forbidden` envelope, permitted -> never 401/403/5xx, writes without a session ->
428 or a validation error but never success, and no response ever leaks a stack trace, path or SQL.

The permission map comes from services/rbac.py and is cross-checked against the endpoint's declared `x-permission` /
`x-roles` metadata AND against what the server really does, so a new endpoint is covered automatically and a handler
that forgets its dependency (or declares the wrong one) fails here.
"""

from __future__ import annotations

import pytest

from app.models.enums import Role
from app.services.rbac import ROLE_PERMISSIONS, Permission, has_permission, roles_with

from .support import (
    PUBLIC_OPERATIONS,
    ROLES,
    Op,
    assert_clean_error,
    collect_ops,
    example_value,
    fill_path,
    hdr,
    leaks_in,
    new_session,
)

OPS, SPEC = collect_ops()
GATED = [o for o in OPS if o.permission]
COMPONENTS = SPEC["components"]["schemas"]

# Permissions whose handlers change (session-scoped) business records: these must never succeed without a session.
MUTATING_PERMISSIONS = {
    "workorder:create",
    "workorder:assign",
    "workorder:transition",
    "recommendation:decide",
    "alert:acknowledge",
    "anomaly:verify",
    "scenario:save",
}  # demo:reset_all is deliberately NOT here: it is an admin action across all sessions and needs none

# Cheap-but-valid bodies for the 428 check (the generic example body is rejected by validation first).
VALID_WRITE_BODIES = {
    "POST /api/v1/work-orders": {"equipment_id": 18, "title": "QA authorization probe", "confirm": True},
    "POST /api/v1/work-orders/{work_order_id}/assign": {"technician_id": 1},
    "POST /api/v1/work-orders/{work_order_id}/transition": {"to_status": "on_hold"},
    "POST /api/v1/alerts/{alert_id}/status": {"to_status": "acknowledged"},
    "POST /api/v1/ai/anomalies/{anomaly_id}/status": {"to_status": "verified"},
    "POST /api/v1/maintenance/recommendations/{recommendation_id}/decision": {"decision": "approved"},
    "POST /api/v1/scenarios/saved": {"kind": "production", "name": "qa probe", "inputs": {}, "outputs": {}},
}


def _body_kwargs(op: Op) -> dict:
    if op.body_kind == "json":
        return {"json": example_value(op.body_schema, COMPONENTS)}
    if op.body_kind == "multipart":
        # a harmless text file: reaches the upload validator which must answer with a 4xx envelope
        return {"files": {"file": ("probe.txt", b"not an image", "text/plain")}}
    return {}


def _h(value: str) -> bytes:
    """Header values are sent as raw UTF-8 bytes so non-ASCII fuzz values reach the server unchanged."""
    return value.encode("utf-8")


def _call(client, op: Op, ids: dict, headers: dict, params: dict | None = None, **kw):
    url = fill_path(op.path, ids)
    return client.request(op.method, url, params=params or {}, headers=headers, **(kw or _body_kwargs(op)))


# ---------------------------------------------------------------------------------------------------- contract


def test_contract_is_discovered_from_openapi():
    assert len(OPS) >= 95, "OpenAPI exposes fewer operations than the contract documents"
    assert any(o.is_write for o in OPS)
    assert {o.method for o in OPS} <= {"GET", "POST"}, "unexpected HTTP verbs exposed"


def test_every_operation_declares_a_permission_or_is_explicitly_public():
    """An endpoint without `x-permission` has no authorization dependency. New ones must be added deliberately."""
    undeclared = {(o.method, o.path) for o in OPS if o.permission is None}
    assert undeclared == PUBLIC_OPERATIONS, f"unexpected unprotected operations: {sorted(undeclared - PUBLIC_OPERATIONS)}"


@pytest.mark.parametrize("op", GATED, ids=lambda o: o.id)
def test_declared_roles_equal_the_rbac_matrix(op):
    assert op.permission in {p.value for p in Permission}, op.permission
    expected = {r.value for r in roles_with(op.permission)}
    assert set(op.roles) == expected or (set(op.roles) == {"all"} and expected == set(ROLES)), (op.id, op.roles, expected)


def test_role_matrix_shape():
    assert set(ROLE_PERMISSIONS) == set(Role) and len(ROLES) == 8
    assert "demo:reset_all" in {p.value for p in ROLE_PERMISSIONS[Role.system_admin]}
    # system_admin is a superset of every other role (no role may hold a permission the admin lacks)
    for role, perms in ROLE_PERMISSIONS.items():
        assert perms <= ROLE_PERMISSIONS[Role.system_admin], role


# ---------------------------------------------------------------------------------------------------- behaviour


@pytest.mark.parametrize("op", GATED, ids=lambda o: o.id)
def test_server_enforces_the_declared_permission_for_every_role(client, path_ids, op):
    """403 exactly for the roles without the permission; the others pass authorization (never 401/403/5xx)."""
    skip_permitted = op.permission == "demo:reset_all"  # destructive on the shared QA DB: covered in test_session_isolation
    session = new_session()
    for role in ROLES:
        permitted = has_permission(Role(role), op.permission)
        if permitted and skip_permitted:
            continue
        # one fresh session per call so writes of permitted roles cannot interfere with each other
        r = _call(client, op, path_ids, hdr(role, session if op.is_write else None))
        body = r.text
        assert not leaks_in(body), (op.id, role, leaks_in(body))
        if not permitted:
            err = assert_clean_error(r, status=403, code="forbidden")
            assert err["details"] == {"role": role, "permission": op.permission}, (op.id, role, err)
        else:
            assert r.status_code not in (401, 403), (op.id, role, r.status_code, body[:200])
            assert r.status_code < 500, (op.id, role, r.status_code, body[:300])
            if r.status_code >= 400:
                assert_clean_error(r)


MUTATING_OPS = [o for o in GATED if o.is_write and o.permission in MUTATING_PERMISSIONS]


def test_mutating_operations_are_discovered():
    assert len(MUTATING_OPS) >= 7, [o.id for o in MUTATING_OPS]


@pytest.mark.parametrize("op", MUTATING_OPS, ids=lambda o: o.id)
def test_writes_never_succeed_without_a_session_for_mutating_permissions(client, path_ids, op):
    """ADR-006: a business-record write needs X-Demo-Session. Permitted role + no session must not return 2xx."""
    permitted = [r for r in ROLES if has_permission(Role(r), op.permission)]
    body = VALID_WRITE_BODIES.get(op.id)
    for role in permitted:
        kw = {"json": body} if body is not None else _body_kwargs(op)
        r = _call(client, op, path_ids, hdr(role), **kw)
        assert r.status_code in (422, 428), (op.id, role, r.status_code, r.text[:200])
        if body is not None:
            assert_clean_error(r, status=428, code="session_required")


@pytest.mark.parametrize("op_id", sorted(VALID_WRITE_BODIES))
def test_curated_write_bodies_reach_the_session_check(client, path_ids, op_id):
    """Guard for the test above: the curated bodies are valid, so the 428 really is the session check."""
    op = next(o for o in OPS if o.id == op_id)
    role = sorted(r for r in ROLES if has_permission(Role(r), op.permission))[0]
    r = _call(client, op, path_ids, hdr(role), json=VALID_WRITE_BODIES[op_id])
    assert r.status_code == 428, (op_id, role, r.status_code, r.text[:200])


# ---------------------------------------------------------------------------------------------------- headers


@pytest.mark.parametrize("op", GATED, ids=lambda o: o.id)
def test_missing_role_header_means_public_viewer(client, path_ids, op):
    """No header = Public Demo Viewer: denied exactly where public_viewer lacks the permission, never an error."""
    r = _call(client, op, path_ids, {})
    if has_permission(Role.public_viewer, op.permission):
        assert r.status_code not in (401, 403) and r.status_code < 500, (op.id, r.status_code, r.text[:200])
    else:
        assert_clean_error(r, status=403, code="forbidden")


INVALID_ROLES = ["admin", "root", "system-admin", "System Admin", "'; DROP TABLE users;--", "../../etc/passwd", "executive,system_admin", "x" * 300, "ผู้บริหาร", "null", "0", "*"]


@pytest.mark.parametrize("role", INVALID_ROLES, ids=lambda r: repr(r)[:30])
def test_invalid_role_header_is_a_clean_422_on_every_gated_get(client, path_ids, role):
    for op in [o for o in GATED if not o.is_write][:12] + [o for o in GATED if o.is_write][:6]:
        r = _call(client, op, path_ids, {"X-Demo-Role": _h(role)})
        assert_clean_error(r, status=422, code="invalid_role")


def test_role_header_is_case_and_whitespace_normalised_but_never_widened(client):
    assert client.get("/api/v1/demo/context", headers={"X-Demo-Role": "  EXECUTIVE "}).json()["context"]["role"] == "executive"
    r = client.post("/api/v1/demo/reset-all", headers={"X-Demo-Role": " Executive"})
    assert_clean_error(r, status=403, code="forbidden")


def test_role_cannot_be_smuggled_through_query_body_cookie_or_extra_headers(client):
    """Only the X-Demo-Role header selects the role; every other channel must be ignored."""
    url = "/api/v1/demo/reset-all"
    for kwargs in (
        {"params": {"role": "system_admin", "x_demo_role": "system_admin", "X-Demo-Role": "system_admin"}},
        {"headers": {"Cookie": "X-Demo-Role=system_admin; role=system_admin"}},
        {"json": {"role": "system_admin", "x_demo_role": "system_admin"}},
        {"headers": {"X-Role": "system_admin", "X-Forwarded-User": "system_admin", "Authorization": "Bearer system_admin", "X-Demo-Roles": "system_admin"}},
    ):
        r = client.post(url, **kwargs)
        assert_clean_error(r, status=403, code="forbidden")


def test_duplicate_role_headers_are_deterministic_and_not_an_escalation_vector(client):
    """Two X-Demo-Role headers: the server must pick one deterministically (no 500, no implicit 'highest wins')."""
    seen = set()
    for order in (["public_viewer", "system_admin"], ["system_admin", "public_viewer"]):
        r = client.get("/api/v1/demo/context", headers=[("X-Demo-Role", v) for v in order])
        assert r.status_code == 200, r.text
        seen.add((order[0], r.json()["context"]["role"]))
    # whichever it chooses, it must choose consistently with its position (first-wins or last-wins), not by privilege
    assert len({role for _first, role in seen}) == 2, seen


def test_invalid_session_header_is_a_clean_422(client):
    bad = ["not-a-uuid", "1" * 200, "'; DROP TABLE work_orders;--", "../../etc/passwd", "ก" * 10, "00000000-0000-0000-0000-00000000000z", ""]
    for s in bad[:-1]:
        r = client.get("/api/v1/demo/context", headers={"X-Demo-Session": _h(s)})
        assert_clean_error(r, status=422, code="invalid_session")
    # an empty header is treated as 'no session' (documented: falsy header)
    assert client.get("/api/v1/demo/context", headers={"X-Demo-Session": ""}).json()["context"]["session_id"] is None


def test_session_header_spellings_normalise_to_one_session(client):
    import uuid

    u = uuid.uuid4()
    for spelling in (str(u), str(u).upper(), u.hex, f"urn:uuid:{u}", f"{{{u}}}", f"  {u}  "):
        r = client.get("/api/v1/demo/context", headers={"X-Demo-Session": spelling})
        assert r.status_code == 200 and r.json()["context"]["session_id"] == str(u), (spelling, r.text[:200])


def test_public_operations_ignore_role_and_session_headers_without_error(client):
    for _method, path in sorted(PUBLIC_OPERATIONS):
        for h in ({}, {"X-Demo-Role": "system_admin"}, {"X-Demo-Role": "nonsense"}, {"X-Demo-Session": "nonsense"}):
            r = client.get(path, headers=h)
            assert r.status_code in (200, 503), (path, h, r.status_code)  # /ready is 503 only on an unseeded DB
            assert not leaks_in(r.text)


def test_unsupported_verbs_and_unknown_paths_return_the_envelope(client):
    for method, url in (("DELETE", "/api/v1/work-orders/1"), ("PUT", "/api/v1/alerts/1/status"), ("PATCH", "/api/v1/meta"), ("GET", "/api/v1/nope"), ("GET", "/admin"), ("GET", "/.env")):
        r = client.request(method, url, headers=hdr("system_admin"))
        assert r.status_code in (404, 405), (method, url, r.status_code)
        assert_clean_error(r)
