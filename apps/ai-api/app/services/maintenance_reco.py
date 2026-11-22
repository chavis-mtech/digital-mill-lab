"""Advisory maintenance recommendations (AI-C04, DML-055). Owner: backend-b.

Rule engine over the health assessments at the demo clock: each recommendation is generated from evidence that must
corroborate (which sensors agree), carries its evidence, assumptions and an advisory notice, and requires a HUMAN
decision (approve / reject, optionally creating a work order). Nothing is executed on any machine.

Rules (rule_id -> trigger):
  R1 inspect_before_use  a sensor is Critical (latest reading >= crit) or a critical alert is unresolved   -> priority critical
  R2 inspect_bearing     vibration >= warn AND a bearing temperature above its normal range                 -> high (critical if vib critical)
  R3 alignment_check     vibration >= warn WITHOUT a bearing-temperature rise (alignment / looseness / balance) -> medium
  R4 lubrication         bearing temperature above its normal range while vibration is below warn          -> medium
  R5 sensor_check        a limit-checked sensor is flat-lined (identical samples) - verify the instrument  -> low
  R6 preventive_service  service interval exceeded (running hours or calendar days)                         -> medium
  R7 condition_check     any other sensor (pressure, flue temperature, current, process temperature) >= warn  -> medium / high
"Possible contributing factors, not a proven cause": the rules state which signals agree, never a diagnosis.

Persistence (ADR-006/014): rule-generated recommendations are recomputed at every call (stateless, deterministic) with a
stable id = 9,000,000 + equipment_id * 100 + rule number. The `ai_recommendations` catalog row for that id is created lazily
on the first human decision / work-order link (FK target) - the row holds no visitor data; the decision itself is a
session-scoped `recommendation_decisions` row and is audited.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import AiRecommendation, ProcessStage, RecommendationDecision
from app.models.enums import HealthState, RecommendationStatus, Severity, StageCode
from app.schemas.common import EntityRef, Evidence, NormalRange
from app.schemas.maintenance import RecommendationDecisionRequest, RecommendationOut
from app.schemas.workorders import WorkOrderCreateRequest
from app.services.audit import write_audit
from app.services.demo_context import DemoContext, require_session
from app.services.maintenance_health import Assessment, SensorAssessment, load_assessments
from app.services.rbac import Permission, has_permission

RULE_ENGINE_VERSION = "rec-rules@1.0"
REC_ID_BASE = 9_000_000
RULE_NO = {"inspect_before_use": 1, "inspect_bearing": 2, "alignment_check": 3, "lubrication": 4, "sensor_check": 5, "preventive_service": 6, "condition_check": 7}
RULE_ID = {k: f"R{v}" for k, v in RULE_NO.items()}
PRIORITY_ORDER = {Severity.critical: 4, Severity.high: 3, Severity.medium: 2, Severity.low: 1, Severity.info: 0}
COMMON_ASSUMPTIONS = [
    "Thresholds are the sensors' engineering limits (ISO 10816-3 style zones for vibration) applied to synthetic data.",
    "The signals listed are possible contributing factors, not a proven cause or a diagnosis.",
    "Whether to stop, inspect or continue is a decision for qualified maintenance engineers; this system never controls machines.",
]


@dataclass
class RecItem:
    id: int
    code: str
    rec_type: str
    title: str
    rationale: str
    priority: Severity
    equipment_id: int | None
    equipment_code: str | None
    stage_code: str | None
    risk_score: float | None
    evidence: list[Evidence] = field(default_factory=list)
    corroborating: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    source: str = "rule_engine"
    row_status: str = "proposed"
    anomaly_event_id: int | None = None
    row_created_at: object = None


def rec_id_for(equipment_id: int, rec_type: str) -> int:
    return REC_ID_BASE + equipment_id * 100 + RULE_NO[rec_type]


def _ev(a: Assessment, s: SensorAssessment, note: str | None = None) -> Evidence:
    ts0 = s.window[0][0] if s.window else None
    ts1 = s.latest[0] if s.latest else None
    nr = None
    if s.normal_min is not None or s.normal_max is not None:
        nr = NormalRange(low=s.normal_min, high=s.normal_max, unit=s.unit, basis="sensor engineering range (sensors.normal_min / normal_max)")
    lim = f"warn {s.warn:g}" if s.warn is not None else ""
    lim += f", crit {s.crit:g}" if s.crit is not None else ""
    parts = [f"state {s.level.value}" if s.level else "not assessed", lim.strip(", ")]
    if s.iso:
        parts.append(f"ISO 10816-3 zone {s.iso}")
    if s.trend_rising:
        parts.append(f"rising {s.trend_slope_per_day:+.3f} {s.unit}/day over 7 d")
    return Evidence(
        metric=s.code, label=s.name, observed=None if s.latest is None else round(s.latest[1], 3), expected=None, normal_range=nr, unit=s.unit,
        window_start=ts0, window_end=ts1, entity=EntityRef(type="equipment", id=a.equipment_id, code=a.code, label=a.name),
        note="; ".join(p for p in parts if p) + (f"; {note}" if note else ""),
    )


def _elevated(s: SensorAssessment) -> bool:
    if s.latest is None:
        return False
    v = s.latest[1]
    if s.low_is_bad:
        return s.normal_min is not None and v < s.normal_min
    return s.normal_max is not None and v > s.normal_max


def _at_least_warn(s: SensorAssessment) -> bool:
    return s.level in (HealthState.warning, HealthState.critical)


def generate_for(a: Assessment) -> list[RecItem]:
    out: list[RecItem] = []
    vib = [s for s in a.sensors if s.sensor_type == "vibration" and _at_least_warn(s)]
    brg = [s for s in a.sensors if s.code.endswith("TMP-BRG")]
    brg_hot = [s for s in brg if _elevated(s)]
    crit_sensors = [s for s in a.sensors if s.level == HealthState.critical]
    crit_alerts = [al for al in a.open_alerts if al.severity == "critical"]

    def add(rec_type: str, title: str, rationale: str, priority: Severity, ev_sensors: list[SensorAssessment], extra: list[str] | None = None, note: str | None = None):
        out.append(
            RecItem(
                id=rec_id_for(a.equipment_id, rec_type), code=f"REC-{a.code}-{rec_type}", rec_type=rec_type, title=title, rationale=rationale, priority=priority,
                equipment_id=a.equipment_id, equipment_code=a.code, stage_code=a.stage_code, risk_score=a.risk_score,
                evidence=[_ev(a, s, note) for s in ev_sensors], corroborating=[s.code for s in ev_sensors],
                assumptions=COMMON_ASSUMPTIONS + (extra or []),
            )
        )

    # R1 ---------------------------------------------------------------
    if crit_sensors or crit_alerts:
        parts = [f"{s.code} reads {s.latest[1]:.2f} {s.unit} (critical limit {s.crit:g}" + (f", ISO zone {s.iso}" if s.iso else "") + ")" for s in crit_sensors]
        parts += [f"unresolved critical alert {al.code} raised {al.raised_at:%Y-%m-%d %H:%M} UTC" for al in crit_alerts]
        agree = len({s.sensor_type for s in a.sensors if _at_least_warn(s)})
        add(
            "inspect_before_use", f"Inspect {a.code} before continued use",
            f"{a.name}: " + "; ".join(parts) + f". {agree} sensor type(s) at Warning or worse. A qualified engineer should inspect before the machine continues in service.",
            Severity.critical, crit_sensors or [s for s in a.sensors if _at_least_warn(s)],
            ["ISO 10816-3 zone D means damage can occur; the stop/continue decision belongs to the responsible engineer."],
        )
    # R2 / R3 ----------------------------------------------------------
    if vib and brg_hot:
        v = max(vib, key=lambda s: s.latest[1] if s.latest else 0)
        extra_cur = [s for s in a.sensors if s.sensor_type == "current" and _elevated(s)]
        crit_v = v.level == HealthState.critical
        add(
            "inspect_bearing", f"Inspect {a.code} bearing (vibration and bearing temperature rising together)",
            f"{v.code} = {v.latest[1]:.2f} {v.unit} (state {v.level.value}" + (f", ISO zone {v.iso}" if v.iso else "") + ") and "
            f"{brg_hot[0].code} = {brg_hot[0].latest[1]:.1f} {brg_hot[0].unit} above its normal range"
            + (f" and {extra_cur[0].code} above normal" if extra_cur else "")
            + ". The agreement of vibration and temperature is consistent with bearing wear or lubrication starvation (possible factors, not a proven cause).",
            Severity.critical if crit_v else Severity.high, [v, brg_hot[0], *extra_cur[:1]],
            ["Bearing wear is one hypothesis among several; inspect (vibration spectrum, lubricant condition) before replacing parts."],
        )
    elif vib:
        v = max(vib, key=lambda s: s.latest[1] if s.latest else 0)
        add(
            "alignment_check", f"Check {a.code} alignment / looseness / balance",
            f"{v.code} = {v.latest[1]:.2f} {v.unit} (state {v.level.value}) while the bearing temperature is within its normal range. "
            "Vibration without a temperature rise points more to alignment, looseness or imbalance than to bearing failure (possible factors).",
            Severity.medium, [v] + brg[:1], ["With RMS velocity only (no spectrum) the fault type cannot be identified; spectrum analysis is needed."],
        )
    # R4 ---------------------------------------------------------------
    if brg_hot and not vib:
        b = brg_hot[0]
        add(
            "lubrication", f"Check {a.code} lubrication (bearing temperature above normal)",
            f"{b.code} = {b.latest[1]:.1f} {b.unit}, above its normal range ({b.normal_max:g}) while vibration is below its warn limit. Under- or over-lubrication is a common first check.",
            Severity.medium, [b], ["Temperature also rises with ambient conditions and load; compare with the load/current signal."],
        )
    # R5 ---------------------------------------------------------------
    flat = [s for s in a.sensors if s.flatline]
    if flat:
        add(
            "sensor_check", f"Verify instrument {flat[0].code} before acting on it",
            f"{', '.join(s.code for s in flat)}: the last samples are identical (flat-line). A frozen signal can hide a real fault or create a false one.",
            Severity.low, flat, ["A flat-line can also be a genuinely constant process value; verify locally."],
        )
    # R6 ---------------------------------------------------------------
    sv = a.service
    if sv.overdue:
        out.append(
            RecItem(
                id=rec_id_for(a.equipment_id, "preventive_service"), code=f"REC-{a.code}-preventive_service", rec_type="preventive_service",
                title=f"Schedule the overdue preventive service for {a.code}", rationale=f"{a.name}: {sv.note}", priority=Severity.medium,
                equipment_id=a.equipment_id, equipment_code=a.code, stage_code=a.stage_code, risk_score=a.risk_score, evidence=[],
                corroborating=[], assumptions=COMMON_ASSUMPTIONS + ["Service intervals are adjustable engineering assumptions, not manufacturer data."],
            )
        )
    # R7 ---------------------------------------------------------------
    covered = {s.code for s in vib} | {s.code for s in brg_hot}
    other = [s for s in a.sensors if _at_least_warn(s) and s.code not in covered]
    if other and not (crit_sensors and not [s for s in other if s.level == HealthState.critical]):
        worst_s = max(other, key=lambda s: (s.level == HealthState.critical, s.code))
        add(
            "condition_check", f"Investigate {worst_s.code} outside its limits on {a.code}",
            "; ".join(f"{s.code} = {s.latest[1]:.2f} {s.unit} ({s.level.value}; warn {s.warn:g})" for s in other) + ". Check the process condition and the instrument; this is a threshold finding, not a diagnosis.",
            Severity.high if worst_s.level == HealthState.critical else Severity.medium, other,
        )
    return out


def generate_all(db: Session, ctx: DemoContext, equipment_ids: list[int] | None = None) -> list[RecItem]:
    items: list[RecItem] = []
    for a in load_assessments(db, ctx, equipment_ids).values():
        items.extend(generate_for(a))
    return items


# ------------------------------------------------------------------ decisions and effective status
def _decisions(db: Session, ctx: DemoContext, rec_ids: list[int]) -> dict[int, RecommendationDecision]:
    if not rec_ids or ctx.session_id is None:
        return {}
    out: dict[int, RecommendationDecision] = {}
    for d in db.execute(
        select(RecommendationDecision)
        .where(RecommendationDecision.recommendation_id.in_(rec_ids), RecommendationDecision.session_id == ctx.session_id, RecommendationDecision.decided_at <= ctx.as_of)
        .order_by(RecommendationDecision.decided_at, RecommendationDecision.id)
    ).scalars():
        out[d.recommendation_id] = d
    return out


def _seeded_items(db: Session, ctx: DemoContext, equipment_id: int | None) -> list[RecItem]:
    """Recommendations written by another pipeline (e.g. ML) into ai_recommendations; shown as seeded baseline."""
    q = select(AiRecommendation, ProcessStage.code).outerjoin(ProcessStage, ProcessStage.id == AiRecommendation.process_stage_id).where(
        AiRecommendation.id < REC_ID_BASE, AiRecommendation.created_at <= ctx.as_of
    )
    if equipment_id is not None:
        q = q.where(AiRecommendation.equipment_id == equipment_id)
    out = []
    for r, stage in db.execute(q).all():
        ev: list[Evidence] = []
        try:
            for e in json.loads(r.evidence_json or "[]"):
                ev.append(Evidence(**e))
        except (ValueError, TypeError):
            ev = []
        out.append(
            RecItem(
                id=r.id, code=r.code, rec_type=r.rec_type, title=r.title, rationale=r.rationale, priority=Severity(r.priority), equipment_id=r.equipment_id,
                equipment_code=None, stage_code=stage, risk_score=r.risk_score, evidence=ev, assumptions=COMMON_ASSUMPTIONS, source="seeded",
                row_status=r.status, anomaly_event_id=r.anomaly_event_id, row_created_at=r.created_at,
            )
        )
    return out


def _to_out(db: Session, ctx: DemoContext, it: RecItem, dec: RecommendationDecision | None, eq_names: dict[int, tuple[str, str]]) -> RecommendationOut:
    status = RecommendationStatus(dec.decision) if dec else RecommendationStatus(it.row_status if it.source == "seeded" else "proposed")
    code, name = eq_names.get(it.equipment_id or -1, (it.equipment_code, None))
    return RecommendationOut(
        id=it.id, code=it.code, rec_type=it.rec_type, title=it.title, rationale=it.rationale, priority=it.priority, risk_score=it.risk_score, advisory=True,
        status=status, equipment=EntityRef(type="equipment", id=it.equipment_id, code=code, label=name) if it.equipment_id else None,
        process_stage_code=StageCode(it.stage_code) if it.stage_code else None, anomaly_event_id=it.anomaly_event_id, evidence=it.evidence,
        created_at=(it.row_created_at or ctx.as_of), decided_by_role=dec.approver_role if dec else None, decided_at=dec.decided_at if dec else None,
        work_order_id=dec.work_order_id if dec else None, model_version=RULE_ENGINE_VERSION if it.source == "rule_engine" else None,
        rule_id=RULE_ID.get(it.rec_type), corroborating_sensors=it.corroborating, assumptions=it.assumptions, decision_note=dec.note if dec else None,
        generated_for_as_of=ctx.as_of, source=it.source,
    )


def list_recommendations(db: Session, ctx: DemoContext, status: RecommendationStatus | None, equipment_id: int | None) -> list[RecommendationOut]:
    items = generate_all(db, ctx, [equipment_id] if equipment_id else None) + _seeded_items(db, ctx, equipment_id)
    decs = _decisions(db, ctx, [i.id for i in items])
    from app.models import Equipment  # noqa: PLC0415

    eq_names = {e.id: (e.code, e.name) for e in db.execute(select(Equipment)).scalars()}
    out = [_to_out(db, ctx, i, decs.get(i.id), eq_names) for i in items]
    if status is not None:
        out = [o for o in out if o.status == status]
    out.sort(key=lambda o: (-PRIORITY_ORDER[o.priority], -(o.risk_score or 0), o.code))
    return out


def resolve_recommendation(db: Session, ctx: DemoContext, rec_id: int) -> RecItem:
    if rec_id >= REC_ID_BASE:
        eid, tno = divmod(rec_id - REC_ID_BASE, 100)
        for it in generate_all(db, ctx, [eid]):
            if it.id == rec_id:
                return it
        raise ApiError(404, "recommendation_not_active", "This recommendation is not generated at the current demo clock (its evidence is not present).", {"recommendation_id": rec_id})
    row = db.get(AiRecommendation, rec_id)
    if row is None or row.created_at > ctx.as_of:
        not_found("recommendation", rec_id)
    for it in _seeded_items(db, ctx, row.equipment_id):
        if it.id == rec_id:
            return it
    not_found("recommendation", rec_id)


def ensure_catalog_row(db: Session, ctx: DemoContext, it: RecItem) -> int:
    """FK target for decisions / work orders. Visitor-independent catalog row, created lazily with a deterministic id."""
    if it.source == "seeded":
        return it.id
    if db.get(AiRecommendation, it.id) is None:
        db.add(
            AiRecommendation(
                id=it.id, code=it.code, rec_type=it.rec_type, title=it.title, rationale=it.rationale,
                evidence_json=json.dumps([e.model_dump(mode="json") for e in it.evidence], default=str), equipment_id=it.equipment_id, priority=it.priority.value,
                risk_score=it.risk_score, advisory=True, status=RecommendationStatus.proposed.value, created_at=ctx.as_of,
                data_kind="synthetic",
            )
        )
        db.flush()
    return it.id


def decide(db: Session, ctx: DemoContext, rec_id: int, body: RecommendationDecisionRequest) -> RecommendationOut:
    sid = require_session(ctx)
    it = resolve_recommendation(db, ctx, rec_id)
    existing = _decisions(db, ctx, [it.id]).get(it.id)
    if existing is not None:
        raise ApiError(409, "already_decided", f"This recommendation was already {existing.decision} in this session. Reset the session to decide again.", {"decision": existing.decision})
    approved = body.decision == "approved"
    if body.create_work_order and not approved:
        raise ApiError(422, "work_order_needs_approval", "create_work_order is only valid with decision=approved.")
    if body.create_work_order:
        if not has_permission(ctx.role, Permission.workorder_create):
            raise ApiError(403, "forbidden", f"Role '{ctx.role.value}' may not create work orders.", {"role": ctx.role.value, "permission": Permission.workorder_create.value})
        if it.equipment_id is None:
            raise ApiError(422, "no_equipment", "This recommendation has no equipment to attach a work order to.")
    row_id = ensure_catalog_row(db, ctx, it)
    wo_id = None
    wo_code = None
    if body.create_work_order:
        from app.services.workorders import create_work_order  # noqa: PLC0415

        pr = {"critical": "urgent", "high": "high", "medium": "medium", "low": "low", "info": "low"}[it.priority.value]
        wo = create_work_order(
            db, ctx,
            WorkOrderCreateRequest(
                source_type="recommendation", equipment_id=it.equipment_id, title=it.title[:200], priority=pr, recommendation_id=it.id, confirm=True,
                description=(it.rationale + "\n\nAdvisory recommendation approved by a human; verify on site.")[:4000],
            ),
            commit=False,
        )
        wo_id, wo_code = wo.id, wo.code
    dec = RecommendationDecision(
        recommendation_id=row_id, session_id=sid, decision=body.decision, approver_role=ctx.role.value, note=(body.note or None), work_order_id=wo_id, decided_at=ctx.as_of
    )
    db.add(dec)
    db.flush()
    write_audit(
        db, ctx, "recommendation.decision", "recommendation", it.code, {"status": "proposed"},
        {
            "status": body.decision, "note": body.note, "work_order": wo_code, "advisory": True, "executes_on_machines": False,
            "evidence": [{"metric": e.metric, "observed": e.observed, "unit": e.unit} for e in it.evidence[:6]],
        },
    )
    db.commit()
    from app.models import Equipment  # noqa: PLC0415

    eq_names = {e.id: (e.code, e.name) for e in db.execute(select(Equipment)).scalars()}
    return _to_out(db, ctx, it, dec, eq_names)

