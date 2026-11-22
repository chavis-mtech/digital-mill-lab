"""Simulated RBAC: matrix properties, server-side enforcement, and contract consistency."""

from __future__ import annotations

import uuid

import pytest

from app.api.v1 import iter_contract_routes
from app.models.enums import Role
from app.services.rbac import ROLE_PERMISSIONS, Permission, copilot_tools_for, has_permission, is_read_only

WO_BODY = {"equipment_id": 1, "title": "Inspect press bearing", "confirm": True}


def test_eight_roles_defined():
    assert len(ROLE_PERMISSIONS) == 8


def test_public_viewer_is_read_only():
    assert is_read_only(Role.public_viewer)
    for p in (Permission.workorder_create, Permission.scenario_save, Permission.model_run, Permission.demo_reset_all):
        assert not has_permission(Role.public_viewer, p)


def test_every_role_can_read_every_dashboard_except_documented_gaps():
    for role in Role:
        for p in (Permission.read_executive, Permission.read_production, Permission.read_logistics):
            assert has_permission(role, p)
    assert not has_permission(Role.logistics_officer, Permission.read_ai)


def test_write_rules_from_spec():
    assert has_permission(Role.maintenance_engineer, Permission.workorder_create)
    assert has_permission(Role.maintenance_engineer, Permission.workorder_transition)
    assert has_permission(Role.ai_analyst, Permission.model_run)
    assert not has_permission(Role.maintenance_engineer, Permission.model_run)
    assert has_permission(Role.system_admin, Permission.demo_reset_all)
    assert not has_permission(Role.factory_manager, Permission.demo_reset_all)
    assert not has_permission(Role.executive, Permission.workorder_create)


def test_copilot_tool_permissions_per_role():
    assert "get_equipment_health" not in copilot_tools_for(Role.logistics_officer)
    assert "get_logistics_summary" in copilot_tools_for(Role.logistics_officer)
    assert "draft_work_order" not in copilot_tools_for(Role.public_viewer)
    assert "draft_work_order" in copilot_tools_for(Role.maintenance_engineer)
    assert set(copilot_tools_for(Role.system_admin)) >= set(copilot_tools_for(Role.factory_manager))


@pytest.mark.parametrize("role", ["public_viewer", "executive", "logistics_officer", "ai_analyst"])
def test_work_order_create_denied(client, role):
    r = client.post("/api/v1/work-orders", json=WO_BODY, headers={"X-Demo-Role": role, "X-Demo-Session": str(uuid.uuid4())})
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "forbidden"
    assert err["details"] == {"role": role, "permission": "workorder:create"}


@pytest.mark.parametrize("role", ["maintenance_engineer", "factory_manager", "production_engineer", "system_admin"])
def test_work_order_create_permitted_reaches_handler(client, role):
    # confirm=false: the handler is reached (RBAC passed) and refuses before touching the DB (work orders are implemented by backend-b)
    r = client.post("/api/v1/work-orders", json={**WO_BODY, "confirm": False}, headers={"X-Demo-Role": role, "X-Demo-Session": str(uuid.uuid4())})
    assert r.status_code == 422 and r.json()["error"]["code"] == "confirmation_required"


def test_reset_all_admin_only(client):
    assert client.post("/api/v1/demo/reset-all", headers={"X-Demo-Role": "factory_manager"}).status_code == 403
    # the permitted path (system_admin) is implemented by backend-b and needs a seeded DB: see tests/backend_b/test_demo_state.py


def test_model_run_ai_analyst_only(client):
    assert client.post("/api/v1/ai/models/oer_forecast/run", json={}, headers={"X-Demo-Role": "maintenance_engineer"}).status_code == 403
    # implemented by ml (was a 501 stub): permitted role passes RBAC; the empty test DB yields 503 data_unavailable
    assert client.post("/api/v1/ai/models/oer_forecast/run", json={}, headers={"X-Demo-Role": "ai_analyst"}).status_code not in (401, 403)


def test_roles_endpoint(client):
    items = client.get("/api/v1/demo/roles").json()["items"]
    assert len(items) == 8
    viewer = next(i for i in items if i["role"] == "public_viewer")
    assert viewer["read_only"] is True


def test_openapi_permission_matches_dependency():
    """x-permission in the contract must equal the permission the handler actually enforces."""
    routes = list(iter_contract_routes())
    assert len(routes) > 80
    for _path, route in routes:
        declared = (route.openapi_extra or {}).get("x-permission")
        enforced = {getattr(d.call, "permission", None) for d in route.dependant.dependencies} - {None}
        enforced_values = {p.value for p in enforced}
        if declared is None:
            assert not enforced_values, route.path
        else:
            assert enforced_values == {declared}, (route.path, declared, enforced_values)
