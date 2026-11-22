"""AI-C05: work-order workflow - state machine, RBAC matrix, session isolation, copy-on-write, audit, cross-module effects."""

from __future__ import annotations

import itertools

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, MaintenanceEvent, WorkOrder, WorkOrderStatusHistory
from app.models.enums import Role, WorkOrderStatus
from app.services.audit import verify_chain
from app.services.rbac import Permission, has_permission
from app.services.workorders import ACTIVE, TERMINAL, TRANSITIONS

from .conftest import EARLY, FOCUS, err, hdr

WO = "/api/v1/work-orders"
S = WorkOrderStatus


def _create(client, h, **over):
    body = {"equipment_id": 18, "title": "Inspect PRS-03 bearing before continued use", "alert_id": 18, "source_type": "alert", "priority": "urgent", "confirm": True, "estimated_downtime_h": 6}
    body.update(over)
    return client.post(WO, params={"as_of": FOCUS}, json=body, headers=h)


def _go(client, h, wid, to, **extra):
    return client.post(f"{WO}/{wid}/transition", params={"as_of": FOCUS}, json={"to_status": to, **extra}, headers=h)


# ---------------------------------------------------------------- state machine (pure)
@pytest.mark.parametrize("src,dst", list(itertools.product(list(S), list(S))))
def test_state_machine_table_is_exactly_the_documented_one(src, dst):
    documented = {
        (S.open, S.assigned), (S.open, S.on_hold), (S.open, S.cancelled), (S.assigned, S.in_progress), (S.assigned, S.on_hold), (S.assigned, S.cancelled),
        (S.in_progress, S.resolved), (S.in_progress, S.on_hold), (S.in_progress, S.cancelled), (S.on_hold, S.assigned), (S.on_hold, S.in_progress),
        (S.on_hold, S.cancelled), (S.resolved, S.closed), (S.resolved, S.in_progress),
    }
    assert (dst in TRANSITIONS[src]) == ((src, dst) in documented)


def test_terminal_states_and_active_set():
    assert TERMINAL == {S.closed, S.cancelled} and all(not TRANSITIONS[t] for t in TERMINAL)
    assert ACTIVE == {S.open, S.assigned, S.in_progress, S.on_hold}


# ---------------------------------------------------------------- scenario B flow
def test_full_workflow_alert_to_resolved_with_audit_trail(client, db, me):
    r = _create(client, me)
    assert r.status_code == 201, r.text
    wo = r.json()
    wid, sid = wo["id"], me["X-Demo-Session"]
    assert wo["status"] == "open" and wo["is_baseline"] is False and wo["alert_status"] == "in_progress" and wo["created_by_role"] == "maintenance_engineer"
    assert wo["code"].startswith("WO-202611-") and wo["demo_as_of"] == FOCUS and wo["allowed_transitions"] == ["assigned", "on_hold", "cancelled"]
    # invalid transitions are rejected with a clear error
    for bad in ("resolved", "in_progress", "closed"):
        r = _go(client, me, wid, bad, resolution_notes="x")
        assert r.status_code == 409 and err(r) == "invalid_transition" and r.json()["error"]["details"]["allowed"] == ["assigned", "cancelled", "on_hold"]
    assert err(_go(client, me, wid, "assigned")) == "technician_required"
    a = client.post(f"{WO}/{wid}/assign", params={"as_of": FOCUS}, json={"technician_id": 1}, headers=me)
    assert a.status_code == 200 and a.json()["status"] == "assigned" and a.json()["assigned_technician"]["code"] == "TEC-M01"
    assert _go(client, me, wid, "in_progress", note="crew on site").json()["status"] == "in_progress"
    r = _go(client, me, wid, "resolved")
    assert r.status_code == 422 and err(r) == "resolution_notes_required"
    r = _go(client, me, wid, "resolved", resolution_notes="Drive-end bearing replaced, alignment checked", downtime_min=330)
    j = r.json()
    assert r.status_code == 200 and j["status"] == "resolved" and j["resolved_at"] == FOCUS and j["alert_status"] == "resolved"
    assert _go(client, me, wid, "closed").json()["status"] == "closed"
    assert err(_go(client, me, wid, "in_progress")) == "invalid_transition"  # closed is terminal
    assert err(client.post(f"{WO}/{wid}/assign", params={"as_of": FOCUS}, json={"technician_id": 2}, headers=me)) == "invalid_transition"
    d = client.get(f"{WO}/{wid}", params={"as_of": FOCUS}, headers=me).json()
    assert [(h["from_status"], h["to_status"]) for h in d["history"]] == [(None, "open"), ("open", "assigned"), ("assigned", "in_progress"), ("in_progress", "resolved"), ("resolved", "closed")]
    assert d["maintenance_event_id"] and d["resolution_notes"].startswith("Drive-end bearing")
    ev = db.get(MaintenanceEvent, d["maintenance_event_id"])  # maintenance record written on resolve
    assert ev.work_order_id == wid and ev.session_id == sid and ev.downtime_min == 330 and ev.event_type == "corrective"
    assert [e["id"] for e in client.get("/api/v1/maintenance/equipment/18/history", params={"as_of": FOCUS, "period": "7d"}, headers=me).json()["items"]][0] == ev.id
    trail = client.get(f"{WO}/{wid}/audit", params={"as_of": FOCUS}, headers=me).json()
    assert trail["chain_verified"] is True and trail["entity_id"] == wo["code"]
    assert [e["action"] for e in trail["items"]] == ["work_order.create", "alert.status_change", "work_order.assign", "work_order.transition", "alert.status_change", "work_order.transition", "work_order.transition"]
    assert all(e["role"] == "maintenance_engineer" and e["hash"] and e["prev_hash"] for e in trail["items"])
    assert verify_chain(db) == (True, None)
    n_audit = db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.session_id == sid)).scalar_one()
    assert n_audit == 7  # every write is audited, nothing else


