"""ROI & Value Simulator (DML-085..090). Owner: backend-b.

ILLUSTRATIVE ONLY: "Illustrative business scenario based on adjustable assumptions, not verified financial results of any
company." Every formula is echoed per case and every assumption is tagged with the SPEC fact taxonomy.

Annual model for one case (m_* = case multipliers, see CASE_MULTIPLIERS):
  FFB_base           = daily_ffb_t x operating_days                                   [separate base 1: baseline FFB]
  dOER_pp            = (target_oer - current_oer) x m_oer
  CPO_oer            = FFB_base x dOER_pp / 100
  recovered_h        = min(downtime_h_month x 12 x min(100, reduction% x m_dt) / 100,
                           (24 - daily_ffb/capacity) x operating_days)                  (cannot run more than 24 h/day)
  FFB_recovered      = recovered_h x processing_capacity_tph                          [separate base 2: extra FFB, only
  CPO_downtime       = FFB_recovered x current_oer / 100                               exists because the mill runs more hours]
  additional_cpo_t   = CPO_oer + CPO_downtime
  gross_value        = additional_cpo_t x 1000 x price_thb_per_kg
  cost_avoidance     = (energy_cost + maintenance_expense) x min(100, eff% x m_eff) / 100
  net_benefit_year1  = gross_value + cost_avoidance - implementation x m_impl - recurring x m_rec
  payback_months     = implementation x m_impl / ((gross_value + cost_avoidance - recurring x m_rec) / 12)
No double counting: the OER uplift is applied only to the baseline FFB; the recovered-hours FFB is valued at the CURRENT
OER (no uplift on it); the two bases are disjoint, so their CPO adds without overlap. Not discounted, no ramp-up, no tax.
"""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, bad_request
from app.models import Facility
from app.schemas.common import Assumption, Disclaimer, ExportFormat, FactTag, Formula, Provenance, ReportDocument
from app.schemas.roi import (
    ROI_DISCLAIMER,
    PrintableDocument,
    RoiCase,
    RoiCaseResult,
    RoiDefaultsResponse,
    RoiExportRequest,
    RoiInputs,
    RoiResponse,
    SensitivityBar,
    SensitivityRequest,
    SensitivityResponse,
)
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_common import fact_tag, param, param_meta

ROI_VERSION = "roi-formulas@1.0"
ROI_DISCLAIMER_TH = "สถานการณ์ทางธุรกิจเพื่อการอธิบาย อิงสมมติฐานที่ปรับได้ ไม่ใช่ผลประกอบการที่ได้รับการตรวจสอบของบริษัทใด ๆ"
DISCLAIMER = Disclaimer(key="roi_illustrative", text_en=ROI_DISCLAIMER, text_th=ROI_DISCLAIMER_TH)

# Case multipliers (Engineering Assumptions, adjustable): share of the entered improvement that is realised, and cost factors.
CASE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "baseline": {"oer_gap_realisation": 0.0, "downtime_reduction_realisation": 0.0, "efficiency_realisation": 0.0, "implementation_cost_factor": 0.0, "recurring_cost_factor": 0.0},
    "conservative": {"oer_gap_realisation": 0.5, "downtime_reduction_realisation": 0.5, "efficiency_realisation": 0.5, "implementation_cost_factor": 1.15, "recurring_cost_factor": 1.0},
    "expected": {"oer_gap_realisation": 1.0, "downtime_reduction_realisation": 1.0, "efficiency_realisation": 1.0, "implementation_cost_factor": 1.0, "recurring_cost_factor": 1.0},
    "optimistic": {"oer_gap_realisation": 1.25, "downtime_reduction_realisation": 1.25, "efficiency_realisation": 1.25, "implementation_cost_factor": 0.95, "recurring_cost_factor": 1.0},
}
CASE_ORDER = [RoiCase.baseline, RoiCase.conservative, RoiCase.expected, RoiCase.optimistic]

