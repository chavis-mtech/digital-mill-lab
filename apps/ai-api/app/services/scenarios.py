"""Scenario catalog (measured highlights), production what-if calculator and saved scenarios (DML-050/087/089).

Owner: backend-b.

Catalog: `scenario_runs` gives the windows / focus / baseline timestamps. Its `description` and `expected_effects_json`
document what each episode was *designed* to do and are NOT shown (the build plan "Design intent is not evidence"): the effects
returned here are computed from the data - focus_ts versus baseline_ts over the SAME hours of the day - and carry a
significance note against the robust day-to-day variation of the previous 28 days. A scenario whose focus_ts is after the
demo clock returns no highlights (no future data is read).

Production what-if (`POST /scenarios/production/calculate`):
  running_h/day   = scheduled_h/day x availability / 100
  capacity_t/day  = running_h/day x rated capacity (t/h)
  processed_t/day = min(FFB intake, capacity_t/day)               (the rest waits on the ramp: reported, not produced)
  OER_eff         = OER + (baseline oil loss - oil loss)           (oil not lost is oil recovered, mass balance)
  CPO_t/day       = processed_t/day x OER_eff / 100
  value/day       = CPO_t x 1000 x price (THB/kg)
  energy cost/day = processed_t x kWh per t FFB x energy cost per kWh
Baseline = trailing 30 days of complete hours at the demo clock (ratio of sums). Illustrative, not a forecast.
"""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import (
    Alert,
    BusinessScenario,
    EnergyConsumption,
    Equipment,
    Facility,
    ProcessHourly,
    ScenarioRun,
    Sensor,
    SensorReading,
    TruckTrip,
)
from app.models.enums import ScenarioCode, StageCode
from app.schemas.common import Assumption, FactTag, Formula, KpiValue, Provenance, TrendDirection
from app.schemas.scenarios import (
    ExpectedEffect,
    ProductionWhatIfRequest,
    ProductionWhatIfResponse,
    SavedScenarioListResponse,
    SavedScenarioOut,
    SavedScenarioRequest,
    ScenarioCatalogResponse,
    ScenarioOut,
)
from app.services.audit import write_audit
from app.services.demo_context import DemoContext, provenance, require_session, session_filter
from app.services.kpi_common import price_map, price_on
from app.services.maintenance_health import load_assessments

FORMULA_VERSION = "production-whatif@1.0"
MAX_SAVED_SCENARIOS = 100
MAX_SAVED_JSON_BYTES = 64 * 1024
NAME_TH = {}


def _utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _prov(source: str, ctx: DemoContext, kind: str = "synthetic_actual", model_version: str | None = None) -> Provenance:
    return Provenance(**provenance(kind, source, ctx, model_version))


# ------------------------------------------------------------------ measured highlights
def _day_start(ctx: DemoContext, ts: datetime) -> datetime:
    tz = ZoneInfo(ctx.timezone)
    d = ts.astimezone(tz).date()
    return datetime.combine(d, datetime.min.time(), tzinfo=tz).astimezone(UTC)


def _hourly_window(db: Session, start: datetime, end: datetime) -> dict:
    """Ratio-of-sums over complete hours in [start, end): hours with ts + 1 h <= end."""
    rows = db.execute(
        select(ProcessHourly.ffb_processed_t, ProcessHourly.cpo_t, ProcessHourly.running_minutes, ProcessHourly.downtime_min, ProcessHourly.oil_loss_total_pct).where(
            ProcessHourly.ts >= start, ProcessHourly.ts <= end - timedelta(hours=1)
        )
    ).all()
    ffb = sum(r[0] or 0 for r in rows)
    cpo = sum(r[1] or 0 for r in rows)
    run_h = sum(r[2] or 0 for r in rows) / 60.0
    down_h = sum(r[3] or 0 for r in rows) / 60.0
    loss_w = sum((r[4] or 0) * (r[0] or 0) for r in rows if r[4] is not None)
    return {
        "hours": len(rows), "ffb_t": ffb, "cpo_t": cpo, "run_h": run_h, "down_h": down_h,
        "oer_pct": 100.0 * cpo / ffb if ffb > 0 else None, "throughput_tph": ffb / run_h if run_h > 0 else None,
        "oil_loss_pct": loss_w / ffb if ffb > 0 else None,
    }