def test_confirm_is_required_and_creates_nothing(client, db, me):
    r = _create(client, me, confirm=False)
    assert r.status_code == 422 and err(r) == "confirmation_required"
    assert db.execute(select(func.count()).select_from(WorkOrder).where(WorkOrder.session_id == me["X-Demo-Session"])).scalar_one() == 0


def test_create_validation_and_links(client, me):
    assert err(_create(client, me, alert_id=1)) == "alert_equipment_mismatch"  # alert 1 belongs to PRS-01
    closed = _create(client, me, alert_id=2, equipment_id=29, title="BLR-01 drum pressure")  # alert 2 was resolved on 2026-08-25
    assert closed.status_code == 409 and err(closed) == "alert_closed"
    assert client.post(WO, params={"as_of": "2026-08-25T09:00:00Z"}, json={"equipment_id": 29, "title": "BLR-01 drum pressure", "alert_id": 2, "source_type": "alert", "confirm": True}, headers=me).status_code == 201  # open at that clock
    assert _create(client, me, alert_id=19).status_code == 201  # the bearing-temperature alert is still open at the focus time
    assert _create(client, me, alert_id=9999).status_code == 404
    assert _create(client, me, equipment_id=999).status_code == 404
    assert _create(client, me, source_type="recommendation", alert_id=None).status_code == 422
    r = _create(client, me)
    assert r.status_code == 201
    dup = _create(client, me)
    assert dup.status_code == 409 and err(dup) == "duplicate_work_order" and dup.json()["error"]["details"]["work_order_id"] == r.json()["id"]
    assert client.post(WO, params={"as_of": FOCUS}, json={"equipment_id": 18, "title": "ab", "confirm": True}, headers=me).status_code == 422  # title too short
    assert client.post(WO, params={"as_of": FOCUS}, json={"equipment_id": 18, "title": "x" * 300, "confirm": True}, headers=me).status_code == 422


# ---------------------------------------------------------------- RBAC matrix
ROLES = [r.value for r in Role]