# bounds used to clamp sensitivity swings to valid inputs
BOUNDS: dict[str, tuple[float, float]] = {
    "daily_ffb_t": (1e-6, 10000), "operating_days": (1, 366), "current_oer_pct": (1e-6, 35), "target_oer_pct": (1e-6, 35), "cpo_price_thb_per_kg": (1e-6, 200),
    "downtime_h_per_month": (0, 744), "processing_capacity_tph": (1e-6, 200), "energy_cost_thb_per_year": (0, 1e15), "maintenance_expense_thb_per_year": (0, 1e15),
    "efficiency_improvement_pct": (0, 100), "downtime_reduction_pct": (0, 100), "implementation_cost_thb": (0, 1e15), "recurring_cost_thb_per_year": (0, 1e15),
}
INT_FIELDS = {"operating_days"}


def compute_case(inp: RoiInputs, case: RoiCase) -> dict:
    """Pure function (unit-tested): all numbers of one case plus the separate FFB bases."""
    m = CASE_MULTIPLIERS[case.value]
    ffb_base = inp.daily_ffb_t * inp.operating_days
    d_oer = (inp.target_oer_pct - inp.current_oer_pct) * m["oer_gap_realisation"]
    cpo_oer = ffb_base * d_oer / 100.0
    reduction = min(100.0, inp.downtime_reduction_pct * m["downtime_reduction_realisation"])
    downtime_year = inp.downtime_h_per_month * 12.0
    recovered_raw = downtime_year * reduction / 100.0
    base_hours_day = inp.daily_ffb_t / inp.processing_capacity_tph
    headroom = max(0.0, 24.0 - base_hours_day) * inp.operating_days
    recovered_h = min(recovered_raw, headroom)
    ffb_recovered = recovered_h * inp.processing_capacity_tph
    cpo_dt = ffb_recovered * inp.current_oer_pct / 100.0
    additional = cpo_oer + cpo_dt
    gross = additional * 1000.0 * inp.cpo_price_thb_per_kg
    eff = min(100.0, inp.efficiency_improvement_pct * m["efficiency_realisation"])
    avoid = (inp.energy_cost_thb_per_year + inp.maintenance_expense_thb_per_year) * eff / 100.0
    impl = inp.implementation_cost_thb * m["implementation_cost_factor"]
    rec = inp.recurring_cost_thb_per_year * m["recurring_cost_factor"]
    net = gross + avoid - impl - rec
    run_rate = gross + avoid - rec
    payback = None
    if case != RoiCase.baseline and run_rate > 0:
        payback = 0.0 if impl == 0 else impl / (run_rate / 12.0)
    return {
        "case": case, "multipliers": m, "ffb_base_t": ffb_base, "delta_oer_pp": d_oer, "cpo_oer_t": cpo_oer, "downtime_year_h": downtime_year, "reduction_pct": reduction,
        "recovered_h_raw": recovered_raw, "headroom_h": headroom, "recovered_h": recovered_h, "capped": recovered_raw > headroom, "ffb_recovered_t": ffb_recovered,
        "cpo_downtime_t": cpo_dt, "additional_cpo_t": additional, "gross_value_thb": gross, "efficiency_pct": eff, "cost_avoidance_thb": avoid,
        "implementation_thb": impl, "recurring_thb": rec, "net_benefit_year1_thb": net, "run_rate_thb": run_rate, "payback_months": payback,
    }


def _round(x: float, n: int = 2) -> float:
    return round(x, n)


