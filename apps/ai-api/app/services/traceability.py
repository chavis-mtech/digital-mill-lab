"""FFB supplier & traceability (SPEC 4.H, DML-082..084). Owner: backend-b.

Chain: Supplier -> Delivery -> FFB batch -> Processing batch -> CPO output lot, via `ffb_deliveries`, `ffb_batches`,
`batch_inputs` (FFB batch -> processing batch, mass + share) and `lot_compositions` (processing batch -> lot, tonnes + share).

TRACKING METHOD = MASS BALANCE (ADR-017), not lot-based segregation. Palm mills mix FFB from many suppliers in the
sterilizer cages and the oil stream is continuous, so oil cannot be physically segregated by supplier. Attribution is by mass
share: a processing batch's FFB input is shared among the FFB batches that fed it (mass_share), and a CPO lot is shared among the
processing batches that filled it (cpo_t / lot quantity). A supplier's share of a lot is
    share_s = sum over batches b of ( cpo_t_b / sum cpo_t ) x ( FFB mass of supplier s in b / FFB mass of b )
and always sums to 1 over suppliers. It is a bookkeeping allocation, NOT a chain of custody: when several suppliers mix, every
lot contains all of them in proportion and no drop of oil can be claimed to come from one supplier. No certification (RSPO or other)
is claimed - the sustainability fields are a data-model sketch.

The demo clock applies: deliveries/batches after `as_of` are never read; a lot that is still filling at `as_of` is traced over
the batches completed by then (its quantity and shares are those of the completed part) and its final FFA is not shown.
"""

from __future__ import annotations

import html
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, bad_request, not_found
from app.models import (
    BatchInput,
    CpoOutputLot,
    FfbBatch,
    FfbDelivery,
    LotComposition,
    Plantation,
    ProductionBatch,
    QualityMeasurement,
    Supplier,
    WeighbridgeTicket,
)
from app.schemas.common import Disclaimer, Period
from app.schemas.roi import PrintableDocument
from app.schemas.traceability import (
    DeliveryListResponse,
    DeliveryOut,
    LotListResponse,
    LotOut,
    SupplierShare,
    TraceEdge,
    TraceGraphResponse,
    TraceNode,
    TraceReportResponse,
)
from app.services.demo_context import DemoContext

METHOD_EXPLANATION = (
    "Tracking method: MASS BALANCE. FFB from many suppliers is mixed in the sterilizer cages and the oil stream is continuous, so oil "
    "cannot be physically segregated by supplier. Each processing batch records which FFB batches fed it (mass share) and each CPO lot "
    "records which processing batches filled it (share of tonnes). A supplier's share of a lot is the sum, over the lot's batches, of "
    "(batch share of the lot) x (supplier's share of the batch's FFB). Shares are a bookkeeping allocation, not a physical chain of "
    "custody: when several suppliers mix, every lot contains all of them in proportion. This is not a certification (no RSPO or other claim)."
)
DISCLAIMERS = [
    Disclaimer(key="mass_balance", text_en=METHOD_EXPLANATION, text_th="วิธีติดตามแบบสมดุลมวล (mass balance): การผสมวัตถุดิบหลายผู้ส่งทำให้แยกน้ำมันทางกายภาพไม่ได้ ส่วนแบ่งเป็นการจัดสรรทางบัญชี ไม่ใช่ห่วงโซ่การครอบครองจริง และไม่ใช่การรับรอง"),
    Disclaimer(key="no_certification", text_en="Sustainability fields are an RSPO-style data-model sketch. No certification, audit result or sustainability claim is made.", text_th="ฟิลด์ด้านความยั่งยืนเป็นเพียงโครงข้อมูลตัวอย่างแนว RSPO ไม่มีการอ้างการรับรองหรือผลการตรวจประเมินใด ๆ"),
    Disclaimer(key="synthetic_data", text_en="All suppliers, plantations, deliveries and lots are synthetic demonstration data (fictional).", text_th="ผู้ส่ง สวน การส่งมอบ และล็อตทั้งหมดเป็นข้อมูลสังเคราะห์ (สมมติ)"),
]


def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _days(period: Period) -> int:
    if period == Period.today:
        return 1
    if period == Period.last_7d:
        return 7
    if period == Period.last_30d:
        return 30
    bad_request("unsupported_period", "period=custom is not supported here; use today, 7d or 30d")