def _energy_window(db: Session, start: datetime, end: datetime, ffb_t: float) -> dict:
    e, steam, cost = db.execute(
        select(func.coalesce(func.sum(EnergyConsumption.electricity_kwh), 0.0), func.coalesce(func.sum(EnergyConsumption.steam_t), 0.0), func.coalesce(func.sum(EnergyConsumption.cost_thb), 0.0)).where(
            EnergyConsumption.process_stage_id.is_(None), EnergyConsumption.ts >= start, EnergyConsumption.ts <= end - timedelta(hours=1)
        )
    ).one()
    return {"kwh_per_t": e / ffb_t if ffb_t > 0 else None, "steam_t_per_t": steam / ffb_t if ffb_t > 0 else None, "kwh": e, "cost_thb": cost}


def _truck_wait(db: Session, start: datetime, end: datetime) -> float | None:
    rows = db.execute(
        select(TruckTrip.arrival_ts, TruckTrip.weigh_in_ts).where(TruckTrip.arrival_ts >= start, TruckTrip.arrival_ts < end, TruckTrip.weigh_in_ts.is_not(None), TruckTrip.weigh_in_ts <= end)
    ).all()
    waits = [(_utc(w) - _utc(a)).total_seconds() / 60.0 for a, w in rows]
    return sum(waits) / len(waits) if waits else None


def _robust_daily_oer_sd(db: Session, ctx: DemoContext, focus_day: datetime) -> float | None:
    tz = ZoneInfo(ctx.timezone)
    start = max(focus_day - timedelta(days=28), ctx.window_start)
    rows = db.execute(select(ProcessHourly.ts, ProcessHourly.ffb_processed_t, ProcessHourly.cpo_t).where(ProcessHourly.ts >= start, ProcessHourly.ts < focus_day)).all()
    per: dict = {}
    for ts, f, c in rows:
        d = _utc(ts).astimezone(tz).date()
        a = per.setdefault(d, [0.0, 0.0])
        a[0] += f or 0
        a[1] += c or 0
    vals = [100.0 * c / f for f, c in per.values() if f >= 200]
    if len(vals) < 7:
        return None
    med = statistics.median(vals)
    mad = statistics.median(abs(v - med) for v in vals)
    return 1.4826 * mad or None


def _signif(delta: float | None, sd: float | None, unit: str) -> str | None:
    if delta is None or sd is None or sd <= 0:
        return None
    z = abs(delta) / sd
    if z < 1.0:
        return f"within normal day-to-day variation (robust sd {sd:.2f} {unit} of the previous 28 days)"
    return f"{z:.1f}x the normal day-to-day variation (robust sd {sd:.2f} {unit} of the previous 28 days)"


def _fx(module: str, metric: str, desc: str, focus, base, unit: str, entity: str | None = None, sig: str | None = None) -> ExpectedEffect:
    return ExpectedEffect(
        module=module, description=desc, entity_code=entity, metric=metric, focus_value=None if focus is None else round(focus, 3), baseline_value=None if base is None else round(base, 3),
        delta=None if focus is None or base is None else round(focus - base, 3), unit=unit, significance=sig, basis="measured: same hours of the day, focus vs baseline",
    )