def _formulas(inp: RoiInputs, c: dict) -> list[Formula]:
    k = c["case"].value
    r = _round
    F = Formula
    m = c["multipliers"]
    return [
        F(key=f"{k}.ffb_base_t", label=f"[{k}] Baseline FFB per year", expression="ffb_base_t = daily_ffb_t x operating_days", inputs={"daily_ffb_t": inp.daily_ffb_t, "operating_days": inp.operating_days}, result=r(c["ffb_base_t"], 1), unit="t FFB/yr"),
        F(key=f"{k}.delta_oer_pp", label=f"[{k}] OER improvement realised", expression="delta_oer_pp = (target_oer - current_oer) x oer_gap_realisation", inputs={"target_oer_pct": inp.target_oer_pct, "current_oer_pct": inp.current_oer_pct, "oer_gap_realisation": m["oer_gap_realisation"]}, result=r(c["delta_oer_pp"], 4), unit="pp"),
        F(key=f"{k}.cpo_oer_t", label=f"[{k}] Additional CPO from OER uplift (base 1: baseline FFB)", expression="cpo_oer_t = ffb_base_t x delta_oer_pp / 100", inputs={"ffb_base_t": r(c["ffb_base_t"], 1), "delta_oer_pp": r(c["delta_oer_pp"], 4)}, result=r(c["cpo_oer_t"], 2), unit="t CPO/yr"),
        F(key=f"{k}.recovered_h", label=f"[{k}] Downtime hours recovered (capped by free hours in the day)", expression="recovered_h = min(downtime_h_month x 12 x reduction% / 100, (24 - daily_ffb/capacity) x operating_days)", inputs={"downtime_h_per_year": c["downtime_year_h"], "reduction_pct": r(c["reduction_pct"], 3), "headroom_h_per_year": r(c["headroom_h"], 1), "capped": str(c["capped"])}, result=r(c["recovered_h"], 1), unit="h/yr"),
        F(key=f"{k}.ffb_recovered_t", label=f"[{k}] FFB processed in recovered hours (base 2: extra FFB)", expression="ffb_recovered_t = recovered_h x processing_capacity_tph", inputs={"recovered_h": r(c["recovered_h"], 1), "processing_capacity_tph": inp.processing_capacity_tph}, result=r(c["ffb_recovered_t"], 1), unit="t FFB/yr"),
        F(key=f"{k}.cpo_downtime_t", label=f"[{k}] Additional CPO from downtime recovery (valued at CURRENT OER)", expression="cpo_downtime_t = ffb_recovered_t x current_oer / 100", inputs={"ffb_recovered_t": r(c["ffb_recovered_t"], 1), "current_oer_pct": inp.current_oer_pct}, result=r(c["cpo_downtime_t"], 2), unit="t CPO/yr"),
        F(key=f"{k}.additional_cpo_t", label=f"[{k}] Total additional CPO (bases are disjoint)", expression="additional_cpo_t = cpo_oer_t + cpo_downtime_t", inputs={"cpo_oer_t": r(c["cpo_oer_t"], 2), "cpo_downtime_t": r(c["cpo_downtime_t"], 2)}, result=r(c["additional_cpo_t"], 2), unit="t CPO/yr"),
        F(key=f"{k}.gross_value_thb", label=f"[{k}] Gross value uplift", expression="gross_value = additional_cpo_t x 1000 x cpo_price_thb_per_kg", inputs={"additional_cpo_t": r(c["additional_cpo_t"], 2), "cpo_price_thb_per_kg": inp.cpo_price_thb_per_kg}, result=r(c["gross_value_thb"], 0), unit="THB/yr"),
        F(key=f"{k}.cost_avoidance_thb", label=f"[{k}] Estimated cost avoidance (energy + maintenance)", expression="cost_avoidance = (energy_cost + maintenance_expense) x efficiency% / 100", inputs={"energy_cost_thb_per_year": inp.energy_cost_thb_per_year, "maintenance_expense_thb_per_year": inp.maintenance_expense_thb_per_year, "efficiency_pct": r(c["efficiency_pct"], 3)}, result=r(c["cost_avoidance_thb"], 0), unit="THB/yr"),
        F(key=f"{k}.net_benefit_year1_thb", label=f"[{k}] Scenario net benefit, year 1", expression="net = gross_value + cost_avoidance - implementation_cost - recurring_cost", inputs={"gross_value_thb": r(c["gross_value_thb"], 0), "cost_avoidance_thb": r(c["cost_avoidance_thb"], 0), "implementation_cost_thb": r(c["implementation_thb"], 0), "recurring_cost_thb": r(c["recurring_thb"], 0)}, result=r(c["net_benefit_year1_thb"], 0), unit="THB"),
        F(key=f"{k}.payback_months", label=f"[{k}] Payback", expression="payback_months = implementation_cost / ((gross_value + cost_avoidance - recurring_cost) / 12); none if the run-rate is not positive", inputs={"implementation_cost_thb": r(c["implementation_thb"], 0), "annual_run_rate_thb": r(c["run_rate_thb"], 0)}, result=None if c["payback_months"] is None else r(c["payback_months"], 1), unit="months"),
    ]


