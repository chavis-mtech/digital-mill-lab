"""DML-082..084: mass-balance traceability - conservation, as_of discipline, honest method statements."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models import BatchInput, CpoOutputLot, FfbBatch, FfbDelivery, LotComposition, ProductionBatch, Supplier

from .conftest import FOCUS, err, hdr

PV = hdr("public_viewer", None)
T = "/api/v1/traceability"


def _closed_lots(client, n=6, as_of=FOCUS):
    items = client.get(f"{T}/lots", params={"as_of": as_of, "period": "30d", "limit": n + 1}, headers=PV).json()["items"]
    return [i for i in items if i["status"] != "filling"][:n]


def test_lot_list_and_status_at_the_clock(client):
    j = client.get(f"{T}/lots", params={"as_of": FOCUS, "period": "7d", "limit": 10}, headers=PV).json()
    assert j["total"] == 7 and j["items"][0]["status"] == "filling" and j["items"][0]["ffa_pct"] is None and j["items"][0]["fill_end_ts"] is None  # no final values for a lot still filling
    done = [i for i in j["items"] if i["status"] != "filling"]
    assert all(i["ffa_pct"] is not None and i["supplier_count"] > 5 and i["quantity_t"] > 50 for i in done)
    assert [i["fill_start_ts"] for i in j["items"]] == sorted((i["fill_start_ts"] for i in j["items"]), reverse=True)


@pytest.mark.parametrize("which", range(6))
def test_supplier_shares_sum_to_one_and_cpo_is_conserved(client, db, which):
    lot = _closed_lots(client)[which]
    rep = client.get(f"{T}/lots/{lot['id']}/report", params={"as_of": FOCUS}, headers=PV).json()
    assert rep["method"] == "mass_balance" and len(rep["supplier_shares"]) == lot["supplier_count"]
    assert sum(s["share_pct"] for s in rep["supplier_shares"]) == pytest.approx(100.0, abs=1e-3)  # shares of all suppliers = 1
    assert sum(s["attributed_cpo_t"] for s in rep["supplier_shares"]) == pytest.approx(lot["quantity_t"], abs=2e-3)  # CPO out = CPO attributed
    # recompute the attribution by hand straight from the tables
    comps = db.execute(select(LotComposition.production_batch_id, LotComposition.cpo_t).where(LotComposition.cpo_lot_id == lot["id"])).all()
    qty = sum(c for _, c in comps)
    by_supplier: dict[str, float] = defaultdict(float)
    sup_code = dict(db.execute(select(Supplier.id, Supplier.code)).all())
    for pb_id, cpo in comps:
        rows = db.execute(
            select(FfbDelivery.supplier_id, BatchInput.mass_share)
            .select_from(BatchInput)
            .join(FfbBatch, FfbBatch.id == BatchInput.ffb_batch_id)
            .join(FfbDelivery, FfbDelivery.id == FfbBatch.delivery_id)
            .where(BatchInput.production_batch_id == pb_id)
        ).all()
        tot = sum(s for _, s in rows)
        for sid, share in rows:
            by_supplier[sup_code[sid]] += cpo / qty * share / tot
    got = {s["supplier_code"]: s["share_pct"] / 100 for s in rep["supplier_shares"]}
    assert got == pytest.approx(dict(by_supplier), abs=1e-5)


def test_mass_in_equals_mass_out_through_the_chain(db):
    """Stored data obeys the conservation the report relies on: FFB in = batch input, CPO of batches = CPO of the lot."""
    lot = db.execute(select(CpoOutputLot).where(CpoOutputLot.status == "in_storage").order_by(CpoOutputLot.id.desc())).scalars().first()
    comps = db.execute(select(LotComposition, ProductionBatch).join(ProductionBatch, ProductionBatch.id == LotComposition.production_batch_id).where(LotComposition.cpo_lot_id == lot.id)).all()
    assert sum(lc.cpo_t for lc, _ in comps) == pytest.approx(lot.quantity_t, abs=1e-6) and sum(lc.share for lc, _ in comps) == pytest.approx(1.0, abs=1e-4)
    for _lc, pb in comps:
        ffb_kg = db.execute(select(func.sum(BatchInput.mass_kg)).where(BatchInput.production_batch_id == pb.id)).scalar_one()
        shares = db.execute(select(func.sum(BatchInput.mass_share)).where(BatchInput.production_batch_id == pb.id)).scalar_one()
        assert ffb_kg / 1000.0 == pytest.approx(pb.ffb_input_t, rel=1e-4) and shares == pytest.approx(1.0, abs=1e-4)
        assert pb.cpo_t == pytest.approx(pb.ffb_input_t * pb.oer_pct / 100, rel=1e-3)  # CPO out = FFB in x OER


def test_backward_graph_edges_conserve_shares(client):
    lot = _closed_lots(client)[0]
    g = client.get(f"{T}/backward", params={"as_of": FOCUS, "lot_id": lot["id"], "max_nodes": 1000}, headers=PV).json()
    assert g["direction"] == "backward" and g["root"] == f"cpo_lot:{lot['id']}" and g["truncated"] is False and g["method"] == "mass_balance"
    assert {"cpo_lot", "production_batch", "ffb_batch", "delivery", "supplier"} <= {n["type"] for n in g["nodes"]}
    into: dict[str, float] = defaultdict(float)
    for e in g["edges"]:
        if e["share"] is not None and e["target"].startswith(("cpo_lot", "production_batch")):
            into[e["target"]] += e["share"]
    assert into[g["root"]] == pytest.approx(1.0, abs=1e-4)  # batches' shares of the lot
    for nid, total in into.items():
        if nid.startswith("production_batch"):
            assert total == pytest.approx(1.0, abs=1e-4), nid  # FFB batches' shares of each processing batch
    sup_share = sum(n["attributes"]["share_of_lot"] for n in g["nodes"] if n["type"] == "supplier")
    assert sup_share == pytest.approx(1.0, abs=1e-4)
    assert "MASS BALANCE" in g["method_explanation"] and "not a certification" in g["method_explanation"] and "not a physical chain of custody" in g["method_explanation"]


def test_backward_graph_collapses_when_too_large_but_keeps_shares(client):
    lot = _closed_lots(client)[0]
    g = client.get(f"{T}/backward", params={"as_of": FOCUS, "lot_id": lot["id"], "max_nodes": 60}, headers=PV).json()
    assert g["truncated"] is True and len(g["nodes"]) <= 60 and "collapsed" in g["method_explanation"]
    assert {n["type"] for n in g["nodes"]} == {"cpo_lot", "production_batch", "supplier"}
    per_batch: dict[str, float] = defaultdict(float)
    for e in g["edges"]:
        if e["source"].startswith("supplier") and e["share"] is not None:
            per_batch[e["target"]] += e["share"]
    assert per_batch and all(v == pytest.approx(1.0, abs=1e-4) for v in per_batch.values())


def test_forward_from_delivery_reaches_cpo_lots_and_respects_the_clock(client, db):
    d = client.get(f"{T}/deliveries", params={"as_of": FOCUS, "period": "7d", "limit": 200}, headers=PV).json()["items"]
    old = [x for x in d if x["received_ts"] < "2026-11-19T00:00:00Z"][0]
    g = client.get(f"{T}/forward", params={"as_of": FOCUS, "delivery_id": old["id"]}, headers=PV).json()
    assert g["direction"] == "forward" and g["root"] == f"delivery:{old['id']}" and "cpo_lot" in {n["type"] for n in g["nodes"]}
    assert all(n["ts"] is None or n["ts"] <= FOCUS for n in g["nodes"])
    assert any(e["source"].startswith("ffb_batch") and e["share"] and 0 < e["share"] <= 1 for e in g["edges"])
    # a delivery that arrives after the demo clock does not exist yet
    future = db.execute(select(FfbDelivery.id).where(FfbDelivery.received_ts > datetime(2026, 11, 20, 8, 0, tzinfo=UTC)).limit(1)).scalar_one()
    assert client.get(f"{T}/forward", params={"as_of": FOCUS, "delivery_id": future}, headers=PV).status_code == 404


def test_forward_from_supplier_is_budgeted_and_flagged(client):
    g = client.get(f"{T}/forward", params={"as_of": FOCUS, "supplier_id": 2, "max_nodes": 100}, headers=PV).json()
    assert g["truncated"] is True and len(g["nodes"]) <= 100 and g["root"] == "supplier:2"
    assert all(n["ts"] is None or n["ts"] <= FOCUS for n in g["nodes"])
    node_ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in g["edges"])  # no dangling edges after truncation


def test_trace_root_validation(client):
    for params in ({}, {"lot_id": 1, "production_batch_id": 1}):
        r = client.get(f"{T}/backward", params=params, headers=PV)
        assert r.status_code == 422 and err(r) == "trace_root_required"
    for params in ({}, {"supplier_id": 1, "delivery_id": 1}):
        assert err(client.get(f"{T}/forward", params=params, headers=PV)) == "trace_root_required"
    assert client.get(f"{T}/backward", params={"lot_id": 99999}, headers=PV).status_code == 404
    assert client.get(f"{T}/lots/0/report", headers=PV).status_code == 422


def test_lot_in_the_future_is_invisible_and_a_filling_lot_is_partial(client):
    lots_now = client.get(f"{T}/lots", params={"as_of": FOCUS, "period": "7d", "limit": 1}, headers=PV).json()["items"][0]
    assert client.get(f"{T}/lots/{lots_now['id']}/report", params={"as_of": "2026-11-18T00:00:00Z"}, headers=PV).status_code == 404
    early = client.get(f"{T}/lots/{lots_now['id']}/report", params={"as_of": "2026-11-20T05:00:00Z"}, headers=PV).json()
    late = client.get(f"{T}/lots/{lots_now['id']}/report", params={"as_of": FOCUS}, headers=PV).json()
    assert early["lot"]["status"] == "filling" and 0 < early["lot"]["quantity_t"] < late["lot"]["quantity_t"]
    assert sum(s["share_pct"] for s in early["supplier_shares"]) == pytest.approx(100.0, abs=1e-3) and early["quality_summary"]["final_lot_ffa_pct"] is None
    assert "still filling" in early["quality_summary"]["note"]
    assert set(early["production_batches"]) < set(late["production_batches"])


def test_report_never_claims_certification_and_printable_version(client):
    lot = _closed_lots(client)[0]
    rep = client.get(f"{T}/lots/{lot['id']}/report", params={"as_of": FOCUS}, headers=PV).json()
    assert rep["sustainability_fields"]["certification_claim"] == "none" and "NOT a certification" in rep["sustainability_fields"]["model"]
    assert {"mass_balance", "no_certification", "synthetic_data"} <= {d["key"] for d in rep["disclaimers"]}
    assert rep["quality_summary"]["final_lot_ffa_pct"] == lot["ffa_pct"] and set(rep["quality_summary"]["lab_results_by_clock"]) >= {"ffa", "moisture", "dirt", "dobi"}
    r = client.get(f"{T}/lots/{lot['id']}/report/printable", params={"as_of": FOCUS}, headers=PV)
    doc = r.json()
    assert r.status_code == 200 and doc["media_type"] == "text/html" and "mass_balance" in doc["html"] and "NOT a certification" in doc["html"] and "<script" not in doc["html"]
    assert doc["report_type"] == "traceability_lot" and doc["filename"].startswith("traceability-CPO-")
    low = doc["html"].lower()
    assert "rspo certified" not in low and "certified by" not in low


def test_deliveries_listing(client):
    j = client.get(f"{T}/deliveries", params={"as_of": FOCUS, "supplier_id": 2, "period": "7d", "limit": 5, "offset": 0}, headers=PV).json()
    assert 0 < len(j["items"]) <= 5 and j["total"] >= len(j["items"]) and all(i["supplier_code"] == "SUP-002" and i["received_ts"] <= FOCUS for i in j["items"])
    assert j["items"][0]["ticket_no"].startswith("WB-")
    assert client.get(f"{T}/deliveries", params={"limit": 501}, headers=PV).status_code == 422