def measured_effects(db: Session, ctx: DemoContext, run: ScenarioRun, eq: Equipment | None) -> list[ExpectedEffect]:
    focus, base = _utc(run.focus_ts), _utc(run.baseline_ts or run.focus_ts)
    out: list[ExpectedEffect] = []
    f0, b0 = _day_start(ctx, focus), _day_start(ctx, base)
    same = base == focus
    if same:  # reference day: compare with the previous 28 days over the same hours of the day
        n = 28
        fw = _hourly_window(db, f0, focus)
        accum = {"ffb_t": 0.0, "cpo_t": 0.0, "run_h": 0.0, "down_h": 0.0}
        e_kwh = steam = 0.0
        waits: list[float] = []
        for k in range(1, n + 1):
            d0 = f0 - timedelta(days=k)
            if d0 < ctx.window_start:
                break
            w = _hourly_window(db, d0, d0 + (focus - f0))
            for key in accum:
                accum[key] += w[key]
            ew = _energy_window(db, d0, d0 + (focus - f0), w["ffb_t"])
            e_kwh += ew["kwh"]
            steam += (ew["steam_t_per_t"] or 0) * w["ffb_t"]
            tw = _truck_wait(db, d0, d0 + (focus - f0))
            if tw is not None:
                waits.append(tw)
        bw = {**accum, "oer_pct": 100 * accum["cpo_t"] / accum["ffb_t"] if accum["ffb_t"] else None, "throughput_tph": accum["ffb_t"] / accum["run_h"] if accum["run_h"] else None}
        be = {"kwh_per_t": e_kwh / accum["ffb_t"] if accum["ffb_t"] else None, "steam_t_per_t": steam / accum["ffb_t"] if accum["ffb_t"] else None}
        bwait = sum(waits) / len(waits) if waits else None
        ref = "previous-28-day average"
    else:
        fw, bw = _hourly_window(db, f0, focus), _hourly_window(db, b0, b0 + (focus - f0))
        be = _energy_window(db, b0, b0 + (focus - f0), bw["ffb_t"])
        bwait = _truck_wait(db, b0, b0 + (focus - f0))
        ref = f"baseline day {base.astimezone(ZoneInfo(ctx.timezone)):%Y-%m-%d}"
    fe = _energy_window(db, f0, focus, fw["ffb_t"])
    sd = _robust_daily_oer_sd(db, ctx, f0)
    if fw["oer_pct"] is not None and bw["oer_pct"] is not None:
        d = fw["oer_pct"] - bw["oer_pct"]
        out.append(_fx("production_kpi", "oer_pct", f"OER {fw['oer_pct']:.2f}% vs {bw['oer_pct']:.2f}% ({ref}): {d:+.2f} pp", fw["oer_pct"], bw["oer_pct"], "%", None, _signif(d, sd, "pp")))
    if fw["throughput_tph"] is not None and bw["throughput_tph"] is not None:
        out.append(_fx("production_kpi", "throughput_tph", f"Throughput while running {fw['throughput_tph']:.1f} vs {bw['throughput_tph']:.1f} t/h ({ref})", fw["throughput_tph"], bw["throughput_tph"], "t/h"))
    if fw["down_h"] or (bw["down_h"] and not same):
        out.append(_fx("production_kpi", "downtime_h", f"Mill downtime {fw['down_h']:.1f} h vs {bw['down_h']:.1f} h ({ref}); same hours of the day" if not same else f"Mill downtime {fw['down_h']:.1f} h on the day (28-day total {bw['down_h']:.1f} h)", fw["down_h"], bw["down_h"] if not same else None, "h"))
    if fe["kwh_per_t"] is not None and be["kwh_per_t"] is not None:
        out.append(_fx("energy", "kwh_per_t", f"Electricity {fe['kwh_per_t']:.2f} vs {be['kwh_per_t']:.2f} kWh/t FFB ({ref})", fe["kwh_per_t"], be["kwh_per_t"], "kWh/t"))
    if fe["steam_t_per_t"] is not None and be["steam_t_per_t"] is not None:
        out.append(_fx("energy", "steam_t_per_t", f"Steam {fe['steam_t_per_t']:.3f} vs {be['steam_t_per_t']:.3f} t/t FFB ({ref})", fe["steam_t_per_t"], be["steam_t_per_t"], "t/t"))
    fwait = _truck_wait(db, f0, focus)
    if fwait is not None and bwait is not None:
        out.append(_fx("logistics", "truck_wait_to_weigh_min", f"Mean wait-to-weigh {fwait:.1f} vs {bwait:.1f} min ({ref}); trucks weighed by the focus time", fwait, bwait, "min"))
    # equipment: key sensor, health state at focus vs baseline
    if eq is not None:
        sensors = list(db.execute(select(Sensor).where(Sensor.equipment_id == eq.id, (Sensor.warn_limit.is_not(None)) | (Sensor.crit_limit.is_not(None)))).scalars())
        best = None
        for s in sensors:
            def ext(a: datetime, b: datetime, s=s) -> float | None:
                fn = func.min if s.low_is_bad else func.max
                return db.execute(select(fn(SensorReading.value)).where(SensorReading.sensor_id == s.id, SensorReading.ts > a, SensorReading.ts <= b, SensorReading.quality == "good")).scalar_one_or_none()
            fx, bx = ext(f0, focus), ext(b0, b0 + (focus - f0)) if not same else None
            if fx is None:
                continue
            ref_v = s.warn_limit or s.crit_limit or 1.0
            score = abs((fx - (bx if bx is not None else (s.normal_max if not s.low_is_bad else s.normal_min) or 0)) / (abs(ref_v) or 1.0))
            if best is None or score > best[0]:
                best = (score, s, fx, bx)
        if best and best[3] is not None:
            _, s, fx, bx = best
            lab = "lowest" if s.low_is_bad else "peak"
            out.append(_fx("process_twin", f"{lab}_{s.code}", f"{eq.code} {s.name}: {lab} {fx:.2f} vs {bx:.2f} {s.unit} ({ref}); limits warn {s.warn_limit} / crit {s.crit_limit}", fx, bx, s.unit, eq.code))
        base_ctx = ctx.model_copy(update={"session_id": None})
        st = {}
        for label, ts in (("focus", focus), ("baseline", base)):
            a = load_assessments(db, base_ctx.model_copy(update={"as_of": ts}), [eq.id], active_wo={}).get(eq.id)
            st[label] = a.state.value if a else "unknown"
        out.append(
            ExpectedEffect(
                module="maintenance_alert", description=f"{eq.code} health state (shared definition): {st['focus']} at the focus time vs {st['baseline']} at the baseline time", entity_code=eq.code,
                metric="health_state", unit="state", basis="measured: kpi_health definition applied at focus_ts and baseline_ts",
            )
        )
    n_alerts = db.execute(select(func.count()).select_from(Alert).where(Alert.scenario_code == run.code, Alert.raised_at <= focus)).scalar_one()
    if n_alerts:
        from app.services.kpi_alerts import ml_views  # noqa: PLC0415 - lazy import (QA-16: severity as seen at the focus time)

        rows = db.execute(select(Alert).where(Alert.scenario_code == run.code, Alert.raised_at <= focus)).scalars().all()
        views = ml_views(db, focus, list(rows))
        sev = [views.get(r.id, (r.severity, r.title))[0] for r in rows]
        order = ["info", "low", "medium", "high", "critical"]
        out.append(
            ExpectedEffect(
                module="anomaly", description=f"{n_alerts} threshold alert(s) linked to this episode raised by the focus time (highest severity: {max(sev, key=order.index)})", entity_code=eq.code if eq else None,
                metric="alerts_raised", focus_value=float(n_alerts), unit="alerts", basis="measured: alerts with scenario_code raised_at <= focus_ts",
            )
        )
    return out