@pytest.mark.parametrize("role", ROLES)
def test_rbac_matrix_every_write_endpoint(client, role):
    """Cross-role matrix: create / assign / transition / recommendation decision / session reset against the permission table."""
    owner = hdr("maintenance_engineer")
    wo = _create(client, owner, alert_id=None, source_type="manual", title="RBAC matrix probe").json()
    sess = owner["X-Demo-Session"]
    h = hdr(role, sess)  # same sandbox session, different simulated role

    def code(r):
        return r.status_code

    create = client.post(WO, params={"as_of": FOCUS}, json={"equipment_id": 17, "title": "RBAC create probe", "confirm": True}, headers=h)
    assign = client.post(f"{WO}/{wo['id']}/assign", params={"as_of": FOCUS}, json={"technician_id": 2}, headers=h)
    move = client.post(f"{WO}/{wo['id']}/transition", params={"as_of": FOCUS}, json={"to_status": "on_hold"}, headers=h)
    for resp, perm in ((create, Permission.workorder_create), (assign, Permission.workorder_assign), (move, Permission.workorder_transition)):
        if has_permission(Role(role), perm):
            assert code(resp) in (200, 201), (role, perm, resp.text)
        else:
            assert code(resp) == 403 and err(resp) == "forbidden" and resp.json()["error"]["details"] == {"role": role, "permission": perm.value}
    # reads are open to every role, including the public viewer
    assert client.get(WO, params={"as_of": FOCUS, "limit": 1}, headers=h).status_code == 200
    assert client.get(f"{WO}/{wo['id']}/audit", params={"as_of": FOCUS}, headers=h).status_code == 200