def _assumptions(inp: RoiInputs) -> list[Assumption]:
    A = Assumption
    out = [
        A(key=f"case_multipliers.{case}.{key}", label=f"{case.capitalize()}: {key.replace('_', ' ')}", value=val, tag=FactTag.engineering_assumption, source="services/roi.py CASE_MULTIPLIERS (adjustable)")
        for case, mm in CASE_MULTIPLIERS.items() for key, val in mm.items()
    ]
    out += [
        A(key="separate_bases", label="OER uplift applies to baseline FFB only; recovered-hour FFB is valued at the current OER", value="yes", tag=FactTag.engineering_assumption, source="no double counting (KPI_DEFINITIONS 4.10)", editable=False),
        A(key="supply_available", label="Extra FFB is available for the recovered hours", value="yes", tag=FactTag.engineering_assumption, source="if the mill is supply-constrained the downtime-recovery value is an upper bound"),
        A(key="max_24h", label="Recovered hours cannot exceed the free hours in a day (24 - daily_ffb/capacity)", value="yes", tag=FactTag.engineering_assumption, source="physical limit", editable=False),
        A(key="price_constant", label="CPO price is constant over the year", value=inp.cpo_price_thb_per_kg, unit="THB/kg", tag=FactTag.engineering_assumption, source="user input; see the sensitivity tornado for price risk"),
        A(key="no_discounting", label="Year-1 figures are undiscounted, without ramp-up, tax or inflation", value="yes", tag=FactTag.engineering_assumption, source="simplification", editable=False),
        A(key="efficiency_base", label="Efficiency improvement applies to energy + maintenance cost only (not to FFB or CPO)", value=inp.efficiency_improvement_pct, unit="%", tag=FactTag.engineering_assumption, source="schema definition of efficiency_improvement_pct"),
    ]
    return out


def _prov(ctx: DemoContext) -> Provenance:
    return Provenance(**provenance("what_if", "ROI formulas over user-adjustable inputs (illustrative)", ctx, ROI_VERSION))


def calculate(ctx: DemoContext, inp: RoiInputs) -> RoiResponse:
    results, formulas = [], []
    for case in CASE_ORDER:
        c = compute_case(inp, case)
        results.append(
            RoiCaseResult(
                case=case, additional_cpo_t=_round(c["additional_cpo_t"], 2), gross_value_uplift_thb=_round(c["gross_value_thb"], 0), cost_avoidance_thb=_round(c["cost_avoidance_thb"], 0),
                implementation_cost_thb=_round(c["implementation_thb"], 0), annual_recurring_cost_thb=_round(c["recurring_thb"], 0), net_benefit_year1_thb=_round(c["net_benefit_year1_thb"], 0),
                payback_months=None if c["payback_months"] is None else _round(c["payback_months"], 1), multipliers=c["multipliers"],
            )
        )
        formulas += _formulas(inp, c)
    return RoiResponse(inputs=inp, cases=results, formulas=formulas, assumptions=_assumptions(inp), disclaimer=DISCLAIMER, provenance=_prov(ctx))


# ------------------------------------------------------------------ defaults from the synthetic baseline
# Illustrative defaults (Engineering Assumptions). Kept deliberately modest: a first draft of 0.5 pp OER gain,
# 15 % downtime cut and a 6 M THB cost produced a 1-month payback, which is arithmetically right but not credible.
DEFAULT_OER_GAIN_PP = 0.10
DEFAULT_EFFICIENCY_PCT = 3.0
DEFAULT_DOWNTIME_REDUCTION_PCT = 5.0
DEFAULT_IMPLEMENTATION_THB = 12_000_000.0
DEFAULT_RECURRING_THB = 3_600_000.0