def _scenario_out(db: Session, ctx: DemoContext, run: ScenarioRun, eqs: dict[int, Equipment]) -> ScenarioOut:
    eq = eqs.get(run.primary_equipment_id) if run.primary_equipment_id else None
    tz = ZoneInfo(ctx.timezone)
    focus = _utc(run.focus_ts)
    available = focus <= ctx.as_of
    effects: list[ExpectedEffect] = []
    note = None
    if available:
        effects = measured_effects(db, ctx, run, eq)
    else:
        note = "The focus time is after the current demo clock, so no data is read for it. Activate the scenario (as_of = focus_ts) to see the measured effects."
    s0, e0 = _utc(run.start_ts).astimezone(tz), _utc(run.end_ts).astimezone(tz)
    desc = (
        f"Deterministic episode in the synthetic timeline, {s0:%Y-%m-%d %H:%M} to {e0:%Y-%m-%d %H:%M} ({ctx.timezone})"
        + (f"; primary entity {eq.code} ({eq.name})" if eq else "")
        + (f"; primary stage {run.primary_stage_code}" if run.primary_stage_code else "")
        + ". The effects listed are measured from the data, not taken from the scenario design."
    )
    return ScenarioOut(
        code=ScenarioCode(run.code), name_en=run.name_en, name_th=run.name_th, description=desc, start_ts=_utc(run.start_ts), end_ts=_utc(run.end_ts), focus_ts=focus,
        baseline_ts=_utc(run.baseline_ts) if run.baseline_ts else None, primary_stage_code=StageCode(run.primary_stage_code) if run.primary_stage_code else None,
        primary_equipment_code=eq.code if eq else None, expected_effects=effects, activate_as_of=focus, activate_query=f"as_of={focus.isoformat().replace('+00:00', 'Z')}&scenario_id={run.code}",
        highlights_available=available, highlights_note=note, window_local=f"{s0:%Y-%m-%d %H:%M} -> {e0:%Y-%m-%d %H:%M} ({ctx.timezone})",
    )


