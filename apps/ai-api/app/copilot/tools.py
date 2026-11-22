"""Typed, read-only Copilot tools (DML-071/072).

Every tool:
  * has a Pydantic argument model (-> JSON schema), a required RBAC permission (`copilot:tool:<name>`), max rows, units;
  * calls the EXISTING service functions in-process with the caller's DemoContext (never raw SQL, never a second KPI
    implementation, never data after as_of - the services enforce ADR-005 and a derived context is only ever EARLIER);
  * returns ToolResult {data, facts (= the evidence numbers), provenance, assumptions, limits};
  * never writes business records. `run_business_scenario` only calls the what-if calculators.
String fields coming from the database are sanitised (tool output is data, never instructions).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.copilot.safety import sanitise_data
from app.copilot.verifier import numbers_from_text
from app.errors import ApiError
from app.services.demo_context import DemoContext, provenance
from app.services.rbac import Permission, has_permission

TZ_NOTE = "Times are mill-local (Asia/Bangkok)."


# ------------------------------------------------------------------ result types
@dataclass
class Fact:
    key: str
    label: str
    value: float
    unit: str = ""

    def out(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label, "value": self.value, "unit": self.unit}


@dataclass
class ToolResult:
    tool: str
    args: dict[str, Any]
    status: str = "ok"  # ok | no_data | error | denied
    data: dict[str, Any] = field(default_factory=dict)
    facts: list[Fact] = field(default_factory=list)
    provenance: dict[str, Any] | None = None
    assumptions: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    message: str | None = None
    duration_ms: float | None = None
    sanitised: list[str] = field(default_factory=list)

    def fact(self, key: str) -> float | None:
        for f in self.facts:
            if f.key == key:
                return f.value
        return None

    def add(self, key: str, label: str, value: Any, unit: str = "") -> None:
        if value is None:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        if v != v:  # NaN
            return
        self.facts.append(Fact(key, label, v, unit))

    def digest(self) -> str:
        raw = json.dumps(self.data, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def summary(self) -> str:
        if self.status != "ok":
            return f"{self.status}: {self.message or ''}".strip()
        return f"{len(self.facts)} evidence values" + (f"; {self.message}" if self.message else "")


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


DateArg = Field("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$", description="today | yesterday | YYYY-MM-DD (mill business day, <= as_of)")


class ProductionArgs(_Args):
    business_date: str = DateArg


class OerTrendArgs(_Args):
    period: Literal["7d", "30d"] = "7d"


class EquipmentArgs(_Args):
    equipment_code: str | None = Field(None, pattern=r"^[A-Z]{2,5}(-[A-Z]{2,5})?-\d{2}$", description="e.g. PRS-03; omit for the ranked list")
    limit: int = Field(5, ge=1, le=10)


class AlertArgs(_Args):
    module: Literal["production", "maintenance", "logistics", "energy", "quality"] | None = None
    limit: int = Field(10, ge=1, le=20)
    include_findings: bool = True


class PeriodArgs(_Args):
    period: Literal["7d", "30d"] = "30d"


class EnergyArgs(_Args):
    period: Literal["today", "7d", "30d"] = "today"


class LogisticsArgs(_Args):
    pass


class ScenarioArgs(_Args):
    kind: Literal["production", "downtime"] = "production"
    oer_delta_pp: float | None = Field(None, ge=-5, le=5)
    ffb_intake_t_per_day: float | None = Field(None, gt=0, le=10000)
    availability_pct: float | None = Field(None, gt=0, le=100)
    downtime_hours: float | None = Field(None, gt=0, le=720)
    equipment_code: str | None = Field(None, pattern=r"^[A-Z]{2,5}(-[A-Z]{2,5})?-\d{2}$")
    planned: bool = False
    days: int = Field(30, ge=1, le=366)
    cut_pct: float | None = Field(None, gt=0, le=100, description="Echo of a percentage cut the hours were derived from")
    default_amount: bool = Field(False, description="True when no amount was given and the default was used")


class SearchArgs(_Args):
    query: str = Field(min_length=2, max_length=300)
    k: int = Field(3, ge=1, le=5)


class TraceArgs(_Args):
    lot_code: str | None = Field(None, pattern=r"^CPO-\d{8}-T\d$")


# ------------------------------------------------------------------ helpers
def _prov(ctx: DemoContext, source: str, kind: str = "synthetic_actual", mv: str | None = None) -> dict[str, Any]:
    p = provenance(kind, source, ctx, mv)
    p["as_of"] = ctx.as_of.isoformat()
    return p


def _dump(o: Any) -> Any:
    return o.model_dump(mode="json") if hasattr(o, "model_dump") else o


def _r(v: Any, n: int = 3) -> float | None:
    try:
        return None if v is None else round(float(v), n)
    except (TypeError, ValueError):
        return None


def resolve_day(ctx: DemoContext, value: str) -> date:
    if value == "today":
        return ctx.business_date
    if value == "yesterday":
        return ctx.business_date - timedelta(days=1)
    d = date.fromisoformat(value)
    if d > ctx.business_date:
        raise ApiError(422, "future_date", "That date is after the demo clock; the copilot never reads data beyond as_of.")
    return d


def ctx_end_of_day(ctx: DemoContext, d: date) -> DemoContext:
    """A context whose clock is the end of an EARLIER business day (never later than ctx.as_of)."""
    if d >= ctx.business_date:
        return ctx
    _, end = ctx.day_bounds(d)
    as_of = min(end - timedelta(seconds=1), ctx.as_of)
    if as_of < ctx.window_start:
        raise ApiError(422, "out_of_window", "That date is before the synthetic dataset window.")
    return ctx.model_copy(update={"as_of": as_of})


def _kpi_facts(res: ToolResult, kpis: list[dict], prefix: str = "") -> dict[str, dict]:
    out = {}
    for k in kpis:
        key = prefix + k["key"]
        out[k["key"]] = {"value": _r(k.get("value")), "previous": _r(k.get("previous")), "delta": _r(k.get("delta")),
                         "delta_pct": _r(k.get("delta_pct"), 2), "unit": k.get("unit"), "label": k.get("label")}  # fmt: skip
        res.add(key, k.get("label", key), _r(k.get("value")), k.get("unit", ""))
        res.add(key + "_previous", k.get("label", key) + " (previous period)", _r(k.get("previous")), k.get("unit", ""))
        res.add(key + "_delta", k.get("label", key) + " (change)", _r(k.get("delta")), k.get("unit", ""))
        res.add(key + "_delta_pct", k.get("label", key) + " (change %)", _r(k.get("delta_pct"), 2), "%")
    return out


def _ml_metrics(res: ToolResult, db: Session, name: str) -> dict[str, Any]:
    """Measured metrics of an ML model from the model registry (so the answer states what the model is and its limits)."""
    try:
        from app.ml.service import model_info  # noqa: PLC0415

        info = model_info(db, name)
    except Exception:  # noqa: BLE001 - registry missing: the answer simply omits ML context
        return {}
    out = {"name": name, "task": info.get("task"), "version": info.get("version"), "metrics": {}}
    for m in info.get("metrics", []):
        res.add(f"ml_{name}_{m['name']}", f"{name} {m['name']} (held-out, synthetic)", _r(m.get("model"), 4))
        res.add(f"ml_{name}_{m['name']}_baseline", f"{name} {m['name']} of baseline {m.get('baseline_name')}", _r(m.get("baseline"), 4))
        out["metrics"][m["name"]] = {"model": m.get("model"), "baseline": m.get("baseline"), "beats_baseline": m.get("beats_baseline")}
    return out


# ------------------------------------------------------------------ tools
def t_production_summary(db: Session, ctx: DemoContext, a: ProductionArgs) -> ToolResult:
    from app.services import production  # noqa: PLC0415

    d = resolve_day(ctx, a.business_date)
    out = production.summary(db, ctx, d)
    res = ToolResult("get_production_summary", a.model_dump())
    kp = _kpi_facts(res, out["kpis"])
    mb = out["mass_balance"]
    res.add("mass_balance_closure_pct", "Mass-balance closure", mb.get("closure_pct"), "%")
    res.add("oil_losses_t", "Oil lost in process streams", mb.get("oil_losses_t"), "t")
    res.data = {"business_date": d.isoformat(), "kpis": kp, "window_start": str(out["window_start"]), "window_end": str(out["window_end"]),
                "oer_formula": out["oer_formula"]["expression"]}  # fmt: skip
    if not kp.get("ffb_processed_t", {}).get("value"):
        res.status, res.message = "no_data", "No FFB processed in this window yet."
    res.provenance = _prov(ctx, "process_hourly via services.production.summary")
    res.assumptions = ["OER = sum(CPO) / sum(FFB processed) x 100 over complete hours of the mill business day up to the demo clock.",
                       "'Previous' = the same clock span on the previous day."]  # fmt: skip
    return res


def t_oer_trend(db: Session, ctx: DemoContext, a: OerTrendArgs) -> ToolResult:
    from app.schemas.common import Period  # noqa: PLC0415
    from app.services import kpi_insights, production  # noqa: PLC0415

    out = production.oer_trend(db, ctx, Period(a.period), "day")
    res = ToolResult("get_oer_trend", a.model_dump())
    pts = [(p["t"], p["v"]) for p in out["oer"]["points"] if p["v"] is not None]
    exp = {str(p["t"]): p["v"] for p in out["expected_oer"]["points"]}
    days = []
    for t, v in pts:
        lt = (t if isinstance(t, datetime) else datetime.fromisoformat(str(t).replace("Z", "+00:00"))).astimezone(ctx.local_as_of.tzinfo)
        key = lt.date().isoformat()
        e = exp.get(str(t))
        days.append({"date": key, "oer_pct": _r(v, 2), "expected_oer_pct": _r(e, 2)})
        res.add(f"oer_{key}", f"OER on {key}", _r(v, 2), "%")
        res.add(f"expected_oer_{key}", f"Expected (trailing 28-day) OER on {key}", _r(e, 2), "%")
    res.add("reference_days", "Reference window for expected OER", 28, "days")
    band = [p for p in out["expected_band"]["points"] if p.get("lower") is not None]
    if band:
        res.add("band_low_today", "Expected OER - 2 s.d. (latest day)", _r(band[-1]["lower"], 2), "%")
        res.add("band_high_today", "Expected OER + 2 s.d. (latest day)", _r(band[-1]["upper"], 2), "%")
    if days:
        last = days[-1]
        res.add("oer_today", "OER today (so far)", last["oer_pct"], "%")
        res.add("expected_oer_today", "Expected OER today (trailing 28-day)", last["expected_oer_pct"], "%")
        if last["oer_pct"] is not None and last["expected_oer_pct"] is not None:
            res.add("oer_gap_pp", "OER minus expected", round(last["oer_pct"] - last["expected_oer_pct"], 2), "pp")
    # measured factor screen (rule R1 of the insight service): deviations vs the 28 reference days, no causal claim
    factors: list[dict] = []
    finding = None
    for item in kpi_insights.insights(db, ctx)["items"]:
        ev = item.get("evidence") or []
        if ev and ev[0].get("metric") == "oer_pct":
            finding = item
            for e in ev[1:]:
                factors.append({"metric": e["metric"], "label": e["label"], "observed": e["observed"], "reference_mean": e["expected"],
                                "unit": e["unit"], "note": e.get("note")})  # fmt: skip
                res.add(f"factor_{e['metric']}_observed", f"{e['label']} today", e["observed"], e["unit"])
                res.add(f"factor_{e['metric']}_reference", f"{e['label']} reference mean", e["expected"], e["unit"])
            e0 = ev[0]
            res.add("r1_oer_today", "OER today (insight rule R1)", _r(e0["observed"], 2), "%")
            res.add("r1_oer_reference", "Trailing 28-day OER (insight rule R1)", _r(e0["expected"], 2), "%")
            res.add("r1_gap_pp", "Gap below trailing 28-day OER", _r(e0["expected"] - e0["observed"], 2), "pp")
            nr = e0.get("normal_range") or {}
            res.add("r1_normal_low", "Normal range low (28-day OER - 2 s.d.)", _r(nr.get("low"), 2), "%")
            res.add("r1_normal_high", "Normal range high (28-day OER + 2 s.d.)", _r(nr.get("high"), 2), "%")
    ml = _ml_metrics(res, db, "oer_forecast")
    res.data = {"ml_oer_forecast": ml, "daily": days[-31:], "factors": factors, "finding_headline": finding["headline"] if finding else None,
                "finding_detail": finding["detail"] if finding else None, "expected_definition": out["expected_band"]["interval"]}  # fmt: skip
    res.provenance = _prov(ctx, "process_hourly via services.production.oer_trend + services.kpi_insights (rule R1)")
    res.assumptions = ["Expected OER = trailing 28-day OER (ratio of sums); a statistical reference, not a model forecast."]
    res.limits = ["Factors are process signals deviating > 2 s.d. from the 28 reference days: statistical association, not proven cause.",
                  "The ML hourly OER forecast does not beat its naive baseline (docs/MODEL_EVALUATION.md), so it is not used here."]  # fmt: skip
    if not days:
        res.status, res.message = "no_data", "No processed hours in the period."
    return res


def t_equipment_health(db: Session, ctx: DemoContext, a: EquipmentArgs) -> ToolResult:
    from app.services import maintenance_health as mh  # noqa: PLC0415

    res = ToolResult("get_equipment_health", a.model_dump())
    if a.equipment_code:
        allx = mh.load_assessments(db, ctx)
        items = [x for x in allx.values() if x.code == a.equipment_code]
        if not items:
            res.status, res.message = "no_data", f"Unknown equipment code {a.equipment_code}."
            res.provenance = _prov(ctx, "equipment")
            return res
        ranked = sorted(allx.values(), key=lambda x: (-x.risk_score, x.criticality, x.code))
        rank = [x.code for x in ranked].index(a.equipment_code) + 1
    else:
        items = mh.rank_failure_risk(db, ctx, a.limit)
        rank = None
    rows = []
    for i, x in enumerate(items):
        h = _dump(mh.health_out(x, ctx))
        breached = [c for c in h["criteria"] if c.get("breached") and c.get("affects_state") and c.get("kind") == "sensor_limit"]
        # keep the most severe criterion per sensor
        per_sensor: dict[str, dict] = {}
        for c in breached:
            prev = per_sensor.get(c["sensor_code"])
            if prev is None or c["state_if_breached"] == "critical":
                per_sensor[c["sensor_code"]] = c
        sensors = [{"sensor_code": c["sensor_code"], "observed": _r(c["observed"], 2), "limit": _r(c["limit"], 2), "unit": c["unit"],
                    "limit_kind": "critical" if c["state_if_breached"] == "critical" else "warning", "iso_zone": c.get("iso_zone"),
                    "observed_ts": c.get("observed_ts")} for c in per_sensor.values()]  # fmt: skip
        trend = [{"sensor_code": s.code, "slope_per_day": _r(s.trend_slope_per_day, 3), "unit": s.unit, "r2": _r(s.trend_r2, 3)}
                 for s in x.sensors if s.trend_rising and s.trend_slope_per_day]  # fmt: skip
        rows.append({"code": x.code, "name": x.name, "stage": x.stage_code, "criticality": x.criticality, "state": x.state.value if hasattr(x.state, "value") else str(x.state),
                     "risk_index": _r(x.risk_score, 1), "anomaly_score": _r(x.anomaly_score, 3), "breached_sensors": sensors, "rising_trends": trend,
                     "open_alerts": [{"code": al.code, "severity": al.severity, "title": al.title} for al in x.open_alerts][:5],
                     "active_work_orders": x.active_work_orders})  # fmt: skip
        p = f"eq_{x.code}"
        res.add(f"{p}_risk", f"{x.code} relative risk index (0-100)", _r(x.risk_score, 1))
        res.add(f"{p}_anomaly", f"{x.code} ML anomaly score (0-1)", _r(x.anomaly_score, 3))
        res.add(f"{p}_rank", f"{x.code} rank by risk index", rank if rank else i + 1)
        for s in sensors:
            res.add(f"{p}_{s['sensor_code']}_observed", f"{s['sensor_code']} latest reading", s["observed"], s["unit"])
            res.add(f"{p}_{s['sensor_code']}_limit", f"{s['sensor_code']} {s['limit_kind']} limit", s["limit"], s["unit"])
        for t in trend:
            res.add(f"{p}_{t['sensor_code']}_slope", f"{t['sensor_code']} trend per day", t["slope_per_day"], t["unit"] + "/day")
    res.data = {"equipment": rows, "rank": rank, "ml_equipment_anomaly": _ml_metrics(res, db, "equipment_anomaly")}
    res.provenance = _prov(ctx, "sensor_readings + alerts + work_orders via services.maintenance_health")
    res.assumptions = ["Health state = worst sensor vs its warning/critical limit (latest readings <= as_of); explicit criteria in each item."]
    res.limits = ["The risk index is a relative ranking (0-100), NOT a calibrated failure probability.",
                  "Anomaly scores are advisory and need human verification on site."]  # fmt: skip
    return res


def t_active_alerts(db: Session, ctx: DemoContext, a: AlertArgs) -> ToolResult:
    from app.services import kpi_alerts, kpi_insights  # noqa: PLC0415

    res = ToolResult("get_active_alerts", a.model_dump())
    out = kpi_alerts.list_alerts(db, ctx, module=a.module, active_only=True, limit=a.limit)
    items = []
    sev_count: dict[str, int] = {}
    for al in out["items"]:
        sev_count[al["severity"]] = sev_count.get(al["severity"], 0) + 1
        items.append({"code": al["code"], "severity": al["severity"], "status": al["status"], "title": al["title"], "module": al["module"],
                      "equipment": (al.get("equipment") or {}).get("code"), "raised_at": str(al["raised_at"]), "priority_score": _r(al.get("priority_score"), 1),
                      "suggested_team": al.get("suggested_team"), "source": al.get("source")})  # fmt: skip
        res.add(f"alert_{al['code']}_priority", f"{al['code']} priority score", _r(al.get("priority_score"), 1))
    total = out.get("total", len(items))
    res.add("active_alerts_total", "Active alerts", total)
    res.add("active_alerts_listed", "Active alerts listed", len(items))
    for s, n in sev_count.items():
        res.add(f"active_alerts_{s}", f"Active {s} alerts (listed)", n)
    findings = []
    if a.include_findings:
        ins = kpi_insights.insights(db, ctx)
        for i, it in enumerate(ins["items"][:8]):
            findings.append({"headline": it["headline"], "severity": it["severity"], "suggested_team": it["suggested_team"],
                             "suggested_decision": it["suggested_decision"], "detail": it["detail"]})  # fmt: skip
            for j, e in enumerate(it.get("evidence") or []):
                res.add(f"finding{i}_ev{j}_observed", f"{e.get('label')} (observed)", e.get("observed"), e.get("unit", ""))
                res.add(f"finding{i}_ev{j}_expected", f"{e.get('label')} (reference)", e.get("expected"), e.get("unit", ""))
            res.add(f"finding{i}_rank", "Finding priority rank", i + 1)
            for j, num in enumerate(numbers_from_text(it["headline"])):
                res.add(f"finding{i}_text{j}", "Number quoted in the finding headline (computed by the insight service)", num)
        res.add("findings_total", "Findings", len(ins["items"]))
        res.add("findings_listed", "Findings listed", len(findings))
    res.data = {"alerts": items, "findings": findings, "total": total}
    res.provenance = _prov(ctx, "alerts (+ session status changes) via services.kpi_alerts; findings via services.kpi_insights")
    res.limits = ["Alerts are threshold rules or ML anomaly flags: advisory, not diagnoses; verify on site."]
    return res


def t_downtime(db: Session, ctx: DemoContext, a: PeriodArgs) -> ToolResult:
    from app.schemas.common import Period  # noqa: PLC0415
    from app.services import maintenance  # noqa: PLC0415

    out = _dump(maintenance.downtime_analysis(db, ctx, Period(a.period)))
    res = ToolResult("get_downtime_analysis", a.model_dump())
    from app.services import kpi  # noqa: PLC0415

    plant = next((k for k in kpi.executive_kpis(db, ctx, Period(a.period))["kpis"] if k["key"] == "plant_downtime_h"), None)
    res.add("plant_downtime_h", "Plant downtime (process_hourly, same as the Executive KPI)", _r(plant["value"], 2) if plant else None, "h")
    res.add("total_downtime_h", "Equipment maintenance-event downtime (sum of event durations, incl. planned work, can overlap)", out["total_downtime_h"], "h")
    res.add("availability_pct", "Plant availability", out["availability_pct"], "%")
    hours = sorted(out["by_hour_of_day"], key=lambda b: -b["downtime_h"])
    eqs = out["by_equipment"][:5]
    causes = out["by_cause"][:5]
    for b in hours[:3]:
        res.add(f"hour_{b['key']}_h", f"Downtime starting in hour {b['label']}", b["downtime_h"], "h")
        res.add(f"hour_{b['key']}_start", "Hour of day", int(b["key"]))
        res.add(f"hour_{b['key']}_end", "Hour of day end", int(b["key"]) + 1)
    for b in eqs:
        res.add(f"equip_{b['key']}_h", f"{b['key']} downtime", b["downtime_h"], "h")
        res.add(f"equip_{b['key']}_events", f"{b['key']} events", b["events"])
    for b in causes:
        res.add(f"cause_{b['key']}_h", f"{b['label']} downtime", b["downtime_h"], "h")
        res.add(f"cause_{b['key']}_events", f"{b['label']} events", b["events"])
    res.add("period_days", "Period length", 7 if a.period == "7d" else 30, "days")
    res.data = {"plant_downtime_h": _r(plant["value"], 2) if plant else None, "total_downtime_h": out["total_downtime_h"], "availability_pct": out["availability_pct"],
                "top_hours": [{"hour": int(b["key"]), "label": b["label"], "downtime_h": b["downtime_h"], "events": b["events"]} for b in hours[:3]],
                "top_equipment": eqs, "by_cause": causes}  # fmt: skip
    if not out["total_downtime_h"]:
        res.status, res.message = "no_data", "No downtime recorded in the period."
    res.provenance = _prov(ctx, "maintenance_events + process_hourly via services.maintenance.downtime_analysis")
    res.assumptions = ["Plant downtime = hours the mill was stopped (process_hourly; the Executive KPI definition).",
                       "Equipment maintenance-event downtime = sum of maintenance-event durations (includes planned inspection/lubrication, events can "
                       "overlap); it is split across the mill-local hours it overlaps and is NOT the same as plant downtime."]  # fmt: skip
    return res


def t_logistics(db: Session, ctx: DemoContext, a: LogisticsArgs) -> ToolResult:
    from app.schemas.common import Period  # noqa: PLC0415
    from app.services import logistics  # noqa: PLC0415

    q = logistics.queue_now(db, ctx)
    k = logistics.kpis(db, ctx, Period.today)
    res = ToolResult("get_logistics_summary", a.model_dump())
    res.add("trucks_waiting", "Trucks waiting for the weighbridge now", q["trucks_waiting"], "trucks")
    res.add("trucks_unloading", "Trucks unloading now", q["trucks_unloading"], "trucks")
    res.add("queue_avg_wait_min", "Average wait of trucks queued now", q.get("avg_wait_min"), "min")
    res.add("queue_max_wait_min", "Longest wait of trucks queued now", q.get("max_wait_min"), "min")
    kp = _kpi_facts(res, k["kpis"], prefix="today_")
    res.data = {"trucks_waiting": q["trucks_waiting"], "trucks_unloading": q["trucks_unloading"], "avg_wait_min": q.get("avg_wait_min"),
                "max_wait_min": q.get("max_wait_min"), "today_kpis": kp}  # fmt: skip
    res.provenance = _prov(ctx, "truck_trips + queue_events via services.logistics")
    res.limits = ["Logistics flags describe flow, never an accusation against a supplier or driver."]
    return res


def t_energy(db: Session, ctx: DemoContext, a: EnergyArgs) -> ToolResult:
    from app.schemas.common import Period  # noqa: PLC0415
    from app.services import energy  # noqa: PLC0415

    out = energy.summary(db, ctx, Period(a.period))
    res = ToolResult("get_energy_summary", a.model_dump())
    kp = _kpi_facts(res, out["kpis"])
    stages = out.get("by_stage", [])[:4]
    for s in stages:
        res.add(f"stage_{s['key']}_kwh", f"{s['label']} electricity", s["kwh"], "kWh")
        res.add(f"stage_{s['key']}_share", f"{s['label']} share", s["share_pct"], "%")
    ab = []
    for i, d in enumerate(out.get("abnormal_days", [])[-3:]):
        res.add(f"abn{i}_actual_kwh", "Abnormal day actual kWh", d["actual_kwh"], "kWh")
        res.add(f"abn{i}_expected_kwh", "Abnormal day expected kWh (production-adjusted)", d["expected_kwh"], "kWh")
        res.add(f"abn{i}_z", "Abnormal day residual z-score", d["z_score"])
        res.add(f"abn{i}_ffb_t", "Abnormal day FFB processed", d["ffb_processed_t"], "t")
        if d["expected_kwh"]:
            res.add(f"abn{i}_excess_pct", "Excess vs expected", round((d["actual_kwh"] / d["expected_kwh"] - 1) * 100, 1), "%")
        t = d["t"] if isinstance(d["t"], datetime) else datetime.fromisoformat(str(d["t"]).replace("Z", "+00:00"))
        ab.append({"date": t.astimezone(ctx.local_as_of.tzinfo).date().isoformat(), "actual_kwh": d["actual_kwh"], "expected_kwh": d["expected_kwh"],
                   "z_score": d["z_score"], "severity": d.get("severity"), "basis": d.get("basis")})  # fmt: skip
    res.data = {"kpis": kp, "by_stage": stages, "abnormal_days": ab, "ml_energy_forecast": _ml_metrics(res, db, "energy_forecast")}
    res.provenance = _prov(ctx, "energy_consumption via services.energy.summary")
    res.assumptions = ["kWh/t = plant electricity / FFB processed (ratio of sums). Abnormal = production-adjusted regression residual z > 2."]
    res.limits = ["The ML energy forecast and anomaly model do not beat their baselines; the statistical baseline is used instead."]
    return res


def _eq_id(db: Session, code: str | None) -> int | None:
    if not code:
        return None
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.core import Equipment  # noqa: PLC0415

    return db.execute(select(Equipment.id).where(Equipment.code == code)).scalar_one_or_none()


def t_business_scenario(db: Session, ctx: DemoContext, a: ScenarioArgs) -> ToolResult:
    res = ToolResult("run_business_scenario", a.model_dump())
    if a.kind == "downtime":
        from app.schemas.maintenance import MaintenanceImpactRequest  # noqa: PLC0415
        from app.services import maintenance  # noqa: PLC0415

        hours = a.downtime_hours or 1.0
        out = _dump(maintenance.impact(db, ctx, MaintenanceImpactRequest(equipment_id=_eq_id(db, a.equipment_code), downtime_hours=hours, planned=a.planned)))
        res.add("downtime_hours", "Downtime hours avoided (input)", hours, "h")
        if a.cut_pct is not None:
            res.add("cut_pct", "Requested downtime cut (user input)", a.cut_pct, "%")
        if a.default_amount:
            res.add("default_hours_used", "Default hours used (no amount given)", hours, "h")
        for key, lab, unit in [("lost_ffb_processing_t", "FFB processing lost", "t"), ("lost_cpo_opportunity_t", "CPO opportunity lost", "t"),
                               ("lost_value_thb", "Lost value (illustrative price)", "THB"), ("maintenance_cost_thb", "Maintenance cost", "THB"),
                               ("total_impact_thb", "Total impact", "THB")]:  # fmt: skip
            res.add(key, lab, out[key], unit)
        for c in out.get("comparison", []):
            res.add(f"{c['key']}_total_thb", f"{c['label']} total impact", c["total_impact_thb"], "THB")
            res.add(f"{c['key']}_cpo_t", f"{c['label']} CPO lost", c["lost_cpo_opportunity_t"], "t")
        res.data = {k: out[k] for k in ("lost_ffb_processing_t", "lost_cpo_opportunity_t", "lost_value_thb", "maintenance_cost_thb", "total_impact_thb",
                                        "recovery_scenario", "equipment_code", "notice")}  # fmt: skip
        res.data["comparison"] = out.get("comparison", [])
        res.assumptions = [x["label"] + ": " + str(x.get("value")) for x in out.get("assumptions", [])][:6]
        res.limits = [out["notice"]] + out.get("required_real_data", [])[:3]
        res.provenance = {**out["provenance"], "as_of": ctx.as_of.isoformat()}
        return res
    from app.schemas.scenarios import ProductionWhatIfRequest  # noqa: PLC0415
    from app.services import scenarios  # noqa: PLC0415

    base = _dump(scenarios.production_what_if(db, ctx, ProductionWhatIfRequest(days=a.days)))["baseline_inputs"]
    req: dict[str, Any] = {"days": a.days}
    if a.oer_delta_pp is not None:
        req["oer_pct"] = round(base["oer_pct"] + a.oer_delta_pp, 4)
    if a.ffb_intake_t_per_day:
        req["ffb_intake_t_per_day"] = a.ffb_intake_t_per_day
    if a.availability_pct:
        req["availability_pct"] = a.availability_pct
    out = _dump(scenarios.production_what_if(db, ctx, ProductionWhatIfRequest(**req)))
    res.add("days", "Horizon", a.days, "days")
    if a.oer_delta_pp is not None:
        res.add("oer_delta_pp", "OER change (input)", a.oer_delta_pp, "pp")
    for k, v in out["baseline_inputs"].items():
        res.add(f"baseline_{k}", f"Baseline {k} (trailing 30 days)", _r(v, 2))
    for k, v in out["inputs_used"].items():
        res.add(f"input_{k}", f"Scenario {k}", _r(v, 2))
    deltas = {}
    for kv in out["delta"]:
        res.add(f"delta_{kv['key']}", f"Change in {kv['label']}", _r(kv["value"], 2), kv["unit"])
        deltas[kv["key"]] = {"value": _r(kv["value"], 2), "unit": kv["unit"]}
    for kv in out["scenario"]:
        res.add(f"scenario_{kv['key']}", f"Scenario {kv['label']}", _r(kv["value"], 2), kv["unit"])
    res.data = {"baseline_inputs": out["baseline_inputs"], "inputs_used": out["inputs_used"], "delta": deltas, "warnings": out.get("warnings", []),
                "calculation_example": out.get("calculation_example")}  # fmt: skip
    res.assumptions = [x["label"] + ": " + str(x.get("value")) for x in out.get("assumptions", [])][:6]
    res.limits = ["What-if calculation with adjustable assumptions on synthetic data - not a forecast and not verified financial results."]
    res.provenance = {**out["provenance"], "as_of": ctx.as_of.isoformat()}
    return res


def t_search_documents(db: Session, ctx: DemoContext, a: SearchArgs) -> ToolResult:
    from app.copilot import kb  # noqa: PLC0415

    hits = kb.search(db, a.query, a.k)
    res = ToolResult("search_demo_documents", a.model_dump())
    res.data = {"hits": hits}
    for i, h in enumerate(hits):
        for j, num in enumerate(numbers_from_text(f"{h['title']} {h['heading']} {h['snippet']}")):
            res.add(f"doc{i}_num{j}", f"Number quoted from {h['ref']}", num)
    if not hits:
        res.status, res.message = "no_data", "No sample document matched."
    res.provenance = {"kind": "synthetic_actual", "source": "kb_chunks (newly authored SAMPLE documents, not company documents)", "as_of": ctx.as_of.isoformat(), "model_version": "tfidf-kb@1"}
    res.limits = ["Sample documents written for this demo; they are not real company procedures."]
    return res


def t_supplier_trace(db: Session, ctx: DemoContext, a: TraceArgs) -> ToolResult:
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.production import CpoOutputLot  # noqa: PLC0415
    from app.schemas.common import Period  # noqa: PLC0415
    from app.services import traceability  # noqa: PLC0415

    res = ToolResult("get_supplier_trace", a.model_dump())
    if a.lot_code:
        lot_id = db.execute(select(CpoOutputLot.id).where(CpoOutputLot.code == a.lot_code)).scalar_one_or_none()
    else:
        lots = _dump(traceability.list_lots(db, ctx, Period.last_7d, 1, 0))["items"]
        lot_id = lots[0]["id"] if lots else None
    if lot_id is None:
        res.status, res.message = "no_data", "No CPO lot found at the demo clock."
        res.provenance = _prov(ctx, "cpo_output_lots")
        return res
    rep = _dump(traceability.lot_report(db, ctx, lot_id))
    shares = rep["supplier_shares"][:5]
    res.add("lot_quantity_t", "Lot quantity", rep["lot"]["quantity_t"], "t")
    res.add("supplier_count", "Suppliers in lot", rep["lot"]["supplier_count"])
    for s in shares:
        res.add(f"share_{s['supplier_code']}", f"{s['supplier_code']} share", _r(s["share_pct"], 2), "%")
    res.data = {"lot": rep["lot"], "method": rep["method"], "top_suppliers": shares}
    res.provenance = _prov(ctx, "batch_inputs + lot_compositions via services.traceability.lot_report")
    res.limits = ["Mass-balance attribution: supplier shares, not physical segregation; no certification claim."]
    return res


# ------------------------------------------------------------------ registry
@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    args_model: type[_Args]
    permission: Permission
    fn: Callable[[Session, DemoContext, Any], ToolResult]
    max_rows: int
    units: str
    read_only: bool = True

    def schema(self) -> dict[str, Any]:
        s = self.args_model.model_json_schema()
        s.pop("title", None)
        return s


TOOLS: dict[str, ToolDef] = {
    t.name: t
    for t in [
        ToolDef("get_production_summary", "Business-day production KPIs (FFB, CPO, OER, KER, throughput, downtime) vs previous day.", ProductionArgs,
                Permission.tool_production_summary, t_production_summary, 12, "t, %, h"),
        ToolDef("get_oer_trend", "Daily OER vs trailing 28-day expectation, plus measured deviating process signals (statistical, not causal).", OerTrendArgs,
                Permission.tool_oer_trend, t_oer_trend, 31, "%"),
        ToolDef("get_equipment_health", "Equipment health state with explicit sensor criteria and the relative risk index ranking.", EquipmentArgs,
                Permission.tool_equipment_health, t_equipment_health, 10, "sensor units, index 0-100"),
        ToolDef("get_active_alerts", "Active alerts (effective status for this session) and prioritised measured findings.", AlertArgs,
                Permission.tool_active_alerts, t_active_alerts, 20, "count, score"),
        ToolDef("get_downtime_analysis", "Downtime by hour of day, equipment and cause; plant availability.", PeriodArgs,
                Permission.tool_downtime_analysis, t_downtime, 15, "h, %"),
        ToolDef("get_logistics_summary", "Trucks waiting/unloading now and today's wait/turnaround KPIs.", LogisticsArgs,
                Permission.tool_logistics_summary, t_logistics, 12, "trucks, min"),
        ToolDef("get_energy_summary", "Electricity/steam/water per tonne, stage breakdown, production-adjusted abnormal days.", EnergyArgs,
                Permission.tool_energy_summary, t_energy, 15, "kWh, kWh/t, t/t"),
        ToolDef("run_business_scenario", "What-if only: production (OER/intake/availability) or downtime impact; never changes records.", ScenarioArgs,
                Permission.tool_business_scenario, t_business_scenario, 20, "t, THB"),
        ToolDef("search_demo_documents", "Search the newly authored SAMPLE documents (process overview, inspection procedure, KPI guide...).", SearchArgs,
                Permission.tool_search_documents, t_search_documents, 5, "-"),
        ToolDef("get_supplier_trace", "Mass-balance supplier shares of a CPO lot.", TraceArgs, Permission.tool_supplier_trace, t_supplier_trace, 5, "%, t"),
    ]
}  # fmt: skip


class ToolDenied(Exception):
    pass


def run_tool(db: Session, ctx: DemoContext, name: str, args: dict[str, Any] | None) -> ToolResult:
    """Validate, permission-check (server-side, before any data access), execute, sanitise. Never raises for tool errors."""
    t0 = time.perf_counter()
    td = TOOLS.get(name)
    if td is None:
        return ToolResult(name, args or {}, status="denied", message="Unknown tool (only the allow-listed read-only tools exist).")
    if not has_permission(ctx.role, td.permission):
        return ToolResult(name, args or {}, status="denied", message=f"Role {ctx.role.value} is not allowed to use {name}.")
    try:
        parsed = td.args_model(**(args or {}))
    except ValidationError as exc:
        return ToolResult(name, args or {}, status="error", message="Invalid arguments: " + "; ".join(e["msg"] for e in exc.errors()[:3]))
    try:
        res = td.fn(db, ctx, parsed)
    except ApiError as exc:
        res = ToolResult(name, parsed.model_dump(), status="no_data", message=exc.message)
    except Exception as exc:  # noqa: BLE001 - a tool failure must never break the chat
        db.rollback()
        res = ToolResult(name, parsed.model_dump(), status="error", message=f"Tool failed: {type(exc).__name__}")
    res.data, flags = sanitise_data(res.data)
    res.sanitised = flags
    if res.provenance is None:
        res.provenance = _prov(ctx, name)
    res.facts = res.facts[: 400]
    res.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return res