# ------------------------------------------------------------------ lots
@dataclass
class LotRow:
    comp_cpo_t: float
    batch_id: int
    batch_code: str
    batch_end: datetime
    batch_cpo_t: float
    batch_ffb_t: float
    mass_kg: float
    mass_share: float
    method: str
    ffb_batch_id: int
    ffb_code: str
    ffb_mass_kg: int
    delivery_id: int
    delivery_code: str
    supplier_id: int
    plantation_id: int | None
    grade: str
    ripe_pct: float | None
    unripe_pct: float | None
    harvest_to_mill_h: float | None
    net_kg: int


def _lot_status(lot: CpoOutputLot, as_of: datetime) -> str:
    if lot.fill_end_ts is None or _utc(lot.fill_end_ts) > as_of:
        return "filling"
    if lot.dispatched_at is not None and _utc(lot.dispatched_at) <= as_of:
        return "dispatched"
    return "in_storage"


def get_lot(db: Session, ctx: DemoContext, lot_id: int) -> CpoOutputLot:
    lot = db.get(CpoOutputLot, lot_id)
    if lot is None or _utc(lot.fill_start_ts) > ctx.as_of:
        not_found("cpo_lot", lot_id)
    return lot


def lot_rows(db: Session, ctx: DemoContext, lot_id: int) -> list[LotRow]:
    q = (
        select(
            LotComposition.cpo_t, ProductionBatch.id, ProductionBatch.code, ProductionBatch.end_ts, ProductionBatch.cpo_t, ProductionBatch.ffb_input_t,
            BatchInput.mass_kg, BatchInput.mass_share, BatchInput.trace_method, FfbBatch.id, FfbBatch.code, FfbBatch.mass_kg, FfbDelivery.id, FfbDelivery.code,
            FfbDelivery.supplier_id, FfbDelivery.plantation_id, FfbDelivery.grade, FfbDelivery.ripe_pct, FfbDelivery.unripe_pct, FfbDelivery.harvest_to_mill_h, FfbDelivery.net_kg,
        )
        .select_from(LotComposition)
        .join(ProductionBatch, ProductionBatch.id == LotComposition.production_batch_id)
        .join(BatchInput, BatchInput.production_batch_id == ProductionBatch.id)
        .join(FfbBatch, FfbBatch.id == BatchInput.ffb_batch_id)
        .join(FfbDelivery, FfbDelivery.id == FfbBatch.delivery_id)
        .where(LotComposition.cpo_lot_id == lot_id, ProductionBatch.end_ts <= ctx.as_of, FfbBatch.received_ts <= ctx.as_of)
        .order_by(ProductionBatch.start_ts, FfbBatch.id)
    )
    return [LotRow(*r[:3], _utc(r[3]), *r[4:]) for r in db.execute(q).all()]


def lot_quantity(rows: list[LotRow]) -> float:
    seen: dict[int, float] = {}
    for r in rows:
        seen[r.batch_id] = r.comp_cpo_t
    return sum(seen.values())


def attribution(rows: list[LotRow]) -> dict[int, dict]:
    """supplier_id -> {share (0-1), ffb_kg, cpo_t}. Shares sum to 1 over suppliers (mass balance)."""
    qty = lot_quantity(rows)
    per_batch_total: dict[int, float] = defaultdict(float)
    per_batch_sup: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    comp: dict[int, tuple[float, float]] = {}
    for r in rows:
        per_batch_total[r.batch_id] += r.mass_share
        a = per_batch_sup[(r.batch_id, r.supplier_id)]
        a[0] += r.mass_share
        a[1] += r.mass_kg
        comp[r.batch_id] = (r.comp_cpo_t, r.batch_cpo_t)
    out: dict[int, dict] = {}
    for (b, s), (share_sum, mass) in per_batch_sup.items():
        cpo_b, batch_cpo = comp[b]
        lot_share_b = cpo_b / qty if qty > 0 else 0.0
        frac = share_sum / per_batch_total[b] if per_batch_total[b] > 0 else 0.0
        o = out.setdefault(s, {"share": 0.0, "ffb_kg": 0.0, "cpo_t": 0.0})
        o["share"] += lot_share_b * frac
        o["ffb_kg"] += mass * (cpo_b / batch_cpo if batch_cpo > 0 else 1.0)
    for o in out.values():
        o["cpo_t"] = o["share"] * qty
    return out