def catalog(db: Session, ctx: DemoContext) -> ScenarioCatalogResponse:
    runs = list(db.execute(select(ScenarioRun).order_by(ScenarioRun.start_ts)).scalars())
    eqs = {e.id: e for e in db.execute(select(Equipment)).scalars()}
    return ScenarioCatalogResponse(items=[_scenario_out(db, ctx, r, eqs) for r in runs])


def get_scenario(db: Session, ctx: DemoContext, code: ScenarioCode) -> ScenarioOut:
    run = db.execute(select(ScenarioRun).where(ScenarioRun.code == code.value)).scalar_one_or_none()
    if run is None:
        not_found("scenario", code.value)
    eqs = {e.id: e for e in db.execute(select(Equipment)).scalars()}
    return _scenario_out(db, ctx, run, eqs)


# ------------------------------------------------------------------ production what-if
def _baseline(db: Session, ctx: DemoContext) -> dict:
    cutoff = ctx.as_of
    start = max(ctx.window_start, cutoff - timedelta(days=30))
    w = _hourly_window(db, start, cutoff)
    if w["hours"] < 24 or not w["ffb_t"]:
        raise ApiError(422, "insufficient_data", "Fewer than 24 complete mill hours before the demo clock: cannot derive baseline values. Move the clock forward.", {"hours": w["hours"]})
    days = w["hours"] / 24.0
    e = _energy_window(db, start, cutoff, w["ffb_t"])
    elec, cost = db.execute(
        select(func.coalesce(func.sum(EnergyConsumption.electricity_kwh), 0.0), func.coalesce(func.sum(EnergyConsumption.cost_thb), 0.0)).where(
            EnergyConsumption.process_stage_id.is_(None), EnergyConsumption.ts >= start, EnergyConsumption.ts <= cutoff - timedelta(hours=1)
        )
    ).one()
    price = price_on(price_map(db, "cpo", ctx.business_date), ctx.business_date)
    cap = db.execute(select(Facility.capacity_tph).limit(1)).scalar_one_or_none() or 60.0
    sched = (w["run_h"] + w["down_h"]) / days
    return {
        "days": days, "ffb_per_day": w["ffb_t"] / days, "scheduled_h": sched, "availability_pct": 100.0 * w["run_h"] / (w["run_h"] + w["down_h"]) if (w["run_h"] + w["down_h"]) else 100.0,
        "throughput_tph": w["throughput_tph"], "oer_pct": w["oer_pct"], "oil_loss_pct": w["oil_loss_pct"] or 1.0, "kwh_per_t": e["kwh_per_t"] or 0.0,
        "energy_cost_per_kwh": cost / elec if elec else 1.0, "price_thb_kg": price, "capacity_tph": cap,
    }


def _model(*, intake: float, hours: float, availability: float, cap_tph: float, oer: float, loss: float, base_loss: float, price: float, kwh_t: float, e_cost: float, days: int) -> dict:
    run_h = hours * availability / 100.0
    cap_t = run_h * cap_tph
    processed = min(intake, cap_t)
    oer_eff = oer + (base_loss - loss)
    cpo = processed * oer_eff / 100.0
    return {
        "running_h": run_h, "capacity_t": cap_t, "processed_t": processed, "unprocessed_t": intake - processed, "oer_eff": oer_eff, "cpo_t_day": cpo, "value_day": cpo * 1000 * price,
        "energy_day": processed * kwh_t * e_cost, "oil_loss_t_day": processed * loss / 100.0, "period": {
            "ffb_processed_t": processed * days, "cpo_t": cpo * days, "revenue_thb": cpo * 1000 * price * days, "energy_cost_thb": processed * kwh_t * e_cost * days,
            "oil_loss_t": processed * loss / 100.0 * days, "unprocessed_ffb_t": (intake - processed) * days,
        },
    }