def defaults(db: Session, ctx: DemoContext) -> RoiDefaultsResponse:
    from app.services.scenarios import _baseline  # noqa: PLC0415 - shared trailing-30-day baseline

    b = _baseline(db, ctx)
    cap = db.execute(select(Facility.capacity_tph).limit(1)).scalar_one_or_none() or 60.0
    days = param("operating_days_per_year")
    daily = b["ffb_per_day"]
    energy_day = daily * b["kwh_per_t"] * b["energy_cost_per_kwh"]
    maint_per_t = param("maintenance_cost_thb_per_t_ffb")
    down_month = b["scheduled_h"] * (1 - b["availability_pct"] / 100.0) * 30.0
    inputs = RoiInputs(
        daily_ffb_t=round(daily, 1), operating_days=int(days), current_oer_pct=round(b["oer_pct"], 2), target_oer_pct=round(b["oer_pct"] + DEFAULT_OER_GAIN_PP, 2), cpo_price_thb_per_kg=round(b["price_thb_kg"], 2),
        downtime_h_per_month=round(down_month, 1), processing_capacity_tph=cap, energy_cost_thb_per_year=round(energy_day * days, 0), maintenance_expense_thb_per_year=round(maint_per_t * daily * days, 0),
        efficiency_improvement_pct=DEFAULT_EFFICIENCY_PCT, downtime_reduction_pct=DEFAULT_DOWNTIME_REDUCTION_PCT,
        implementation_cost_thb=DEFAULT_IMPLEMENTATION_THB, recurring_cost_thb_per_year=DEFAULT_RECURRING_THB,
    )
    A = Assumption
    syn = FactTag.synthetic_demonstration_data
    assumptions = [
        A(key="daily_ffb_t", label="Daily FFB throughput", value=inputs.daily_ffb_t, unit="t/day", tag=syn, source=f"process_hourly, trailing {b['days']:.0f} days to the demo clock (ratio of sums)"),
        A(key="operating_days", label="Operating days per year", value=inputs.operating_days, unit="days", tag=FactTag(fact_tag(param_meta("operating_days_per_year")["category"])), source="DOMAIN_PARAMETERS operating_days_per_year"),
        A(key="current_oer_pct", label="Current OER", value=inputs.current_oer_pct, unit="%", tag=syn, source="process_hourly, trailing 30 days (ratio of sums)"),
        A(key="target_oer_pct", label=f"Target OER (current + {DEFAULT_OER_GAIN_PP:g} pp)", value=inputs.target_oer_pct, unit="%", tag=FactTag.engineering_assumption, source="illustrative placeholder deliberately kept small (a software-only OER gain is hard to achieve); not a target set by any company"),
        A(key="cpo_price_thb_per_kg", label="CPO price", value=inputs.cpo_price_thb_per_kg, unit="THB/kg", tag=syn, source="prices.cpo at the demo clock (illustrative synthetic series, not market data)"),
        A(key="downtime_h_per_month", label="Downtime hours per month", value=inputs.downtime_h_per_month, unit="h", tag=syn, source="process_hourly downtime share x 30 days"),
        A(key="processing_capacity_tph", label="Processing capacity", value=cap, unit="t FFB/h", tag=syn, source="facilities.capacity_tph", editable=False),
        A(key="energy_cost_thb_per_year", label="Energy cost per year", value=inputs.energy_cost_thb_per_year, unit="THB", tag=syn, source="energy_consumption cost per tonne x daily FFB x operating days"),
        A(key="maintenance_expense_thb_per_year", label="Maintenance expense per year", value=inputs.maintenance_expense_thb_per_year, unit="THB", tag=FactTag(fact_tag(param_meta("maintenance_cost_thb_per_t_ffb")["category"])), source=f"DOMAIN_PARAMETERS maintenance_cost_thb_per_t_ffb ({maint_per_t:g} THB/t) x annual FFB"),
        A(key="efficiency_improvement_pct", label="Efficiency improvement (energy + maintenance)", value=DEFAULT_EFFICIENCY_PCT, unit="%", tag=FactTag.engineering_assumption, source="illustrative placeholder"),
        A(key="downtime_reduction_pct", label="Downtime reduction", value=DEFAULT_DOWNTIME_REDUCTION_PCT, unit="%", tag=FactTag.engineering_assumption, source="illustrative placeholder"),
        A(key="implementation_cost_thb", label="Implementation cost", value=DEFAULT_IMPLEMENTATION_THB, unit="THB", tag=FactTag.engineering_assumption, source="placeholder sized as a small multi-person-year programme incl. sensors/integration; replace with a real quote; not a company budget"),
        A(key="recurring_cost_thb_per_year", label="Recurring operating cost per year", value=DEFAULT_RECURRING_THB, unit="THB", tag=FactTag.engineering_assumption, source="placeholder (support, hosting, model upkeep); replace with a real quote; not a company budget"),
    ]
    return RoiDefaultsResponse(inputs=inputs, assumptions=assumptions, case_multipliers=CASE_MULTIPLIERS, disclaimer=DISCLAIMER)