def _lot_out(lot: CpoOutputLot, ctx: DemoContext, qty: float | None, suppliers: int | None) -> LotOut:
    closed = lot.fill_end_ts is not None and _utc(lot.fill_end_ts) <= ctx.as_of
    return LotOut(
        id=lot.id, code=lot.code, tank_code=lot.tank_code, fill_start_ts=_utc(lot.fill_start_ts), fill_end_ts=_utc(lot.fill_end_ts) if closed else None,
        quantity_t=round(qty if qty is not None else lot.quantity_t, 3), ffa_pct=lot.ffa_pct if closed else None, status=_lot_status(lot, ctx.as_of), supplier_count=suppliers,
    )


def list_lots(db: Session, ctx: DemoContext, period: Period, limit: int, offset: int) -> LotListResponse:
    start, end = ctx.period_bounds(_days(period))
    base = select(CpoOutputLot).where(CpoOutputLot.fill_start_ts >= start, CpoOutputLot.fill_start_ts <= end)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    lots = list(db.execute(base.order_by(CpoOutputLot.fill_start_ts.desc(), CpoOutputLot.id.desc()).limit(limit).offset(offset)).scalars())
    ids = [lot.id for lot in lots]
    qty: dict[int, float] = {}
    sup: dict[int, int] = {}
    if ids:
        for lid, q in db.execute(
            select(LotComposition.cpo_lot_id, func.sum(LotComposition.cpo_t)).join(ProductionBatch, ProductionBatch.id == LotComposition.production_batch_id)
            .where(LotComposition.cpo_lot_id.in_(ids), ProductionBatch.end_ts <= ctx.as_of).group_by(LotComposition.cpo_lot_id)
        ):
            qty[lid] = float(q)
        for lid, n in db.execute(
            select(LotComposition.cpo_lot_id, func.count(func.distinct(FfbDelivery.supplier_id)))
            .select_from(LotComposition)
            .join(ProductionBatch, ProductionBatch.id == LotComposition.production_batch_id)
            .join(BatchInput, BatchInput.production_batch_id == ProductionBatch.id)
            .join(FfbBatch, FfbBatch.id == BatchInput.ffb_batch_id)
            .join(FfbDelivery, FfbDelivery.id == FfbBatch.delivery_id)
            .where(LotComposition.cpo_lot_id.in_(ids), ProductionBatch.end_ts <= ctx.as_of)
            .group_by(LotComposition.cpo_lot_id)
        ):
            sup[lid] = int(n)
    return LotListResponse(items=[_lot_out(lot, ctx, qty.get(lot.id, 0.0), sup.get(lot.id, 0)) for lot in lots], total=total)


# ------------------------------------------------------------------ deliveries
def list_deliveries(db: Session, ctx: DemoContext, supplier_id: int | None, period: Period, limit: int, offset: int) -> DeliveryListResponse:
    start, end = ctx.period_bounds(_days(period))
    cond = [FfbDelivery.received_ts >= start, FfbDelivery.received_ts <= end]
    if supplier_id is not None:
        cond.append(FfbDelivery.supplier_id == supplier_id)
    total = db.execute(select(func.count()).select_from(FfbDelivery).where(*cond)).scalar_one()
    rows = db.execute(
        select(FfbDelivery, Supplier.code, Plantation.code, WeighbridgeTicket.ticket_no)
        .join(Supplier, Supplier.id == FfbDelivery.supplier_id)
        .outerjoin(Plantation, Plantation.id == FfbDelivery.plantation_id)
        .outerjoin(WeighbridgeTicket, WeighbridgeTicket.id == FfbDelivery.ticket_id)
        .where(*cond).order_by(FfbDelivery.received_ts.desc(), FfbDelivery.id.desc()).limit(limit).offset(offset)
    ).all()
    return DeliveryListResponse(
        items=[
            DeliveryOut(id=d.id, code=d.code, supplier_code=sc, plantation_code=pc, received_ts=_utc(d.received_ts), net_kg=d.net_kg, accepted_kg=d.accepted_kg, grade=d.grade, ripe_pct=d.ripe_pct, ticket_no=tn)
            for d, sc, pc, tn in rows
        ],
        total=total,
    )