def production_what_if(db: Session, ctx: DemoContext, body: ProductionWhatIfRequest) -> ProductionWhatIfResponse:
    b = _baseline(db, ctx)
    if b["price_thb_kg"] is None:
        raise ApiError(422, "insufficient_data", "No CPO price before the demo clock; provide cpo_price_thb_per_kg.")
    inp = {
        "ffb_intake_t_per_day": body.ffb_intake_t_per_day if body.ffb_intake_t_per_day is not None else b["ffb_per_day"],
        "oer_pct": body.oer_pct if body.oer_pct is not None else b["oer_pct"],
        "availability_pct": body.availability_pct if body.availability_pct is not None else b["availability_pct"],
        "processing_hours_per_day": body.processing_hours_per_day if body.processing_hours_per_day is not None else b["scheduled_h"],
        "energy_cost_thb_per_kwh": body.energy_cost_thb_per_kwh if body.energy_cost_thb_per_kwh is not None else b["energy_cost_per_kwh"],
        "oil_loss_pct": body.oil_loss_pct if body.oil_loss_pct is not None else b["oil_loss_pct"],
        "cpo_price_thb_per_kg": body.cpo_price_thb_per_kg if body.cpo_price_thb_per_kg is not None else b["price_thb_kg"],
    }
    days = body.days
    common = {"cap_tph": b["capacity_tph"], "base_loss": b["oil_loss_pct"], "kwh_t": b["kwh_per_t"], "days": days}
    base = _model(intake=b["ffb_per_day"], hours=b["scheduled_h"], availability=b["availability_pct"], oer=b["oer_pct"], loss=b["oil_loss_pct"], price=b["price_thb_kg"], e_cost=b["energy_cost_per_kwh"], **common)
    sc = _model(intake=inp["ffb_intake_t_per_day"], hours=inp["processing_hours_per_day"], availability=inp["availability_pct"], oer=inp["oer_pct"], loss=inp["oil_loss_pct"], price=inp["cpo_price_thb_per_kg"], e_cost=inp["energy_cost_thb_per_kwh"], **common)
    pb, ps = base["period"], sc["period"]
    kb = _prov(f"process_hourly / energy_consumption / prices, trailing {b['days']:.0f} days (ratio of sums)", ctx)
    kw = _prov("production what-if formulas (echoed)", ctx, "what_if", FORMULA_VERSION)

    def kpi(key, label, unit, vb, vs, good=TrendDirection.up):
        return (
            KpiValue(key=key, label=label, value=round(vb, 3), unit=unit, good_direction=good, provenance=kb),
            KpiValue(key=key, label=label, value=round(vs, 3), unit=unit, good_direction=good, previous=round(vb, 3), delta=round(vs - vb, 3), delta_pct=round(100 * (vs - vb) / vb, 3) if vb else None, provenance=kw),
            KpiValue(key=key, label=label, value=round(vs - vb, 3), unit=unit, good_direction=good, previous=round(vb, 3), delta=round(vs - vb, 3), delta_pct=round(100 * (vs - vb) / vb, 3) if vb else None, provenance=kw),
        )

    rows = [
        kpi("ffb_processed_t", f"FFB processed ({days} d)", "t", pb["ffb_processed_t"], ps["ffb_processed_t"]),
        kpi("oer_pct", "Effective OER", "%", base["oer_eff"], sc["oer_eff"]),
        kpi("cpo_t", f"CPO produced ({days} d)", "t", pb["cpo_t"], ps["cpo_t"]),
        kpi("availability_pct", "Availability", "%", b["availability_pct"], inp["availability_pct"]),
        kpi("running_hours_per_day", "Running hours per day", "h", base["running_h"], sc["running_h"]),
        kpi("cpo_revenue_thb", f"CPO value at illustrative price ({days} d)", "THB", pb["revenue_thb"], ps["revenue_thb"]),
        kpi("energy_cost_thb", f"Energy cost ({days} d)", "THB", pb["energy_cost_thb"], ps["energy_cost_thb"], TrendDirection.down),
        kpi("value_less_energy_thb", f"CPO value less energy cost ({days} d)", "THB", pb["revenue_thb"] - pb["energy_cost_thb"], ps["revenue_thb"] - ps["energy_cost_thb"]),
        kpi("oil_loss_t", f"Oil lost in residues ({days} d)", "t", pb["oil_loss_t"], ps["oil_loss_t"], TrendDirection.down),
        kpi("unprocessed_ffb_t", f"FFB waiting (intake above capacity, {days} d)", "t", pb["unprocessed_ffb_t"], ps["unprocessed_ffb_t"], TrendDirection.down),
    ]
    r = lambda x, n=3: round(x, n)  # noqa: E731
    F = Formula
    formulas = [
        F(key="running_hours", label="Running hours per day", expression="running_h = processing_hours x availability / 100", inputs={"processing_hours": r(inp["processing_hours_per_day"]), "availability_pct": r(inp["availability_pct"])}, result=r(sc["running_h"]), unit="h/day"),
        F(key="capacity_t", label="Processing capacity per day", expression="capacity_t = running_h x rated_capacity_tph", inputs={"running_h": r(sc["running_h"]), "rated_capacity_tph": b["capacity_tph"]}, result=r(sc["capacity_t"], 1), unit="t FFB/day"),
        F(key="processed_t", label="FFB processed per day", expression="processed_t = min(ffb_intake, capacity_t)", inputs={"ffb_intake_t_per_day": r(inp["ffb_intake_t_per_day"], 1), "capacity_t": r(sc["capacity_t"], 1)}, result=r(sc["processed_t"], 1), unit="t FFB/day"),
        F(key="oer_effective", label="Effective OER", expression="OER_eff = OER + (baseline_oil_loss - oil_loss)", inputs={"oer_pct": r(inp["oer_pct"], 3), "baseline_oil_loss_pct": r(b["oil_loss_pct"]), "oil_loss_pct": r(inp["oil_loss_pct"])}, result=r(sc["oer_eff"]), unit="%"),
        F(key="cpo_t_day", label="CPO per day", expression="cpo_t = processed_t x OER_eff / 100", inputs={"processed_t": r(sc["processed_t"], 1), "oer_eff_pct": r(sc["oer_eff"])}, result=r(sc["cpo_t_day"]), unit="t CPO/day"),
        F(key="cpo_t_period", label=f"CPO over {days} days", expression="cpo_t_period = cpo_t_day x days", inputs={"cpo_t_day": r(sc["cpo_t_day"]), "days": days}, result=r(ps["cpo_t"]), unit="t CPO"),
        F(key="delta_cpo_t", label="CPO change vs baseline", expression="delta_cpo_t = scenario_cpo_t - baseline_cpo_t", inputs={"scenario_cpo_t": r(ps["cpo_t"]), "baseline_cpo_t": r(pb["cpo_t"])}, result=r(ps["cpo_t"] - pb["cpo_t"]), unit="t CPO"),
        F(key="revenue_period", label=f"CPO value over {days} days (illustrative)", expression="revenue = cpo_t x 1000 x price_thb_per_kg", inputs={"cpo_t": r(ps["cpo_t"]), "price_thb_per_kg": r(inp["cpo_price_thb_per_kg"])}, result=r(ps["revenue_thb"], 0), unit="THB"),
        F(key="energy_cost_period", label=f"Energy cost over {days} days", expression="energy_cost = processed_t x kWh_per_t x energy_cost_per_kwh x days", inputs={"processed_t": r(sc["processed_t"], 1), "kwh_per_t": r(b["kwh_per_t"]), "energy_cost_thb_per_kwh": r(inp["energy_cost_thb_per_kwh"]), "days": days}, result=r(ps["energy_cost_thb"], 0), unit="THB"),
        F(key="calculation_example", label="Calculation example (not a forecast): 1,000 t FFB x +0.5 pp OER", expression="delta_cpo_t = ffb_t x delta_oer_pp / 100", inputs={"ffb_t": 1000.0, "delta_oer_pp": 0.5}, result=5.0, unit="t CPO"),
    ]
    A = Assumption
    assumptions = [
        A(key="baseline_window", label="Baseline = trailing 30 days of complete hours at the demo clock", value=f"{b['days']:.1f} days", tag=FactTag.synthetic_demonstration_data, source="process_hourly (ratio of sums)", editable=False),
        A(key="rated_capacity_tph", label="Rated mill capacity", value=b["capacity_tph"], unit="t FFB/h", tag=FactTag.synthetic_demonstration_data, source="facilities.capacity_tph", editable=False),
        A(key="supply", label="FFB intake is available and the ramp can hold what exceeds capacity", value="yes", tag=FactTag.engineering_assumption, source="intake above capacity is reported as 'FFB waiting', not produced"),
        A(key="oil_loss_to_oer", label="One percentage point less oil lost = one percentage point more OER", value=1.0, unit="pp/pp", tag=FactTag.engineering_assumption, source="mass balance: oil not lost to EFB/fibre/sludge is recovered as CPO"),
        A(key="energy_per_tonne", label="Electricity intensity held at baseline", value=round(b["kwh_per_t"], 3), unit="kWh/t FFB", tag=FactTag.synthetic_demonstration_data, source="energy_consumption (plant rows), ratio of sums"),
        A(key="energy_cost", label="Blended energy cost per kWh consumed", value=round(inp["energy_cost_thb_per_kwh"], 3), unit="THB/kWh", tag=FactTag.synthetic_demonstration_data, source="energy_consumption.cost_thb / electricity_kwh" if body.energy_cost_thb_per_kwh is None else "user input"),
        A(key="cpo_price", label="CPO price", value=round(inp["cpo_price_thb_per_kg"], 3), unit="THB/kg", tag=FactTag.synthetic_demonstration_data, source="prices.cpo (illustrative synthetic series, not market data)" if body.cpo_price_thb_per_kg is None else "user input"),
    ]
    warnings = []
    if sc["unprocessed_t"] > 0.5:
        warnings.append(f"The intake ({inp['ffb_intake_t_per_day']:.0f} t/day) exceeds the processing capacity ({sc['capacity_t']:.0f} t/day): {sc['unprocessed_t']:.0f} t/day would wait on the ramp (longer wait raises FFA - not modelled).")
    if inp["oer_pct"] + (b["oil_loss_pct"] - inp["oil_loss_pct"]) > 25.0:
        warnings.append("Effective OER above 25% is outside any plausible palm-mill range - check the inputs.")
    return ProductionWhatIfResponse(
        baseline=[x[0] for x in rows], scenario=[x[1] for x in rows], delta=[x[2] for x in rows], formulas=formulas, assumptions=assumptions, provenance=kw,
        baseline_inputs={k: round(v, 4) for k, v in {"ffb_intake_t_per_day": b["ffb_per_day"], "oer_pct": b["oer_pct"], "availability_pct": b["availability_pct"], "processing_hours_per_day": b["scheduled_h"], "energy_cost_thb_per_kwh": b["energy_cost_per_kwh"], "oil_loss_pct": b["oil_loss_pct"], "cpo_price_thb_per_kg": b["price_thb_kg"]}.items()},
        inputs_used={k: round(v, 4) for k, v in inp.items()}, warnings=warnings, horizon_days=days,
    )


