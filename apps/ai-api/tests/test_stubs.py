"""Every contract stub returns HTTP 501 with the standard error envelope (after validation + RBAC pass)."""

from __future__ import annotations

import re
import uuid

import pytest

from app.api.v1 import iter_contract_routes

PATH_SAMPLES = {
    "stage_code": "PRESSING",
    "code": "NORMAL_DAY",
    "name": "oer_forecast",
    "report_type": "executive",
    "slug": "kpi-guide",
    "ref": "kb:kpi-guide#0",
    "copilot_session_id": str(uuid.uuid4()),
}
QUERY_SAMPLES = {"metric": "oer_pct"}

ROI_INPUTS = {
    "daily_ffb_t": 1000,
    "operating_days": 300,
    "current_oer_pct": 20.5,
    "target_oer_pct": 21.0,
    "cpo_price_thb_per_kg": 35,
    "downtime_h_per_month": 20,
    "processing_capacity_tph": 60,
    "energy_cost_thb_per_year": 5_000_000,
    "maintenance_expense_thb_per_year": 8_000_000,
    "efficiency_improvement_pct": 5,
    "implementation_cost_thb": 6_000_000,
    "recurring_cost_thb_per_year": 1_200_000,
}
BODY_SAMPLES = {
    "/api/v1/alerts/{alert_id}/status": {"to_status": "acknowledged"},
    "/api/v1/ai/anomalies/{anomaly_id}/status": {"to_status": "verified"},
    "/api/v1/ai/models/{name}/run": {},
    "/api/v1/maintenance/recommendations/{recommendation_id}/decision": {"decision": "approved"},
    "/api/v1/maintenance/impact": {"downtime_hours": 4},
    "/api/v1/work-orders": {"equipment_id": 1, "title": "Inspect press bearing", "confirm": True},
    "/api/v1/work-orders/{work_order_id}/assign": {"technician_id": 1},
    "/api/v1/work-orders/{work_order_id}/transition": {"to_status": "in_progress"},
    "/api/v1/logistics/queue-simulation": {},
    "/api/v1/energy/what-if": {"efficiency_improvement_pct": 5},
    "/api/v1/scenarios/saved": {"kind": "production", "name": "x", "inputs": {}, "outputs": {}},
    "/api/v1/scenarios/production/calculate": {"oer_pct": 21},
    "/api/v1/roi/calculate": ROI_INPUTS,
    "/api/v1/roi/sensitivity": {"inputs": ROI_INPUTS},
    "/api/v1/roi/export": {"inputs": ROI_INPUTS},
    "/api/v1/copilot/chat": {"message": "OER today?"},
    "/api/v1/demo/tick": {},
}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _stub_routes():
    for full_path, route in iter_contract_routes():
        if (route.openapi_extra or {}).get("x-status") == "stub":
            for method in route.methods:
                yield method, full_path, route


@pytest.mark.parametrize("method,full_path,route", list(_stub_routes()), ids=lambda v: v if isinstance(v, str) else "")
def test_stub_returns_501_envelope(client, method, full_path, route):
    path = full_path
    for name in re.findall(r"{(\w+)}", path):
        path = path.replace("{" + name + "}", PATH_SAMPLES.get(name, "1"))
    params = {}
    if full_path == "/api/v1/executive/series":
        params = QUERY_SAMPLES
    headers = {"X-Demo-Role": "system_admin", "X-Demo-Session": str(uuid.uuid4())}
    if method == "GET":
        r = client.get(path, params=params, headers=headers)
    elif full_path == "/api/v1/cv/ffb-assessment":
        r = client.post(path, headers=headers, files={"file": ("a.png", PNG, "image/png")})
    else:
        r = client.post(path, params=params, headers=headers, json=BODY_SAMPLES.get(full_path, {}))
    assert r.status_code == 501, (full_path, r.status_code, r.text)
    err = r.json()["error"]
    assert err["code"] == "not_implemented"
    assert err["details"]["owner"] == route.openapi_extra["x-owner"]
    assert err["details"]["status"] == "planned"


def test_contract_has_all_operations_and_stub_enumeration_works():
    # Wave 0 asserted "> 70 stubs"; owners flip operations to implemented, so the guard is now: all 94+ operations exist and every
    # remaining stub is enumerated with owner metadata.
    assert len(list(iter_contract_routes())) >= 94
    assert all((r.openapi_extra or {}).get("x-owner") for _m, _p, r in _stub_routes())