# ------------------------------------------------------------------ graphs
class _Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, TraceNode] = {}
        self.edges: dict[tuple[str, str], TraceEdge] = {}

    def node(self, nid: str, type_: str, label: str, ts=None, quantity=None, unit=None, **attrs) -> None:
        if nid not in self.nodes:
            self.nodes[nid] = TraceNode(id=nid, type=type_, label=label, ts=_utc(ts) if ts else None, quantity=None if quantity is None else round(quantity, 3), unit=unit, attributes=attrs)

    def edge(self, src: str, dst: str, mass=None, unit=None, share=None, method="mass_balance") -> None:
        key = (src, dst)
        if key not in self.edges:
            self.edges[key] = TraceEdge(source=src, target=dst, mass=None if mass is None else round(mass, 3), unit=unit, share=None if share is None else round(share, 6), method=method)

    def response(self, direction: str, root: str, method: str, truncated: bool, note: str | None = None) -> TraceGraphResponse:
        expl = METHOD_EXPLANATION + (f" Note: {note}" if note else "")
        return TraceGraphResponse(direction=direction, root=root, nodes=list(self.nodes.values()), edges=list(self.edges.values()), method=method, method_explanation=expl, truncated=truncated)


def _method(methods: list[str]) -> str:
    return "lot_based" if methods and all(m == "lot_based" for m in methods) else "mass_balance"