# ------------------------------------------------------------------ saved scenarios (session-scoped)
def _saved_out(r: BusinessScenario) -> SavedScenarioOut:
    return SavedScenarioOut(id=r.id, kind=r.kind, name=r.name, inputs=json.loads(r.inputs_json), outputs=json.loads(r.outputs_json), created_at=_utc(r.created_at), demo_as_of=_utc(r.demo_as_of) if r.demo_as_of else None)


def list_saved(db: Session, ctx: DemoContext, kind: str | None) -> SavedScenarioListResponse:
    q = select(BusinessScenario).where(session_filter(BusinessScenario.session_id, ctx)).order_by(BusinessScenario.id.desc())
    if kind:
        q = q.where(BusinessScenario.kind == kind)
    return SavedScenarioListResponse(items=[_saved_out(r) for r in db.execute(q).scalars()])


def save_scenario(db: Session, ctx: DemoContext, body: SavedScenarioRequest) -> SavedScenarioOut:
    sid = require_session(ctx)
    inputs_json = json.dumps(body.inputs, default=str, sort_keys=True)
    outputs_json = json.dumps(body.outputs, default=str, sort_keys=True)
    if len(inputs_json.encode()) > MAX_SAVED_JSON_BYTES or len(outputs_json.encode()) > MAX_SAVED_JSON_BYTES:
        raise ApiError(413, "payload_too_large", f"inputs/outputs may be at most {MAX_SAVED_JSON_BYTES // 1024} KiB each", {"limit_bytes": MAX_SAVED_JSON_BYTES})
    n = db.execute(select(func.count()).select_from(BusinessScenario).where(BusinessScenario.session_id == sid)).scalar_one()
    if n >= MAX_SAVED_SCENARIOS:
        raise ApiError(409, "session_quota_exceeded", f"This demo session already holds {n} saved scenarios (limit {MAX_SAVED_SCENARIOS}). Reset the session to continue.", {"limit": MAX_SAVED_SCENARIOS})
    row = BusinessScenario(
        session_id=sid, kind=body.kind, name=body.name.strip(), role=ctx.role.value, inputs_json=inputs_json, outputs_json=outputs_json, formula_version=FORMULA_VERSION,
        demo_as_of=ctx.as_of, data_kind="what_if",
    )
    db.add(row)
    db.flush()
    write_audit(db, ctx, "scenario.save", "business_scenario", row.id, None, {"kind": row.kind, "name": row.name})
    db.commit()
    return _saved_out(row)