# ------------------------------------------------------------------ sensitivity (tornado)
def _with(inp: RoiInputs, var: str, value: float) -> RoiInputs:
    lo, hi = BOUNDS[var]
    v = min(max(value, lo), hi)
    if var in INT_FIELDS:
        v = int(round(v))
    d = inp.model_dump()
    d[var] = v
    return RoiInputs(**d)


def _vary(inp: RoiInputs, var: str, frac: float) -> tuple[RoiInputs, float, str | None]:
    """Inputs with `var` moved by frac (e.g. -0.2). OER levels are NOT swung as levels (a +-20% move of 18.9% would be +-3.8 pp and
    swamp everything): target_oer_pct swings the IMPROVEMENT (target - current); current_oer_pct shifts current and target together."""
    if var == "target_oer_pct":
        gap = inp.target_oer_pct - inp.current_oer_pct
        new = inp.current_oer_pct + gap * (1 + frac)
        return _with(inp, var, new), new, "swing applied to the improvement (target - current), not to the OER level"
    if var == "current_oer_pct":
        shift = inp.current_oer_pct * frac
        d = inp.model_dump()
        d["current_oer_pct"] = min(max(inp.current_oer_pct + shift, BOUNDS[var][0]), BOUNDS[var][1])
        d["target_oer_pct"] = min(max(inp.target_oer_pct + shift, BOUNDS["target_oer_pct"][0]), BOUNDS["target_oer_pct"][1])
        return RoiInputs(**d), d["current_oer_pct"], "current and target OER shifted together (the improvement stays the same)"
    v = getattr(inp, var) * (1 + frac)
    out = _with(inp, var, v)
    return out, getattr(out, var), None


def sensitivity(ctx: DemoContext, body: SensitivityRequest) -> SensitivityResponse:
    unknown = [v for v in body.variables if v not in BOUNDS]
    if unknown:
        bad_request("unknown_variable", "Unknown sensitivity variable(s)", {"unknown": unknown, "allowed": sorted(BOUNDS)})
    base = compute_case(body.inputs, RoiCase.expected)["net_benefit_year1_thb"]
    bars = []
    s = body.swing_pct / 100.0
    for var in dict.fromkeys(body.variables):
        try:
            lo_in, lo_v, note = _vary(body.inputs, var, -s)
            hi_in, hi_v, _ = _vary(body.inputs, var, +s)
        except ValueError as exc:
            raise ApiError(422, "invalid_sensitivity_input", f"Swing produces an invalid value for {var}", {"variable": var}) from exc
        nl = compute_case(lo_in, RoiCase.expected)["net_benefit_year1_thb"]
        nh = compute_case(hi_in, RoiCase.expected)["net_benefit_year1_thb"]
        bars.append(SensitivityBar(variable=var, low_value=_round(lo_v, 4), high_value=_round(hi_v, 4), net_benefit_low_thb=_round(nl, 0), net_benefit_high_thb=_round(nh, 0), note=note))
    bars.sort(key=lambda b: -abs(b.net_benefit_high_thb - b.net_benefit_low_thb))
    return SensitivityResponse(base_net_benefit_thb=_round(base, 0), bars=bars, provenance=_prov(ctx))