def trace_backward(db: Session, ctx: DemoContext, lot_id: int | None, production_batch_id: int | None, max_nodes: int) -> TraceGraphResponse:
    if (lot_id is None) == (production_batch_id is None):
        raise ApiError(422, "trace_root_required", "Provide exactly one of lot_id or production_batch_id.", {"fields": ["lot_id", "production_batch_id"]})
    g = _Graph()
    note = None
    if lot_id is not None:
        lot = get_lot(db, ctx, lot_id)
        rows = lot_rows(db, ctx, lot_id)
        root = f"cpo_lot:{lot.id}"
        qty = lot_quantity(rows)
        g.node(root, "cpo_lot", lot.code, lot.fill_start_ts, qty, "t", status=_lot_status(lot, ctx.as_of), tank=lot.tank_code)
        batches = {r.batch_id: r for r in rows}
        for b in batches.values():
            g.node(f"production_batch:{b.batch_id}", "production_batch", b.batch_code, b.batch_end, b.comp_cpo_t, "t CPO")
            g.edge(f"production_batch:{b.batch_id}", root, b.comp_cpo_t, "t CPO", b.comp_cpo_t / qty if qty else None)
    else:
        pb = db.get(ProductionBatch, production_batch_id)
        if pb is None or _utc(pb.end_ts) > ctx.as_of:
            not_found("production_batch", production_batch_id)
        raw = db.execute(
            select(BatchInput.mass_kg, BatchInput.mass_share, BatchInput.trace_method, FfbBatch.id, FfbBatch.code, FfbBatch.mass_kg, FfbDelivery.id, FfbDelivery.code, FfbDelivery.supplier_id, FfbDelivery.plantation_id, FfbDelivery.grade, FfbDelivery.ripe_pct, FfbDelivery.unripe_pct, FfbDelivery.harvest_to_mill_h, FfbDelivery.net_kg)
            .select_from(BatchInput).join(FfbBatch, FfbBatch.id == BatchInput.ffb_batch_id).join(FfbDelivery, FfbDelivery.id == FfbBatch.delivery_id)
            .where(BatchInput.production_batch_id == pb.id, FfbBatch.received_ts <= ctx.as_of)
        ).all()
        rows = [LotRow(pb.cpo_t, pb.id, pb.code, _utc(pb.end_ts), pb.cpo_t, pb.ffb_input_t, *r[:3], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14]) for r in raw]
        root = f"production_batch:{pb.id}"
        g.node(root, "production_batch", pb.code, pb.end_ts, pb.cpo_t, "t CPO", ffb_input_t=pb.ffb_input_t, oer_pct=pb.oer_pct)
        batches = {pb.id: rows[0]} if rows else {}
    sup_ids = {r.supplier_id for r in rows}
    suppliers = {s.id: s for s in db.execute(select(Supplier).where(Supplier.id.in_(sup_ids))).scalars()} if sup_ids else {}
    attr = attribution(rows) if lot_id is not None else {}
    detail_nodes = len(g.nodes) + len({r.ffb_batch_id for r in rows}) + len({r.delivery_id for r in rows}) + len(sup_ids) + len({r.plantation_id for r in rows if r.plantation_id})
    truncated = detail_nodes > max_nodes
    for sid in sup_ids:
        s = suppliers[sid]
        a = attr.get(sid, {})
        g.node(f"supplier:{sid}", "supplier", f"{s.code} - {s.name}", supplier_type=s.supplier_type, province=s.province, sustainability_status=s.sustainability_status,
               **({"share_of_lot": round(a["share"], 6), "attributed_cpo_t": round(a["cpo_t"], 3), "ffb_kg": round(a["ffb_kg"], 1)} if a else {}))
    if not truncated:
        plant_ids = {r.plantation_id for r in rows if r.plantation_id}
        plants = {p.id: p for p in db.execute(select(Plantation).where(Plantation.id.in_(plant_ids))).scalars()} if plant_ids else {}
        for r in rows:
            fb, dl, sp = f"ffb_batch:{r.ffb_batch_id}", f"delivery:{r.delivery_id}", f"supplier:{r.supplier_id}"
            g.node(fb, "ffb_batch", r.ffb_code, quantity=r.ffb_mass_kg, unit="kg", grade=r.grade)
            g.node(dl, "delivery", r.delivery_code, quantity=r.net_kg, unit="kg", grade=r.grade, ripe_pct=r.ripe_pct, unripe_pct=r.unripe_pct, harvest_to_mill_h=r.harvest_to_mill_h)
            g.edge(fb, f"production_batch:{r.batch_id}", r.mass_kg, "kg FFB", r.mass_share, r.method)
            g.edge(dl, fb, r.ffb_mass_kg, "kg FFB", 1.0, r.method)
            if r.plantation_id and r.plantation_id in plants:
                pn = f"plantation:{r.plantation_id}"
                g.node(pn, "plantation", plants[r.plantation_id].code, area_ha=plants[r.plantation_id].area_ha)
                g.edge(sp, pn)
                g.edge(pn, dl, r.net_kg, "kg FFB", None, r.method)
            else:
                g.edge(sp, dl, r.net_kg, "kg FFB", None, r.method)
    else:
        note = f"the full chain has {detail_nodes} nodes (> max_nodes={max_nodes}); FFB-batch, delivery and plantation layers are collapsed into supplier -> processing-batch edges (mass and share are preserved). Raise max_nodes or use the lot report for per-supplier totals."
        agg: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0, 0])
        for r in rows:
            a = agg[(r.supplier_id, r.batch_id)]
            a[0] += r.mass_kg
            a[1] += r.mass_share
            a[2] += 1
        for (sid, bid), (mass, share, n) in agg.items():
            g.edge(f"supplier:{sid}", f"production_batch:{bid}", mass, "kg FFB", share, _method([r.method for r in rows]))
            g.nodes[f"supplier:{sid}"].attributes.setdefault("collapsed_ffb_batches", 0)
            g.nodes[f"supplier:{sid}"].attributes["collapsed_ffb_batches"] += n
    return g.response("backward", root, _method([r.method for r in rows]), truncated, note)