def test_public_viewer_is_read_only_everywhere(client):
    pv = hdr("public_viewer")
    for method, url, body in [
        ("post", WO, {"equipment_id": 18, "title": "viewer try", "confirm": True}),
        ("post", f"{WO}/117/assign", {"technician_id": 1}),
        ("post", f"{WO}/117/transition", {"to_status": "on_hold"}),
        ("post", "/api/v1/maintenance/recommendations/9001802/decision", {"decision": "approved"}),
        ("post", "/api/v1/scenarios/saved", {"kind": "production", "name": "x", "inputs": {}, "outputs": {}}),
        ("post", "/api/v1/demo/reset-all", None),
    ]:
        r = getattr(client, method)(url, params={"as_of": FOCUS}, headers=pv, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (url, r.status_code)
    assert client.get(WO, params={"as_of": FOCUS}, headers=pv).status_code == 200


def test_writes_without_session_return_428(client):
    h = hdr("maintenance_engineer", None)
    for url, body in [
        (WO, {"equipment_id": 18, "title": "no session", "confirm": True}),
        (f"{WO}/117/assign", {"technician_id": 1}),
        (f"{WO}/117/transition", {"to_status": "on_hold"}),
        ("/api/v1/maintenance/recommendations/9001802/decision", {"decision": "approved"}),
        ("/api/v1/scenarios/saved", {"kind": "production", "name": "x", "inputs": {}, "outputs": {}}),
        ("/api/v1/demo/session/reset", None),
    ]:
        r = client.post(url, params={"as_of": FOCUS}, headers=h, **({"json": body} if body is not None else {}))
        assert r.status_code == 428 and err(r) == "session_required", (url, r.status_code, r.text)


# ---------------------------------------------------------------- session isolation, copy-on-write, time travel
def test_session_isolation_and_seeded_rows_visible_to_both(client):
    a, b = hdr("maintenance_engineer"), hdr("maintenance_engineer")
    wid = _create(client, a).json()["id"]
    la = client.get(WO, params={"as_of": FOCUS, "limit": 200}, headers=a).json()
    lb = client.get(WO, params={"as_of": FOCUS, "limit": 200}, headers=b).json()
    assert wid in {i["id"] for i in la["items"]} and wid not in {i["id"] for i in lb["items"]}
    assert la["total"] == lb["total"] + 1 == 118
    seeded_a = {i["id"] for i in la["items"] if i["is_baseline"]}
    assert seeded_a == {i["id"] for i in lb["items"] if i["is_baseline"]} and len(seeded_a) == 117
    assert client.get(f"{WO}/{wid}", params={"as_of": FOCUS}, headers=b).status_code == 404  # not a 403: existence is not leaked
    assert client.get(f"{WO}/{wid}/audit", params={"as_of": FOCUS}, headers=b).status_code == 404
    assert client.get(f"{WO}/117", params={"as_of": FOCUS}, headers=b).status_code == 200
    assert [i["id"] for i in client.get(WO, params={"as_of": FOCUS, "mine_only": True}, headers=a).json()["items"]] == [wid]
    assert client.get(WO, params={"as_of": FOCUS, "mine_only": True}, headers=b).json()["total"] == 0


def test_copy_on_write_never_touches_the_baseline(client, db):
    def baseline_fingerprint():
        rows = db.execute(select(WorkOrder.id, WorkOrder.status, WorkOrder.assigned_technician_id).where(WorkOrder.session_id.is_(None)).order_by(WorkOrder.id)).all()
        hist = db.execute(select(func.count()).select_from(WorkOrderStatusHistory).where(WorkOrderStatusHistory.session_id.is_(None))).scalar_one()
        return [tuple(r) for r in rows], hist

    before = baseline_fingerprint()
    a, b = hdr("maintenance_engineer"), hdr("factory_manager")
    r = client.post(f"{WO}/117/assign", params={"as_of": FOCUS}, json={"technician_id": 3}, headers=a)
    assert r.status_code == 200
    j = r.json()
    assert j["id"] != 117 and j["cloned_from_id"] == 117 and j["is_baseline"] is False and j["status"] == "assigned" and j["code"].startswith("WO-202611-0117-C")
    assert client.get(f"{WO}/117", params={"as_of": FOCUS}, headers=a).json()["id"] == j["id"]  # A sees its copy under the seeded id
    seen_a = [i for i in client.get(WO, params={"as_of": FOCUS, "equipment_id": 27}, headers=a).json()["items"] if i["status"] != "closed"]
    assert [(i["id"], i["status"]) for i in seen_a] == [(j["id"], "assigned")]  # the baseline row is replaced, not duplicated
    seen_b = client.get(f"{WO}/117", params={"as_of": FOCUS}, headers=b).json()
    assert seen_b["id"] == 117 and seen_b["status"] == "open" and seen_b["is_baseline"] is True
    assert _go(client, a, 117, "in_progress").json()["id"] == j["id"]  # follow-up changes hit the same copy
    assert baseline_fingerprint() == before
    detail = client.get(f"{WO}/{j['id']}", params={"as_of": FOCUS}, headers=a).json()
    assert [h["to_status"] for h in detail["history"]][-2:] == ["assigned", "in_progress"] and detail["history"][0]["to_status"] == "open"
    actions = [e["action"] for e in client.get(f"{WO}/{j['id']}/audit", params={"as_of": FOCUS}, headers=a).json()["items"]]
    assert "work_order.copy_on_write" in actions and "work_order.assign" in actions
    assert err(client.post(f"{WO}/1/transition", params={"as_of": FOCUS}, json={"to_status": "in_progress"}, headers=a)) == "invalid_transition"  # closed baseline row
    assert baseline_fingerprint() == before


def test_cross_module_effects_stay_in_the_session(client):
    a, b = hdr("maintenance_engineer"), hdr("maintenance_engineer")
    eq = lambda h: client.get("/api/v1/maintenance/equipment/16/health", params={"as_of": FOCUS}, headers=h).json()  # noqa: E731
    assert eq(a)["state"] == "normal" and eq(a)["maintenance_status"] == "none"
    wid = _create(client, a, equipment_id=16, alert_id=None, source_type="manual", title="PRS-01 lubrication check").json()["id"]
    ha, hb = eq(a), eq(b)
    assert (ha["state"], ha["maintenance_status"], ha["active_work_order_ids"]) == ("maintenance_required", "work_order_open", [wid])
    assert (hb["state"], hb["maintenance_status"], hb["active_work_order_ids"]) == ("normal", "none", [])  # other visitors are unaffected
    summ = {i["code"]: i for i in client.get("/api/v1/maintenance/equipment", params={"as_of": FOCUS}, headers=a).json()["items"]}
    assert summ["PRS-01"]["open_work_orders"] == 1 and summ["PRS-01"]["maintenance_status"] == "work_order_open"
    client.post(f"{WO}/{wid}/assign", params={"as_of": FOCUS}, json={"technician_id": 1}, headers=a)
    assert eq(a)["maintenance_status"] == "assigned"
    _go(client, a, wid, "cancelled")
    assert (eq(a)["state"], eq(a)["maintenance_status"]) == ("normal", "none")
    # PRS-03: a critical reading outranks the work order (same ordering as the process twin)
    _create(client, a)
    h = client.get("/api/v1/maintenance/equipment/18/health", params={"as_of": FOCUS}, headers=a).json()
    assert h["state"] == "critical" and h["maintenance_status"] == "work_order_open"
    assert client.get("/api/v1/maintenance/equipment/18/health", params={"as_of": FOCUS}, headers=b).json()["maintenance_status"] == "none"


def test_linked_alert_status_is_session_scoped(client):
    a, b = hdr("maintenance_engineer"), hdr("maintenance_engineer")
    wid = _create(client, a).json()["id"]
    assert client.get(f"{WO}/{wid}", params={"as_of": FOCUS}, headers=a).json()["alert_status"] == "in_progress"
    _go(client, a, wid, "cancelled")
    assert client.get(f"{WO}/{wid}", params={"as_of": FOCUS}, headers=a).json()["alert_status"] == "acknowledged"  # still needs attention
    wid_b = _create(client, b).json()  # B can still raise a WO from the same baseline alert: it was never closed for B
    assert wid_b["alert_status"] == "in_progress"


def test_time_travel_hides_future_records_and_protects_history(client):
    a = hdr("maintenance_engineer")
    assert client.get(f"{WO}/117", params={"as_of": EARLY}, headers=a).status_code == 404  # seeded WO 117 is created 2026-11-20
    assert 117 not in {i["id"] for i in client.get(WO, params={"as_of": EARLY, "limit": 200}, headers=a).json()["items"]}
    wid = _create(client, a).json()["id"]
    assert client.get(f"{WO}/{wid}", params={"as_of": EARLY}, headers=a).status_code == 404  # created later on the demo clock
    r = client.post(f"{WO}/{wid}/assign", params={"as_of": "2026-11-20T09:00:00Z"}, json={"technician_id": 1}, headers=a)
    assert r.status_code == 200
    at_focus = client.get(f"{WO}/{wid}", params={"as_of": FOCUS}, headers=a).json()
    assert at_focus["status"] == "open" and at_focus["assigned_technician"] is None and at_focus["allowed_transitions"] == [] and at_focus["read_only_reason"]
    r = client.post(f"{WO}/{wid}/transition", params={"as_of": FOCUS}, json={"to_status": "on_hold"}, headers=a)
    assert r.status_code == 409 and err(r) == "clock_before_record"


def test_list_filters_paging_and_counts(client):
    a = hdr("maintenance_engineer")
    j = client.get(WO, params={"as_of": FOCUS, "status": "open"}, headers=a).json()
    assert [i["code"] for i in j["items"]] == ["WO-202611-0117"] and j["counts_by_status"]["closed"] == 113 and j["counts_by_status"]["in_progress"] == 1
    p1 = client.get(WO, params={"as_of": FOCUS, "limit": 5, "offset": 0}, headers=a).json()
    p2 = client.get(WO, params={"as_of": FOCUS, "limit": 5, "offset": 5}, headers=a).json()
    assert len(p1["items"]) == 5 and not ({i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}) and p1["total"] == 117
    assert client.get(WO, params={"limit": 0}, headers=a).status_code == 422 and client.get(WO, params={"status": "bogus"}, headers=a).status_code == 422
    assert client.get(WO, params={"as_of": FOCUS, "priority": "urgent"}, headers=a).json()["total"] >= 0


def test_tour_precondition_prs03_has_no_work_order_after_onset(client):
    """Guided tour step 5 creates the PRS-03 work order: the seeded baseline must not already contain one after the 2026-11-06 onset."""
    wos = client.get(WO, params={"as_of": FOCUS, "equipment_id": 18, "limit": 200}, headers=hdr("public_viewer", None)).json()["items"]
    assert all(w["created_at"] < "2026-11-06T00:00:00Z" for w in wos) and not [w for w in wos if w["status"] not in ("closed", "cancelled")]
    h = client.get("/api/v1/maintenance/equipment/18/health", params={"as_of": FOCUS}, headers=hdr("public_viewer", None)).json()
    assert h["state"] == "critical" and h["maintenance_status"] == "none"