# ------------------------------------------------------------------ export
def _thb(x: float | None) -> str:
    return "-" if x is None else f"{x:,.0f}"


def _csv(resp: RoiResponse) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["# " + ROI_DISCLAIMER])
    w.writerow(["# Independent concept demo on synthetic data. Not an official system of any company."])
    w.writerow(["section", "key", "label", "value", "unit"])
    for k, v in resp.inputs.model_dump().items():
        w.writerow(["input", k, k.replace("_", " "), v, ""])
    w.writerow([])
    w.writerow(["case", "additional_cpo_t", "gross_value_uplift_thb", "cost_avoidance_thb", "implementation_cost_thb", "annual_recurring_cost_thb", "net_benefit_year1_thb", "payback_months"])
    for c in resp.cases:
        w.writerow([c.case.value, c.additional_cpo_t, c.gross_value_uplift_thb, c.cost_avoidance_thb, c.implementation_cost_thb, c.annual_recurring_cost_thb, c.net_benefit_year1_thb, "" if c.payback_months is None else c.payback_months])
    w.writerow([])
    w.writerow(["section", "key", "label", "result", "unit", "expression"])
    for f in resp.formulas:
        w.writerow(["formula", f.key, f.label, "" if f.result is None else f.result, f.unit, f.expression])
    w.writerow([])
    w.writerow(["section", "key", "label", "value", "unit", "tag", "source"])
    for a in resp.assumptions:
        w.writerow(["assumption", a.key, a.label, a.value, a.unit or "", a.tag.value, a.source or ""])
    w.writerow([])
    w.writerow(["# " + resp.double_counting_note])
    w.writerow(["# " + ROI_DISCLAIMER])
    return buf.getvalue()


def _markdown(resp: RoiResponse) -> str:
    L = [f"# ROI & value scenario (illustrative)\n\n> **{ROI_DISCLAIMER}**\n", "Independent concept demo on synthetic data. Not an official system of any company.\n", "## Inputs\n", "| input | value |\n|---|---|"]
    L += [f"| {k} | {v:,} |" if isinstance(v, (int, float)) else f"| {k} | {v} |" for k, v in resp.inputs.model_dump().items()]
    L += ["\n## Cases (year 1, THB)\n", "| case | additional CPO (t) | gross value uplift | cost avoidance | implementation | recurring | net benefit | payback (months) |", "|---|---|---|---|---|---|---|---|"]
    for c in resp.cases:
        L.append(f"| {c.case.value} | {c.additional_cpo_t:,.1f} | {_thb(c.gross_value_uplift_thb)} | {_thb(c.cost_avoidance_thb)} | {_thb(c.implementation_cost_thb)} | {_thb(c.annual_recurring_cost_thb)} | {_thb(c.net_benefit_year1_thb)} | {'-' if c.payback_months is None else c.payback_months} |")
    L += [f"\n## No double counting\n\n{resp.double_counting_note}\n", "## Formulas\n", "| key | expression | result | unit |", "|---|---|---|---|"]
    L += [f"| {f.key} | `{f.expression}` | {'' if f.result is None else f'{f.result:,}'} | {f.unit} |" for f in resp.formulas]
    L += ["\n## Assumptions\n", "| key | value | tag | source |", "|---|---|---|---|"]
    L += [f"| {a.key} | {a.value} | {a.tag.value} | {a.source or ''} |" for a in resp.assumptions if not a.key.startswith("case_multipliers.")]
    L += ["\nCase multipliers: see `GET /api/v1/roi/defaults`.\n", f"> {ROI_DISCLAIMER}"]
    return "\n".join(L)