def trace_forward(db: Session, ctx: DemoContext, supplier_id: int | None, delivery_id: int | None, max_nodes: int) -> TraceGraphResponse:
    if (supplier_id is None) == (delivery_id is None):
        raise ApiError(422, "trace_root_required", "Provide exactly one of supplier_id or delivery_id.", {"fields": ["supplier_id", "delivery_id"]})
    g = _Graph()
    if delivery_id is not None:
        d0 = db.get(FfbDelivery, delivery_id)
        if d0 is None or _utc(d0.received_ts) > ctx.as_of:
            not_found("delivery", delivery_id)
        supplier_id = d0.supplier_id
    sup = db.get(Supplier, supplier_id)
    if sup is None:
        not_found("supplier", supplier_id)
    q = select(FfbDelivery, Plantation.code, Plantation.area_ha, WeighbridgeTicket.ticket_no).outerjoin(Plantation, Plantation.id == FfbDelivery.plantation_id).outerjoin(WeighbridgeTicket, WeighbridgeTicket.id == FfbDelivery.ticket_id)
    if delivery_id is not None:
        q = q.where(FfbDelivery.id == delivery_id)
        total_available = 1
    else:
        q = q.where(FfbDelivery.supplier_id == supplier_id, FfbDelivery.received_ts <= ctx.as_of)
        total_available = db.execute(select(func.count()).select_from(FfbDelivery).where(FfbDelivery.supplier_id == supplier_id, FfbDelivery.received_ts <= ctx.as_of)).scalar_one()
    deliveries = db.execute(q.order_by(FfbDelivery.received_ts.desc(), FfbDelivery.id.desc()).limit(400)).all()
    dids = [d.id for d, *_ in deliveries]
    fbs = defaultdict(list)
    for fb in db.execute(select(FfbBatch).where(FfbBatch.delivery_id.in_(dids), FfbBatch.received_ts <= ctx.as_of)).scalars() if dids else []:
        fbs[fb.delivery_id].append(fb)
    fb_ids = [fb.id for lst in fbs.values() for fb in lst]
    inputs = defaultdict(list)
    for bi, pb in db.execute(select(BatchInput, ProductionBatch).join(ProductionBatch, ProductionBatch.id == BatchInput.production_batch_id).where(BatchInput.ffb_batch_id.in_(fb_ids), ProductionBatch.end_ts <= ctx.as_of)).all() if fb_ids else []:
        inputs[bi.ffb_batch_id].append((bi, pb))
    pb_ids = {pb.id for lst in inputs.values() for _, pb in lst}
    comps = defaultdict(list)
    if pb_ids:
        for lc, lot in db.execute(select(LotComposition, CpoOutputLot).join(CpoOutputLot, CpoOutputLot.id == LotComposition.cpo_lot_id).where(LotComposition.production_batch_id.in_(pb_ids), CpoOutputLot.fill_start_ts <= ctx.as_of)).all():
            comps[lc.production_batch_id].append((lc, lot))
    root = f"supplier:{sup.id}" if delivery_id is None else f"delivery:{delivery_id}"
    g.node(f"supplier:{sup.id}", "supplier", f"{sup.code} - {sup.name}", supplier_type=sup.supplier_type, province=sup.province, sustainability_status=sup.sustainability_status, deliveries_before_clock=total_available)
    truncated = False
    methods: list[str] = []
    for d, plant_code, area, ticket_no in deliveries:
        # nodes this delivery's chain would add
        add: set[str] = {f"delivery:{d.id}"}
        if d.plantation_id:
            add.add(f"plantation:{d.plantation_id}")
        for fb in fbs.get(d.id, []):
            add.add(f"ffb_batch:{fb.id}")
            for _bi, pb in inputs.get(fb.id, []):
                add.add(f"production_batch:{pb.id}")
                for _lc, lot in comps.get(pb.id, []):
                    add.add(f"cpo_lot:{lot.id}")
        new = [n for n in add if n not in g.nodes]
        if len(g.nodes) + len(new) > max_nodes:
            truncated = True
            break
        dn = f"delivery:{d.id}"
        g.node(dn, "delivery", d.code, d.received_ts, d.net_kg, "kg", grade=d.grade, ripe_pct=d.ripe_pct, ticket_no=ticket_no, accepted_kg=d.accepted_kg)
        if d.plantation_id:
            pn = f"plantation:{d.plantation_id}"
            g.node(pn, "plantation", plant_code or str(d.plantation_id), area_ha=area)
            g.edge(f"supplier:{sup.id}", pn)
            g.edge(pn, dn, d.net_kg, "kg FFB")
        else:
            g.edge(f"supplier:{sup.id}", dn, d.net_kg, "kg FFB")
        for fb in fbs.get(d.id, []):
            fn = f"ffb_batch:{fb.id}"
            g.node(fn, "ffb_batch", fb.code, fb.received_ts, fb.mass_kg, "kg", grade=fb.grade)
            g.edge(dn, fn, fb.mass_kg, "kg FFB", 1.0)
            for bi, pb in inputs.get(fb.id, []):
                pn2 = f"production_batch:{pb.id}"
                methods.append(bi.trace_method)
                g.node(pn2, "production_batch", pb.code, pb.end_ts, pb.cpo_t, "t CPO", ffb_input_t=pb.ffb_input_t, oer_pct=pb.oer_pct)
                g.edge(fn, pn2, bi.mass_kg, "kg FFB", bi.mass_share, bi.trace_method)
                for lc, lot in comps.get(pb.id, []):
                    ln = f"cpo_lot:{lot.id}"
                    g.node(ln, "cpo_lot", lot.code, lot.fill_start_ts, None, "t", status=_lot_status(lot, ctx.as_of), tank=lot.tank_code)
                    g.edge(pn2, ln, lc.cpo_t, "t CPO", None, lc.trace_method)
    if len(deliveries) < total_available:
        truncated = True
    note = "newest deliveries first; the graph stops at max_nodes (or the newest 400 deliveries). Shares on batch edges are the FFB batch's share of the processing batch; they are bookkeeping allocations (mass balance)." if truncated else None
    return g.response("forward", root, _method(methods), truncated, note)


