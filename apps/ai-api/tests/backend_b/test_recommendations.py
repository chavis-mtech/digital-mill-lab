"""AI-C04: advisory recommendations from evidence rules; human decision, session scope, audit."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditLog, RecommendationDecision
from app.services.maintenance_reco import REC_ID_BASE, rec_id_for

from .conftest import EARLY, FOCUS, err, hdr

REC_BEARING = rec_id_for(18, "inspect_bearing")
REC_BEFORE_USE = rec_id_for(18, "inspect_before_use")
URL = "/api/v1/maintenance/recommendations"


def _recs(client, headers, **params):
    r = client.get(URL, params={"as_of": FOCUS, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_prs03_recommendations_have_evidence_assumptions_and_advisory_notice(client):
    items = {i["rec_type"]: i for i in _recs(client, hdr("public_viewer", None), equipment_id=18)}
    assert {"inspect_before_use", "inspect_bearing"} <= set(items)
    for it in items.values():
        assert it["advisory"] is True and it["status"] == "proposed" and it["id"] >= REC_ID_BASE
        assert "qualified engineer" in it["advisory_notice"].lower() and "machine" in it["advisory_notice"].lower()
        assert it["assumptions"] and it["evidence"] and it["model_version"].startswith("rec-rules")
        assert all(e["observed"] is not None and e["normal_range"] and e["entity"]["code"] == "PRS-03" for e in it["evidence"])
    b = items["inspect_bearing"]
    assert set(b["corroborating_sensors"]) >= {"PRS-03-VIB-DE", "PRS-03-TMP-BRG"} and b["priority"] == "critical"
    assert "not a proven cause" in b["rationale"].lower() or "possible" in b["rationale"].lower()
    assert items["inspect_before_use"]["title"].endswith("before continued use")


def test_no_recommendation_for_healthy_press_on_baseline_day_and_none_before_evidence(client):
    assert [i for i in _recs(client, hdr("public_viewer", None), equipment_id=18, as_of="2026-11-05T08:00:00Z")] == []
    early = _recs(client, hdr("public_viewer", None), equipment_id=18, as_of=EARLY)
    assert all(i["priority"] != "critical" for i in early)


def test_decision_requires_role_session_and_is_human(client):
    body = {"decision": "approved"}
    assert client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": FOCUS}, json=body, headers=hdr("public_viewer")).status_code == 403
    assert client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": FOCUS}, json=body, headers=hdr("production_engineer")).status_code == 403
    r = client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": FOCUS}, json=body, headers=hdr("maintenance_engineer", None))
    assert r.status_code == 428 and err(r) == "session_required"
    assert client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": FOCUS}, json={"decision": "execute"}, headers=hdr("maintenance_engineer")).status_code == 422


def test_approve_with_work_order_is_atomic_audited_and_session_scoped(client, db, fm):
    other = hdr("maintenance_engineer")
    r = client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": FOCUS}, json={"decision": "approved", "create_work_order": True, "note": "ok"}, headers=fm)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "approved" and j["decided_by_role"] == "factory_manager" and j["work_order_id"] and j["decision_note"] == "ok" and j["advisory"] is True
    wo = client.get(f"/api/v1/work-orders/{j['work_order_id']}", params={"as_of": FOCUS}, headers=fm).json()
    assert wo["source_type"] == "recommendation" and wo["recommendation_id"] == REC_BEARING and wo["status"] == "open" and wo["equipment"]["code"] == "PRS-03"
    sid = fm["X-Demo-Session"]
    actions = [a.action for a in db.execute(select(AuditLog).where(AuditLog.session_id == sid).order_by(AuditLog.id)).scalars()]
    assert actions == ["work_order.create", "recommendation.decision"]
    # same session: already decided; other visitor still sees it as proposed
    assert err(client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": FOCUS}, json={"decision": "rejected"}, headers=fm)) == "already_decided"
    mine = {i["rec_type"]: i for i in _recs(client, fm, equipment_id=18)}
    assert mine["inspect_bearing"]["status"] == "approved" and mine["inspect_bearing"]["work_order_id"] == j["work_order_id"]
    theirs = {i["rec_type"]: i for i in _recs(client, other, equipment_id=18)}
    assert theirs["inspect_bearing"]["status"] == "proposed" and theirs["inspect_bearing"]["work_order_id"] is None
    assert [d.session_id for d in db.execute(select(RecommendationDecision).where(RecommendationDecision.recommendation_id == REC_BEARING)).scalars()] == [sid]
    assert [i["rec_type"] for i in _recs(client, fm, status="approved")] == ["inspect_bearing"]


def test_reject_creates_no_work_order_and_work_order_needs_approval(client, me):
    r = client.post(f"{URL}/{REC_BEFORE_USE}/decision", params={"as_of": FOCUS}, json={"decision": "rejected", "create_work_order": True}, headers=me)
    assert r.status_code == 422 and err(r) == "work_order_needs_approval"
    r = client.post(f"{URL}/{REC_BEFORE_USE}/decision", params={"as_of": FOCUS}, json={"decision": "rejected", "note": "defer"}, headers=me)
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["work_order_id"] is None
    wos = client.get("/api/v1/work-orders", params={"as_of": FOCUS, "mine_only": True}, headers=me).json()
    assert wos["total"] == 0


def test_recommendation_not_generated_at_the_clock_is_404(client, me):
    r = client.post(f"{URL}/{REC_BEARING}/decision", params={"as_of": "2026-11-05T08:00:00Z"}, json={"decision": "approved"}, headers=me)
    assert r.status_code == 404 and err(r) == "recommendation_not_active"
    assert client.post(f"{URL}/5/decision", params={"as_of": FOCUS}, json={"decision": "approved"}, headers=me).status_code == 404


def test_session_reset_removes_decision(client, db):
    h = hdr("maintenance_engineer")
    client.post(f"{URL}/{REC_BEFORE_USE}/decision", params={"as_of": FOCUS}, json={"decision": "rejected"}, headers=h)
    assert client.post("/api/v1/demo/session/reset", headers=h).json()["deleted"]["recommendation_decisions"] == 1
    assert {i["rec_type"]: i["status"] for i in _recs(client, h, equipment_id=18)}["inspect_before_use"] == "proposed"