def export(ctx: DemoContext, body: RoiExportRequest) -> ReportDocument:
    resp = calculate(ctx, body.inputs)
    if body.format == ExportFormat.csv:
        content, ext = _csv(resp), "csv"
    elif body.format == ExportFormat.markdown:
        content, ext = _markdown(resp), "md"
    else:
        payload = resp.model_dump(mode="json")
        payload["disclaimer_text"] = ROI_DISCLAIMER
        content, ext = json.dumps(payload, ensure_ascii=False, indent=2), "json"
    return ReportDocument(
        report_type="roi", title="ROI & value scenario (illustrative)", format=body.format, generated_at=datetime.now(UTC), as_of=ctx.as_of,
        filename=f"roi-scenario-{ctx.business_date}.{ext}", content=content, disclaimers=[DISCLAIMER],
    )


def printable_html(ctx: DemoContext, inp: RoiInputs) -> str:
    resp = calculate(ctx, inp)
    e = html.escape
    rows = "".join(
        f"<tr><th>{e(c.case.value)}</th><td>{c.additional_cpo_t:,.1f}</td><td>{_thb(c.gross_value_uplift_thb)}</td><td>{_thb(c.cost_avoidance_thb)}</td><td>{_thb(c.implementation_cost_thb)}</td>"
        f"<td>{_thb(c.annual_recurring_cost_thb)}</td><td>{_thb(c.net_benefit_year1_thb)}</td><td>{'-' if c.payback_months is None else c.payback_months}</td></tr>"
        for c in resp.cases
    )
    inputs = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in resp.inputs.model_dump().items())
    formulas = "".join(f"<tr><td>{e(f.key)}</td><td><code>{e(f.expression)}</code></td><td>{'' if f.result is None else f'{f.result:,}'} {e(f.unit)}</td></tr>" for f in resp.formulas if f.key.startswith("expected."))
    assum = "".join(f"<tr><td>{e(a.label)}</td><td>{e(str(a.value))} {e(a.unit or '')}</td><td>{e(a.tag.value)}</td><td>{e(a.source or '')}</td></tr>" for a in resp.assumptions if not a.key.startswith("case_multipliers."))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROI scenario (illustrative)</title><style>
body{{font:14px/1.5 system-ui,sans-serif;margin:24px auto;max-width:960px;padding:0 16px;color:#111}}
h1{{font-size:20px}}h2{{font-size:16px;margin-top:24px}}table{{border-collapse:collapse;width:100%;margin:8px 0}}th,td{{border:1px solid #bbb;padding:4px 8px;text-align:left;vertical-align:top}}
.disc{{border:2px solid #b45309;background:#fffbeb;padding:10px 12px;font-weight:600}}code{{font-size:12px}}@media print{{body{{margin:0}}}}
</style></head><body>
<h1>ROI &amp; value scenario (illustrative)</h1>
<p class="disc">{e(ROI_DISCLAIMER)}</p>
<p>Independent concept demo on synthetic data. Not an official system of any company. Generated for demo clock {e(ctx.as_of.isoformat())}.</p>
<h2>Inputs</h2><table>{inputs}</table>
<h2>Cases (year 1, THB)</h2><table><tr><th>case</th><th>additional CPO (t)</th><th>gross value uplift</th><th>cost avoidance</th><th>implementation</th><th>recurring</th><th>net benefit</th><th>payback (months)</th></tr>{rows}</table>
<h2>No double counting</h2><p>{e(resp.double_counting_note)}</p>
<h2>Formulas (expected case)</h2><table>{formulas}</table>
<h2>Assumptions</h2><table><tr><th>assumption</th><th>value</th><th>tag</th><th>source</th></tr>{assum}</table>
<p class="disc">{e(ROI_DISCLAIMER)}</p></body></html>"""


def printable_document(ctx: DemoContext, inp: RoiInputs) -> PrintableDocument:
    return PrintableDocument(
        report_type="roi", title="ROI & value scenario (illustrative)", filename=f"roi-scenario-{ctx.business_date}.html", html=printable_html(ctx, inp),
        generated_at=datetime.now(UTC), as_of=ctx.as_of, disclaimers=[DISCLAIMER],
    )