# ------------------------------------------------------------------ report
def lot_report(db: Session, ctx: DemoContext, lot_id: int) -> TraceReportResponse:
    lot = get_lot(db, ctx, lot_id)
    rows = lot_rows(db, ctx, lot_id)
    attr = attribution(rows)
    qty = lot_quantity(rows)
    sups = {s.id: s for s in db.execute(select(Supplier).where(Supplier.id.in_(list(attr)))).scalars()} if attr else {}
    shares = sorted(
        (SupplierShare(supplier_code=sups[s].code, supplier_name=sups[s].name, ffb_kg=round(a["ffb_kg"], 1), share_pct=round(100 * a["share"], 4), attributed_cpo_t=round(a["cpo_t"], 4)) for s, a in attr.items()),
        key=lambda x: -x.share_pct,
    )
    batches = list(dict.fromkeys(r.batch_code for r in rows))
    # quality summary: lab results taken by the demo clock + FFB intake quality weighted by attributable mass
    q = db.execute(
        select(QualityMeasurement.parameter, QualityMeasurement.value, QualityMeasurement.unit, QualityMeasurement.sample_ts)
        .where(QualityMeasurement.cpo_lot_id == lot_id, QualityMeasurement.sample_ts <= ctx.as_of).order_by(QualityMeasurement.sample_ts)
    ).all()
    lab: dict[str, dict] = {}
    for p, v, u, ts in q:
        lab[p] = {"latest": round(v, 3), "unit": u, "sample_ts": _utc(ts).isoformat(), "n_samples": lab.get(p, {}).get("n_samples", 0) + 1}
    w = sum(r.mass_kg for r in rows) or 1.0
    wavg = lambda attr_name: (sum((getattr(r, attr_name) or 0) * r.mass_kg for r in rows if getattr(r, attr_name) is not None) / w) if rows else None  # noqa: E731
    grade_mass: dict[str, float] = defaultdict(float)
    for r in rows:
        grade_mass[r.grade] += r.mass_kg
    summary = {
        "lab_results_by_clock": lab, "final_lot_ffa_pct": lot.ffa_pct if lot.fill_end_ts and _utc(lot.fill_end_ts) <= ctx.as_of else None,
        "intake_ripe_pct_weighted": None if not rows else round(wavg("ripe_pct"), 2), "intake_unripe_pct_weighted": None if not rows else round(wavg("unripe_pct"), 2),
        "harvest_to_mill_h_weighted": None if not rows else round(wavg("harvest_to_mill_h"), 1), "intake_grade_share_pct": {g: round(100 * m / w, 1) for g, m in sorted(grade_mass.items())},
        "status": _lot_status(lot, ctx.as_of), "note": "A lot that is still filling is reported over the batches completed by the demo clock; its final lab values are not shown." if _lot_status(lot, ctx.as_of) == "filling" else None,
    }
    by_type: dict[str, float] = defaultdict(float)
    by_status: dict[str, float] = defaultdict(float)
    for s, a in attr.items():
        by_type[sups[s].supplier_type] += a["share"] * 100
        by_status[sups[s].sustainability_status] += a["share"] * 100
    plant_ids = {r.plantation_id for r in rows if r.plantation_id}
    plants = list(db.execute(select(Plantation).where(Plantation.id.in_(plant_ids))).scalars()) if plant_ids else []
    sust = {
        "model": "RSPO-style data-model sketch - NOT a certification, audit or sustainability claim",
        "certification_claim": "none", "supply_chain_model": "mass_balance (see method)", "suppliers_by_type_share_pct": {k: round(v, 2) for k, v in sorted(by_type.items())},
        "supplier_sustainability_status_share_pct": {k: round(v, 2) for k, v in sorted(by_status.items())},
        "plantations_in_lot": {"count": len(plants), "with_area": sum(1 for p in plants if p.area_ha), "with_coordinates": sum(1 for p in plants if p.lat is not None and p.lon is not None), "total_area_ha": round(sum(p.area_ha or 0 for p in plants), 1)},
        "fields_in_data_model": ["supplier_type", "sustainability_status (not_assessed / data_collected / gap_identified / documented)", "plantation area_ha, coarse lat/lon, planting_year", "plantations.sustainability_json (audit fields, empty in the demo)"],
        "fields_a_real_audit_would_need": ["land-title / legality documents", "NDPE / deforestation-free evidence with dates", "smallholder registration and traceability to plantation polygons", "third-party audit results", "segregation / mass-balance ledger approved by a certification body"],
    }
    return TraceReportResponse(
        lot=_lot_out(lot, ctx, qty, len(attr)), method=_method([r.method for r in rows]), supplier_shares=shares, production_batches=batches, quality_summary=summary,
        sustainability_fields=sust, disclaimers=DISCLAIMERS,
    )


