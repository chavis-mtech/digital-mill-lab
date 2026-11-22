"""Energy & Sustainability (DML-065/066/069/070 data side). Owner: backend-a.

Plant totals = energy_consumption rows with process_stage_id IS NULL (stage rows are sub-meters).
  kwh_per_t_ffb          = SUM(electricity_kwh) / SUM(ffb_processed_t)        (idle base load in the numerator, KPI 4.6)
  steam_t_per_t_ffb      = SUM(steam_t) / SUM(ffb_processed_t)
  water_m3_per_t_ffb     = SUM(water_m3) / SUM(ffb_processed_t)
  energy_cost_thb_per_t  = SUM(cost_thb) / SUM(ffb_processed_t)    cost_thb = grid import x tariff + diesel x price
                           (biomass fibre/shell burned in the boiler has no purchase cost)
  grid_import_share_pct  = 100 * SUM(grid_import_kwh) / SUM(electricity_kwh)
  idle_kwh               = SUM(idle_kwh)  (metered consumption while not processing) ; idle cost estimate = idle_kwh x
                           grid tariff (what the idle energy would cost if bought; labelled estimate)
  Sources: grid import kWh, self-generated kWh (turbine / genset), diesel L (genset + loaders), biomass t (fibre + shell).

Abnormal consumption (statistical baseline, AI-E02 data side; the ML agent's model lives under /ai/energy/*):
  Fit on the reference hours (the 28 days before the evaluated day, hours <= as_of) an ordinary least-squares line
      kWh_h = a + b * ffb_processed_t_h          (a = fixed / idle load per hour, b = kWh per extra tonne)
  Expected kWh for a day = SUM over its hours of (a + b * ffb_h). Residual r = actual - expected; the daily residuals
  of the reference days give s.d. sigma; z = r / sigma. A day is marked abnormal when z >= 2.5 (high) or z >= 2.0
  (medium) and actual > expected by more than 3%. This is production-adjusted: a low-throughput day is not flagged
  just because fixed loads raise kWh/t.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.core import ProcessStage
from app.schemas.common import Period
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_common import (
    THRESHOLDS,
    Window,
    assumption_from_param,
    kpi_value,
    local_midnight,
    param,
    period_windows,
    price_map,
    price_on,
    rnd,
    safe_div,
    status_above,
)
from app.services.kpi_data import add_bucket, load_energy

SRC = "energy_consumption (plant)"
REF_DAYS = 28


def _sums(e: pd.DataFrame) -> dict[str, float]:
    if e.empty:
        return {}
    cols = ["electricity_kwh", "grid_import_kwh", "self_generated_kwh", "steam_t", "water_m3", "ffb_processed_t", "idle_kwh", "cost_thb",
            "diesel_l", "boiler_fibre_t", "boiler_shell_t"]  # fmt: skip
    return {c: float(e[c].fillna(0).sum()) for c in cols}


def _values(s: dict[str, float], tariff: float | None) -> dict[str, float | None]:
    ffb = s.get("ffb_processed_t")
    return {
        "electricity_kwh": s.get("electricity_kwh"),
        "kwh_per_t_ffb": safe_div(s.get("electricity_kwh"), ffb),
        "steam_t_per_t_ffb": safe_div(s.get("steam_t"), ffb),
        "water_m3_per_t_ffb": safe_div(s.get("water_m3"), ffb),
        "energy_cost_thb_per_t": safe_div(s.get("cost_thb"), ffb),
        "grid_import_share_pct": safe_div(s.get("grid_import_kwh"), s.get("electricity_kwh"), 100.0),
        "idle_kwh": s.get("idle_kwh"),
        "idle_cost_estimate_thb": (s.get("idle_kwh") or 0) * tariff if tariff and s else None,
        "diesel_l_per_t_ffb": safe_div(s.get("diesel_l"), ffb),
    }


KPI_META = [
    ("electricity_kwh", "Electricity consumed", "kWh", "down"),
    ("kwh_per_t_ffb", "Electricity per tonne FFB", "kWh/t", "down"),
    ("steam_t_per_t_ffb", "Steam per tonne FFB", "t/t", "down"),
    ("water_m3_per_t_ffb", "Water per tonne FFB", "m3/t", "down"),
    ("energy_cost_thb_per_t", "Purchased energy cost per tonne FFB", "THB/t", "down"),
    ("grid_import_share_pct", "Grid import share of electricity", "%", "down"),
    ("idle_kwh", "Idle consumption (not processing)", "kWh", "down"),
    ("idle_cost_estimate_thb", "Idle energy valued at grid tariff (estimate)", "THB", "down"),
    ("diesel_l_per_t_ffb", "Diesel per tonne FFB", "L/t", "down"),
]


# ---------------------------------------------------------------------------- statistical baseline
def fit_baseline(ref_hourly: pd.DataFrame) -> tuple[float, float] | None:
    """OLS kWh_h = a + b * ffb_h over reference hours. Returns (a, b) or None if too little data."""
    if ref_hourly.empty or len(ref_hourly) < 48:
        return None
    x = ref_hourly["ffb_processed_t"].fillna(0).to_numpy()
    y = ref_hourly["electricity_kwh"].fillna(0).to_numpy()
    if np.var(x) == 0:
        return None
    b, a = np.polyfit(x, y, 1)
    return float(a), float(b)


def daily_markers(db: Session, ctx: DemoContext, w: Window) -> list[dict[str, Any]]:
    """Production-adjusted daily residual z-scores for each business day in w (see module docstring)."""
    hist = load_energy(db, Window(max(w.start - timedelta(days=REF_DAYS), ctx.window_start), w.end))
    if hist.empty:
        return []
    hist = add_bucket(hist, "ts", ctx, "day")
    days = sorted(d for d in hist["bucket"].unique() if d >= pd.Timestamp(w.start).tz_convert(ctx.timezone).normalize())
    out = []
    for d in days:
        ref = hist[(hist["bucket"] < d) & (hist["bucket"] >= d - pd.Timedelta(days=REF_DAYS))]
        coef = fit_baseline(ref)
        if coef is None:
            continue
        a, b = coef
        ref_d = ref.assign(exp=a + b * ref["ffb_processed_t"].fillna(0)).groupby("bucket")[["electricity_kwh", "exp"]].sum()
        sigma = float((ref_d["electricity_kwh"] - ref_d["exp"]).std())
        day = hist[hist["bucket"] == d]
        actual = float(day["electricity_kwh"].sum())
        expected = float((a + b * day["ffb_processed_t"].fillna(0)).sum())
        z = (actual - expected) / sigma if sigma > 0 else None
        sev = None
        if z is not None and actual > expected * 1.03:
            sev = "high" if z >= 2.5 else ("medium" if z >= 2.0 else None)
        out.append({
            "t": d.tz_convert("UTC").to_pydatetime(), "actual_kwh": rnd(actual, 1), "expected_kwh": rnd(expected, 1), "z_score": rnd(z, 2),
            "ffb_processed_t": rnd(float(day["ffb_processed_t"].sum()), 1), "hours": int(len(day)), "abnormal": sev is not None, "severity": sev,
            "basis": f"OLS on {len(ref)} reference hours: kWh_h = {a:.1f} + {b:.2f} x ffb_t_h; sigma(daily residual) = {sigma:.0f} kWh",
        })  # fmt: skip
    return out


def expected_today(db: Session, ctx: DemoContext) -> dict[str, Any] | None:
    """Expected vs actual electricity for the as_of day so far (used by the executive insight rule R3)."""
    today = Window(max(local_midnight(ctx, ctx.business_date), ctx.window_start), ctx.as_of)
    m = daily_markers(db, ctx, today)
    return m[-1] if m else None


# ---------------------------------------------------------------------------- endpoints
def summary(db: Session, ctx: DemoContext, period: Period) -> dict[str, Any]:
    cur, prev = period_windows(ctx, period)
    tariff = price_on(price_map(db, "electricity"), ctx.business_date, param("grid_electricity_thb_per_kwh"))
    s_cur = _sums(load_energy(db, cur))
    s_prev = _sums(load_energy(db, prev)) if prev else {}
    v, vp = _values(s_cur, tariff), _values(s_prev, tariff) if s_prev else {}
    status = {"kwh_per_t_ffb": status_above(v["kwh_per_t_ffb"], "kwh_per_t"), "steam_t_per_t_ffb": status_above(v["steam_t_per_t_ffb"], "steam_t_per_t")}
    target = {"kwh_per_t_ffb": THRESHOLDS["kwh_per_t"]["amber"], "steam_t_per_t_ffb": THRESHOLDS["steam_t_per_t"]["amber"]}
    kpis = [kpi_value(ctx, k, lab, v.get(k), u, SRC if k != "idle_cost_estimate_thb" else "energy_consumption.idle_kwh x electricity price",
                      vp.get(k), g, status.get(k), target.get(k),
                      kind="what_if" if k == "idle_cost_estimate_thb" else "synthetic_actual") for k, lab, u, g in KPI_META]  # fmt: skip
    stages = {s.id: (s.code, s.name_en) for s in db.execute(select(ProcessStage)).scalars()}
    st = load_energy(db, cur, all_stages=True)
    by_stage = []
    total = s_cur.get("electricity_kwh") or 0.0
    if not st.empty:
        sub = st[st["process_stage_id"].notna()].groupby("process_stage_id")["electricity_kwh"].sum()
        for sid, kwh in sub.sort_values(ascending=False).items():
            code, name = stages.get(int(sid), (str(sid), str(sid)))
            by_stage.append({"key": code, "label": name, "kwh": rnd(float(kwh), 1), "share_pct": rnd(safe_div(float(kwh), total, 100.0), 2)})
        unmetered = total - float(sub.sum())
        by_stage.append({"key": "UNMETERED", "label": "Unmetered / base load (plant meter - stage sub-meters)", "kwh": rnd(unmetered, 1),
                         "share_pct": rnd(safe_div(unmetered, total, 100.0), 2)})  # fmt: skip
    sources = [
        {"key": "grid_import_kwh", "label": "Grid import", "kwh": rnd(s_cur.get("grid_import_kwh"), 1), "share_pct": rnd(safe_div(s_cur.get("grid_import_kwh"), total, 100.0), 2)},
        {"key": "self_generated_kwh", "label": "Self-generated (steam turbine / genset)", "kwh": rnd(s_cur.get("self_generated_kwh"), 1),
         "share_pct": rnd(safe_div(s_cur.get("self_generated_kwh"), total, 100.0), 2)},
    ]  # fmt: skip
    fuels = [
        kpi_value(ctx, "diesel_l", "Diesel (genset + loaders)", s_cur.get("diesel_l"), "L", SRC, s_prev.get("diesel_l"), "down"),
        kpi_value(ctx, "biomass_t", "Biomass burned (fibre + shell)", (s_cur.get("boiler_fibre_t") or 0) + (s_cur.get("boiler_shell_t") or 0) if s_cur else None, "t", SRC,
                  (s_prev.get("boiler_fibre_t", 0) + s_prev.get("boiler_shell_t", 0)) if s_prev else None, "flat"),
        kpi_value(ctx, "steam_t", "Steam produced", s_cur.get("steam_t"), "t", SRC, s_prev.get("steam_t"), "flat"),
    ]  # fmt: skip
    return {
        "kpis": kpis,
        "by_stage": by_stage,
        "sources": sources,
        "fuels": fuels,
        "abnormal_days": [m for m in daily_markers(db, ctx, cur) if m["abnormal"]],
        "provenance": provenance("synthetic_actual", SRC, ctx),
        "method": "Ratios are ratio of sums over plant rows; abnormal days by production-adjusted residual z-score (app/services/energy.py).",
    }


SERIES_META = {
    "electricity_kwh": ("Electricity consumed", "kWh", lambda s: s.get("electricity_kwh")),
    "kwh_per_t_ffb": ("Electricity per tonne FFB", "kWh/t", lambda s: safe_div(s.get("electricity_kwh"), s.get("ffb_processed_t"))),
    "steam_t": ("Steam produced", "t", lambda s: s.get("steam_t")),
    "water_m3": ("Water used", "m3", lambda s: s.get("water_m3")),
    "cost_thb": ("Purchased energy cost", "THB", lambda s: s.get("cost_thb")),
    "grid_import_kwh": ("Grid import", "kWh", lambda s: s.get("grid_import_kwh")),
    "idle_kwh": ("Idle consumption", "kWh", lambda s: s.get("idle_kwh")),
}


def series(db: Session, ctx: DemoContext, metric: str, period: Period, granularity: str) -> dict[str, Any]:
    if metric not in SERIES_META:
        raise ApiError(422, "invalid_metric", f"Unknown metric '{metric}'", {"allowed": list(SERIES_META)})
    if Period(period) == Period.custom:
        raise ApiError(422, "invalid_period", "Use today, 7d or 30d for series")
    cur, _ = period_windows(ctx, period)
    e = load_energy(db, cur)
    label, unit, fn = SERIES_META[metric]
    pts = []
    if not e.empty:
        e = add_bucket(e, "ts", ctx, granularity)
        for b, g in e.groupby("bucket"):
            pts.append({"t": b.tz_convert("UTC").to_pydatetime(), "v": rnd(fn(_sums(g)), 4)})
    out = [{"key": metric, "label": label, "unit": unit, "points": pts, "provenance": provenance("synthetic_actual", SRC, ctx)}]
    markers = daily_markers(db, ctx, cur) if granularity in ("day", "week") or metric in ("electricity_kwh", "kwh_per_t_ffb") else []
    if metric == "electricity_kwh" and granularity == "day" and markers:
        out.append({"key": "expected_kwh", "label": "Production-adjusted expected kWh (statistical baseline)", "unit": "kWh",
                    "points": [{"t": m["t"], "v": m["expected_kwh"]} for m in markers], "provenance": provenance("synthetic_actual", SRC + " (OLS baseline)", ctx)})  # fmt: skip
    return {"metric": metric, "granularity": granularity, "series": out, "markers": markers}


def what_if(db: Session, ctx: DemoContext, body: Any) -> dict[str, Any]:
    """Energy what-if over the last 30 days' measured daily averages, scaled to `days` (DML-069). All outputs what_if.

    process_kwh  = electricity - idle                    (measured, last 30 days, per day)
    scenario_kwh = process_kwh x (1 - eff%) + idle x (1 - idle_red%)
    grid_after   = grid_before x (scenario_kwh / baseline_kwh) x (1 - grid_red%)   (shift to self-generation)
    biogas (optional): biogas_kwh = POME m3 x biogas_m3_per_m3_pome x biogas_kwh_el_per_m3, offsets grid_after (no export credited)
    saving_thb = (grid_before - grid_after) x tariff     (self-generated biomass power has no purchase cost)
    """
    w = Window(max(ctx.as_of - timedelta(days=30), ctx.window_start), ctx.as_of)
    e = load_energy(db, w)
    if e.empty:
        raise ApiError(422, "no_data", "No energy data before as_of")
    s = _sums(e)
    ndays = max(len(e) / 24.0, 1 / 24)
    per_day = {k: v / ndays for k, v in s.items()}
    tariff = body.electricity_tariff_thb_per_kwh or price_on(price_map(db, "electricity"), ctx.business_date, param("grid_electricity_thb_per_kwh"))
    days = body.days
    base_kwh = per_day["electricity_kwh"] * days
    idle = per_day["idle_kwh"] * days
    proc = base_kwh - idle
    scen = proc * (1 - body.efficiency_improvement_pct / 100) + idle * (1 - body.idle_reduction_pct / 100)
    grid_before = per_day["grid_import_kwh"] * days
    grid_after = grid_before * safe_div(scen, base_kwh) * (1 - body.grid_import_reduction_pct / 100)
    biogas_kwh = 0.0
    from sqlalchemy import func  # noqa: PLC0415

    from app.models.production import ByproductOutput, ProductionBatch  # noqa: PLC0415

    pome_t = db.execute(
        select(func.sum(ByproductOutput.quantity_t)).join(ProductionBatch, ProductionBatch.id == ByproductOutput.production_batch_id)
        .where(ByproductOutput.product == "pome", ProductionBatch.start_ts >= w.start, ProductionBatch.end_ts <= w.end)
    ).scalar_one_or_none() or 0.0  # fmt: skip
    if body.biogas_capture:
        biogas_kwh = pome_t / ndays * days * param("biogas_m3_per_m3_pome") * param("biogas_kwh_el_per_m3")
    grid_after_bio = max(0.0, grid_after - biogas_kwh)
    saving_kwh = base_kwh - scen
    saving_thb = (grid_before - grid_after_bio) * tariff
    ffb = per_day["ffb_processed_t"] * days
    pv = provenance("what_if", "energy_consumption (last 30 days) + DOMAIN_PARAMETERS", ctx)
    return {
        "baseline_kwh": rnd(base_kwh, 0), "scenario_kwh": rnd(scen, 0), "saving_kwh": rnd(saving_kwh, 0), "saving_thb": rnd(saving_thb, 0),
        "kwh_per_t_before": rnd(safe_div(base_kwh, ffb), 3), "kwh_per_t_after": rnd(safe_div(scen, ffb), 3),
        "grid_import_before_kwh": rnd(grid_before, 0), "grid_import_after_kwh": rnd(grid_after_bio, 0), "biogas_kwh": rnd(biogas_kwh, 0),
        "formulas": [
            {"key": "scenario_kwh", "label": "Scenario electricity", "expression": "scenario_kwh = (baseline_kwh - idle_kwh) * (1 - eff/100) + idle_kwh * (1 - idle_red/100)",
             "inputs": {"baseline_kwh": rnd(base_kwh, 0), "idle_kwh": rnd(idle, 0), "eff": body.efficiency_improvement_pct, "idle_red": body.idle_reduction_pct},
             "result": rnd(scen, 0), "unit": "kWh"},
            {"key": "grid_after_kwh", "label": "Grid import after", "expression": "grid_after = grid_before * scenario_kwh / baseline_kwh * (1 - grid_red/100) - biogas_kwh (>= 0)",
             "inputs": {"grid_before": rnd(grid_before, 0), "grid_red": body.grid_import_reduction_pct, "biogas_kwh": rnd(biogas_kwh, 0)},
             "result": rnd(grid_after_bio, 0), "unit": "kWh"},
            {"key": "saving_thb", "label": "Purchased-electricity saving", "expression": "saving_thb = (grid_before - grid_after) * tariff",
             "inputs": {"tariff_thb_per_kwh": tariff}, "result": rnd(saving_thb, 0), "unit": "THB"},
        ],  # fmt: skip
        "assumptions": [
            {"key": "baseline_window", "label": "Baseline = measured daily averages of the 30 days before as_of, scaled to days", "value": days, "unit": "d",
             "tag": "synthetic_demonstration_data", "source": "energy_consumption", "editable": True},
            assumption_from_param("grid_electricity_thb_per_kwh", "Grid tariff", tariff),
            assumption_from_param("biogas_m3_per_m3_pome", "Biogas yield per m3 POME"),
            assumption_from_param("biogas_kwh_el_per_m3", "Electricity per m3 biogas"),
        ],
        "limits": [
            "Efficiency and idle reductions are user inputs, not engineering findings; no specific equipment change is proven to deliver them.",
            "Only grid import is valued: self-generated power from the mill's own fibre/shell has no purchase cost, so a kWh saving does not always save money.",
            "Biogas surplus beyond grid import is not credited (export tariffs and plant capex are out of scope); POME tonnes ~ m3.",
            "No environmental or emissions conclusion is drawn; no steam-balance re-simulation (turbine output depends on steam demand).",
            "Synthetic data - not any company's results.",
        ],
        "provenance": pv,
    }