def lot_report_html(rep: TraceReportResponse, ctx: DemoContext) -> str:
    e = html.escape
    sh = "".join(f"<tr><td>{e(s.supplier_code)}</td><td>{e(s.supplier_name)}</td><td>{s.ffb_kg:,.0f}</td><td>{s.share_pct:.3f}</td><td>{s.attributed_cpo_t:.3f}</td></tr>" for s in rep.supplier_shares)
    q = rep.quality_summary
    qrows = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in q.items() if k != "lab_results_by_clock" and v is not None)
    lab = "".join(f"<tr><th>{e(k)}</th><td>{v['latest']} {e(v['unit'])} ({v['n_samples']} sample(s), latest {e(v['sample_ts'])})</td></tr>" for k, v in q["lab_results_by_clock"].items())
    sus = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in rep.sustainability_fields.items())
    disc = "".join(f"<p class='disc'>{e(d.text_en)}</p>" for d in rep.disclaimers)
    lot = rep.lot
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Traceability report {e(lot.code)}</title><style>
body{{font:14px/1.5 system-ui,sans-serif;margin:24px auto;max-width:960px;padding:0 16px;color:#111}}h1{{font-size:20px}}h2{{font-size:16px;margin-top:22px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}th,td{{border:1px solid #bbb;padding:4px 8px;text-align:left;vertical-align:top}}.disc{{border:2px solid #b45309;background:#fffbeb;padding:8px 10px}}
@media print{{body{{margin:0}}}}</style></head><body>
<h1>CPO lot traceability report - {e(lot.code)}</h1>
<p>Independent concept demo on synthetic data. Demo clock {e(ctx.as_of.isoformat())}. Tank {e(lot.tank_code)}, status {e(lot.status)}, quantity {lot.quantity_t:,.3f} t, suppliers {lot.supplier_count}. Method: <b>{e(rep.method)}</b>.</p>
{disc}
<h2>Supplier shares (mass-balance allocation)</h2><table><tr><th>supplier</th><th>name</th><th>FFB attributed (kg)</th><th>share %</th><th>attributed CPO (t)</th></tr>{sh}</table>
<h2>Processing batches</h2><p>{e(', '.join(rep.production_batches))}</p>
<h2>Quality</h2><table>{qrows}{lab}</table>
<h2>Sustainability data-model sketch (not a certification)</h2><table>{sus}</table>
</body></html>"""


def lot_report_document(db: Session, ctx: DemoContext, lot_id: int) -> PrintableDocument:
    rep = lot_report(db, ctx, lot_id)
    return PrintableDocument(
        report_type="traceability_lot", title=f"CPO lot traceability report - {rep.lot.code}", filename=f"traceability-{rep.lot.code}.html", html=lot_report_html(rep, ctx),
        generated_at=datetime.now(UTC), as_of=ctx.as_of, disclaimers=rep.disclaimers,
    )
