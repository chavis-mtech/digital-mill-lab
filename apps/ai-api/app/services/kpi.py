"""Executive Control Tower KPIs (DML-035/037/041). Owner: backend-a.

Every KPI is computed from stored synthetic records up to the demo clock (never beyond as_of) and carries
provenance. Definitions (KPI_DEFINITIONS.md, mapped to real columns; W = window, hourly rows complete at W.end):

  ffb_received_t      = SUM(ffb_deliveries.accepted_kg) / 1000, received_ts in W            (KPI-01, accepted net)
  ffb_processed_t     = SUM(process_hourly.ffb_processed_t)                                  (KPI-02)
  cpo_produced_t      = SUM(process_hourly.cpo_t)                                            (KPI-03)
                        The data engine books CPO in the hour the FFB is processed and guarantees
                        produced = dispatched (cpo_output_lots.dispatched_at) + closing stock (CHK-03), so the
                        hourly production meter equals KPI-03's stock-based formula; there is no 3-6 h
                        sterilizer-to-tank lag in the synthetic data (a real mill needs lag alignment -> use
                        day / 7-day windows for decisions, not single hours).
  oer_pct             = 100 * SUM(cpo_t) / SUM(ffb_processed_t)    denominator = FFB PROCESSED (not received),
                        ratio of sums, accepted/processed mass basis                          (KPI-04 "process OER")
  ker_pct             = 100 * SUM(kernel_t) / SUM(ffb_processed_t)                           (KPI-05)
  throughput_tph      = SUM(ffb_processed_t) / SUM(running_minutes / 60)   (running hours, not scheduled) (KPI-06)
  equipment_availability_pct = 100 * SUM(running_minutes) / SUM(running_minutes + downtime_min)
                        Plant mechanical availability: scheduled time = running + stopped (planned + unplanned);
                        starved hours (no FFB, running = downtime = 0) are NOT counted as downtime  (KPI-08)
  plant_downtime_h    = SUM(process_hourly.downtime_min) / 60  (planned weekly stop + breakdown stops) (KPI-09)
  energy_kwh_per_t    = SUM(energy_consumption.electricity_kwh) / SUM(energy_consumption.ffb_processed_t),
                        plant rows (process_stage_id IS NULL); idle base load included in the numerator  (KPI-10)
  est_production_cost_thb_per_t (per t CPO, ILLUSTRATIVE, KPI-11):
        ( SUM_h ffb_processed_t * 1000 * ffb_price(day)                       FFB purchase (prices table)
        + SUM ffb_processed_t * (processing_cost_ex_ffb + maintenance_cost) conversion + maintenance rates
                                                                              (DOMAIN_PARAMETERS, Engineering Assumption)
        + SUM energy_consumption.cost_thb                                    grid import x tariff + diesel x price
        - SUM_h kernel_t * 1000 * kernel_price(day) )                        kernel credit (by-product credit method)
        / SUM(cpo_t)
        Conversion cost is assumed to EXCLUDE energy and maintenance (avoids the double count KPI_DEFINITIONS 4.7 warns of).
  active_maintenance_alerts = COUNT(alerts active at W.end with module = maintenance OR equipment_id set)  (KPI-12)
  logistics_queue_time_min  = AVG(truck_trips.weigh_in_ts - arrival_ts) over trucks weighed in during W
                        (completed spells only; trucks still waiting are right-censored -> /logistics/queue) (KPI-13)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.platform import ScenarioRun
from app.schemas.common import Period
from app.services.demo_context import DemoContext, provenance
from app.services.kpi_alerts import active_alerts, is_maintenance_alert
from app.services.kpi_common import (
    BASELINE_DAYS,
    Window,
    kpi_value,
    oer_status,
    param,
    period_windows,
    rnd,
    safe_div,
    status_above,
    status_below,
)
from app.services.kpi_data import SUM_COLS, aggregate, totals

SRC_HOURLY = "process_hourly"
SRC_ENERGY = "energy_consumption (plant)"


def cost_rates() -> dict[str, float]:
    return {
        "processing_cost_ex_ffb_thb_per_t_ffb": param("processing_cost_ex_ffb_thb_per_t_ffb"),
        "maintenance_cost_thb_per_t_ffb": param("maintenance_cost_thb_per_t_ffb"),
    }


def metric_values(t: dict[str, float | None]) -> dict[str, float | None]:
    """Derive KPI values from window sums (see module docstring)."""
    ffb = t.get("ffb_processed_t")
    cpo = t.get("cpo_t")
    run = t.get("running_h")
    down = t.get("downtime_h")
    rates = cost_rates()
    cost_num = None
    if ffb is not None and t.get("ffb_cost_thb") is not None:
        cost_num = (
            (t.get("ffb_cost_thb") or 0.0)
            + ffb * (rates["processing_cost_ex_ffb_thb_per_t_ffb"] + rates["maintenance_cost_thb_per_t_ffb"])
            + (t.get("energy_cost_thb") or 0.0)
            - (t.get("kernel_credit_thb") or 0.0)
        )
    return {
        "ffb_received_t": t.get("ffb_received_t") if t.get("ffb_received_t") is not None else (0.0 if t.get("hours") else None),
        "ffb_processed_t": ffb,
        "cpo_produced_t": cpo,
        "oer_pct": safe_div(cpo, ffb, 100.0),
        "ker_pct": safe_div(t.get("kernel_t"), ffb, 100.0),
        "throughput_tph": safe_div(ffb, run),
        "equipment_availability_pct": safe_div(run, (run or 0) + (down or 0), 100.0) if run is not None else None,
        "plant_downtime_h": down,
        "energy_kwh_per_t": safe_div(t.get("electricity_kwh"), t.get("energy_ffb_t")),
        "est_production_cost_thb_per_t": safe_div(cost_num, cpo),
        "logistics_queue_time_min": safe_div(t.get("queue_wait_sum_min"), t.get("queue_n")),
        "steam_t_per_t": safe_div(t.get("steam_t"), t.get("energy_ffb_t")),
        "energy_cost_thb_per_t": safe_div(t.get("energy_cost_thb"), t.get("energy_ffb_t")),
    }


# key -> (label, unit, good_direction, source)
KPI_META: dict[str, tuple[str, str, str, str]] = {
    "ffb_received_t": ("FFB received (accepted net)", "t", "up", "ffb_deliveries.accepted_kg"),
    "ffb_processed_t": ("FFB processed", "t", "up", SRC_HOURLY),
    "cpo_produced_t": ("CPO produced", "t", "up", SRC_HOURLY),
    "oer_pct": ("Oil extraction rate (OER)", "%", "up", SRC_HOURLY),
    "ker_pct": ("Kernel extraction rate (KER)", "%", "up", SRC_HOURLY),
    "throughput_tph": ("Throughput (per running hour)", "t/h", "up", SRC_HOURLY),
    "equipment_availability_pct": ("Plant availability", "%", "up", SRC_HOURLY),
    "plant_downtime_h": ("Plant downtime", "h", "down", SRC_HOURLY),
    "energy_kwh_per_t": ("Electricity per tonne FFB", "kWh/t", "down", SRC_ENERGY),
    "est_production_cost_thb_per_t": ("Estimated production cost (illustrative)", "THB/t CPO", "down",
                                      "process_hourly + energy_consumption + prices + DOMAIN_PARAMETERS cost rates"),
    "active_maintenance_alerts": ("Active maintenance alerts", "count", "down", "alerts (+ session status changes)"),
    "logistics_queue_time_min": ("Truck wait-to-weigh (mean)", "min", "down", "truck_trips"),
}  # fmt: skip
EXEC_KEYS = list(KPI_META)
EXTRA_SERIES = {
    "steam_t_per_t": ("Steam per tonne FFB", "t/t", "down", SRC_ENERGY),
    "energy_cost_thb_per_t": ("Energy cost per tonne FFB", "THB/t", "down", SRC_ENERGY),
}


def _alert_count(db: Session, at: datetime, session_id: str | None) -> tuple[int, int]:
    act = [a for a, _ in active_alerts(db, at, session_id) if is_maintenance_alert(a)]
    from app.services.kpi_alerts import ml_views  # noqa: PLC0415 - lazy import (QA-16: severity as seen at the clock, not the episode peak)

    views = ml_views(db, at, act)
    return len(act), sum(1 for a in act if views.get(a.id, (a.severity, a.title))[0] == "critical")


def oer_baseline(db: Session, ctx: DemoContext, before: datetime) -> float | None:
    """Trailing 28-day OER (ratio of sums) ending at `before`."""
    w = Window(max(before - timedelta(days=BASELINE_DAYS), ctx.window_start), before)
    if w.end <= w.start:
        return None
    t = totals(db, ctx, w)
    return safe_div(t.get("cpo_t"), t.get("ffb_processed_t"), 100.0)


def window_kpis(db: Session, ctx: DemoContext, cur: Window, prev: Window | None) -> list[dict[str, Any]]:
    tc = metric_values(totals(db, ctx, cur))
    tp = metric_values(totals(db, ctx, prev)) if prev else {}
    ac, crit = _alert_count(db, cur.end, ctx.session_id)
    pc = _alert_count(db, prev.end, ctx.session_id)[0] if prev else None
    tc["active_maintenance_alerts"] = float(ac)
    tp["active_maintenance_alerts"] = float(pc) if pc is not None else None
    baseline = oer_baseline(db, ctx, cur.start)
    status = {
        "oer_pct": oer_status(tc["oer_pct"], baseline),
        "equipment_availability_pct": status_below(tc["equipment_availability_pct"], "availability_pct"),
        "energy_kwh_per_t": status_above(tc["energy_kwh_per_t"], "kwh_per_t"),
        "logistics_queue_time_min": status_above(tc["logistics_queue_time_min"], "queue_min"),
        "active_maintenance_alerts": "high" if crit >= 2 else ("medium" if crit >= 1 else None),
    }
    target = {
        "oer_pct": baseline,
        "equipment_availability_pct": param("plant_availability_target_pct"),
        "energy_kwh_per_t": 18.5,
        "logistics_queue_time_min": 15.0,
    }
    out = []
    for key in EXEC_KEYS:
        label, unit, good, src = KPI_META[key]
        out.append(
            kpi_value(ctx, key, label, tc.get(key), unit, src, previous=tp.get(key), good_direction=good,
                      status=status.get(key), target=target.get(key))
        )  # fmt: skip
    return out


def executive_kpis(db: Session, ctx: DemoContext, period: Period, start: date | None = None, end: date | None = None) -> dict[str, Any]:
    cur, prev = period_windows(ctx, period, start, end)
    return {
        "period": Period(period).value,
        "period_start": cur.start,
        "period_end": cur.end,
        "previous_start": prev.start if prev else cur.start,
        "previous_end": prev.end if prev else cur.start,
        "kpis": window_kpis(db, ctx, cur, prev),
        "oer_baseline_pct": rnd(oer_baseline(db, ctx, cur.start), 3),
        "definitions_ref": "app/services/kpi.py module docstring; docs/business/KPI_DEFINITIONS.md",
    }


# ---------------------------------------------------------------------------- series
def _bucket_metric(row: pd.Series, metric: str) -> float | None:
    t = {c: (None if pd.isna(row.get(c)) else float(row.get(c))) for c in SUM_COLS}
    return metric_values(t).get(metric)


def metric_series(db: Session, ctx: DemoContext, metric: str, w: Window, granularity: str) -> list[dict[str, Any]]:
    if metric == "active_maintenance_alerts":
        agg = aggregate(db, ctx, w, granularity)
        idx = list(agg.index)
        pts = []
        for i, b in enumerate(idx):
            b_end = idx[i + 1].tz_convert("UTC").to_pydatetime() if i + 1 < len(idx) else w.end
            pts.append({"t": b.tz_convert("UTC").to_pydatetime(), "v": float(_alert_count(db, min(b_end, w.end), ctx.session_id)[0])})
        return pts
    agg = aggregate(db, ctx, w, granularity)
    return [{"t": b.tz_convert("UTC").to_pydatetime(), "v": rnd(_bucket_metric(row, metric), 4)} for b, row in agg.iterrows()]


def kpi_series(db: Session, ctx: DemoContext, metric: str, period: Period, granularity: str, compare_previous: bool) -> dict[str, Any]:
    meta = KPI_META.get(metric) or EXTRA_SERIES.get(metric)
    if meta is None:
        raise ApiError(422, "invalid_metric", f"Unknown metric '{metric}'", {"allowed": EXEC_KEYS + list(EXTRA_SERIES)})
    if Period(period) == Period.custom:
        raise ApiError(422, "invalid_period", "Use today, 7d or 30d for series")
    label, unit, _good, src = meta
    cur, prev = period_windows(ctx, period)
    series = [{"key": metric, "label": label, "unit": unit, "points": metric_series(db, ctx, metric, cur, granularity),
               "provenance": provenance("synthetic_actual", src, ctx)}]  # fmt: skip
    if compare_previous and prev is not None:
        shift = cur.start - prev.start
        pts = metric_series(db, ctx, metric, prev, granularity)
        for p in pts:
            p["t"] = p["t"] + shift
        series.append({"key": f"{metric}_previous", "label": f"{label} - previous period (shifted +{shift.days} d)", "unit": unit,
                       "points": pts, "provenance": provenance("synthetic_actual", src, ctx)})  # fmt: skip
    if metric == "oer_pct" and granularity in ("day", "week"):
        b = oer_baseline(db, ctx, cur.start)
        series.append({"key": "oer_baseline_pct", "label": "Trailing 28-day OER baseline at window start", "unit": "%",
                       "points": [{"t": p["t"], "v": rnd(b, 4)} for p in series[0]["points"]],
                       "provenance": provenance("synthetic_actual", SRC_HOURLY, ctx)})  # fmt: skip
    return {"metric": metric, "granularity": granularity, "series": series}


def sparklines(db: Session, ctx: DemoContext, days: int = 14) -> dict[str, list[dict[str, Any]]]:
    """Daily values of each control-tower KPI over the last N days (sparklines for the KPI cards)."""
    w = Window(max(ctx.as_of - timedelta(days=days), ctx.window_start), ctx.as_of)
    agg = aggregate(db, ctx, w, "day")
    out: dict[str, list[dict[str, Any]]] = {}
    for key in EXEC_KEYS:
        if key == "active_maintenance_alerts":
            continue
        out[key] = [{"t": b.tz_convert("UTC").to_pydatetime(), "v": rnd(_bucket_metric(row, key), 4)} for b, row in agg.iterrows()]
    return out


# ---------------------------------------------------------------------------- cost & productivity
def cost_productivity(db: Session, ctx: DemoContext, period: Period) -> dict[str, Any]:
    cur, prev = period_windows(ctx, period)
    t = totals(db, ctx, cur)
    ffb = t.get("ffb_processed_t") or 0.0
    rates = cost_rates()
    lines = [
        ("ffb_purchase", "FFB purchase (daily illustrative FFB price x FFB processed)", t.get("ffb_cost_thb") or 0.0),
        ("conversion", f"Conversion excl. energy & maintenance ({rates['processing_cost_ex_ffb_thb_per_t_ffb']:.0f} THB/t FFB, assumption)",
         ffb * rates["processing_cost_ex_ffb_thb_per_t_ffb"]),
        ("maintenance", f"Maintenance ({rates['maintenance_cost_thb_per_t_ffb']:.0f} THB/t FFB, assumption)", ffb * rates["maintenance_cost_thb_per_t_ffb"]),
        ("energy", "Purchased energy (grid import x tariff + diesel x price)", t.get("energy_cost_thb") or 0.0),
        ("kernel_credit", "Kernel credit (kernel x daily kernel price)", -(t.get("kernel_credit_thb") or 0.0)),
    ]  # fmt: skip
    gross = sum(v for k, _, v in lines if k != "kernel_credit")
    cost_lines = [
        {"key": k, "label": lab, "thb_per_t_ffb": rnd(safe_div(v, ffb), 2), "total_thb": rnd(v, 0), "share_pct": rnd(safe_div(v, gross, 100.0), 2)}
        for k, lab, v in lines
    ]
    mv = metric_values(t)
    mp = metric_values(totals(db, ctx, prev)) if prev else {}
    cpo_per_run_h = safe_div(t.get("cpo_t"), t.get("running_h"))
    cpo_per_run_h_prev = safe_div(mp.get("cpo_produced_t"), (totals(db, ctx, prev).get("running_h") if prev else None))
    prod = [
        kpi_value(ctx, "est_production_cost_thb_per_t", "Estimated net cost per t CPO", mv["est_production_cost_thb_per_t"], "THB/t CPO",
                  KPI_META["est_production_cost_thb_per_t"][3], mp.get("est_production_cost_thb_per_t"), "down", nd=0),
        kpi_value(ctx, "throughput_tph", "Throughput", mv["throughput_tph"], "t/h", SRC_HOURLY, mp.get("throughput_tph")),
        kpi_value(ctx, "equipment_availability_pct", "Plant availability", mv["equipment_availability_pct"], "%", SRC_HOURLY,
                  mp.get("equipment_availability_pct")),
        kpi_value(ctx, "cpo_per_running_h", "CPO per running hour", cpo_per_run_h, "t/h", SRC_HOURLY, cpo_per_run_h_prev),
        kpi_value(ctx, "energy_kwh_per_t", "Electricity per tonne FFB", mv["energy_kwh_per_t"], "kWh/t", SRC_ENERGY, mp.get("energy_kwh_per_t"), "down"),
        kpi_value(ctx, "energy_cost_thb_per_t", "Purchased energy cost per tonne FFB", mv["energy_cost_thb_per_t"], "THB/t", SRC_ENERGY,
                  mp.get("energy_cost_thb_per_t"), "down"),
        kpi_value(ctx, "oer_pct", "OER", mv["oer_pct"], "%", SRC_HOURLY, mp.get("oer_pct")),
    ]  # fmt: skip
    return {
        "period": Period(period).value,
        "cost_lines": cost_lines,
        "productivity": prod,
        "note": "Illustrative cost model on synthetic data; not any company's financial results. Rates: "
        "processing_cost_ex_ffb_thb_per_t_ffb and maintenance_cost_thb_per_t_ffb (DOMAIN_PARAMETERS, Engineering Assumption); "
        "prices are an illustrative synthetic series. Cost per t CPO = (FFB + conversion + maintenance + purchased energy - kernel credit) / CPO.",
        "provenance": provenance("synthetic_actual", "process_hourly + energy_consumption + prices + DOMAIN_PARAMETERS", ctx),
    }


# ---------------------------------------------------------------------------- scenario comparison
COMPARE_KEYS = ["oer_pct", "ffb_processed_t", "throughput_tph", "equipment_availability_pct", "plant_downtime_h",
                "energy_kwh_per_t", "logistics_queue_time_min", "steam_t_per_t"]  # fmt: skip


def scenario_comparison(db: Session, ctx: DemoContext) -> dict[str, Any]:
    """Focus business day of each scenario vs NORMAL_DAY, computed from the data (not the design-intent text).

    A scenario is included only when its focus time is <= as_of; the focus day is cut at as_of if still running.
    """
    runs = {r.code: r for r in db.execute(select(ScenarioRun)).scalars()}
    from app.services.kpi_common import iso_utc, local_midnight, to_local  # noqa: PLC0415

    def day_values(run: ScenarioRun) -> dict[str, float | None] | None:
        focus = iso_utc(run.focus_ts)
        if focus > ctx.as_of:
            return None
        d = to_local(ctx, focus).date()
        w = Window(local_midnight(ctx, d), min(local_midnight(ctx, d + timedelta(days=1)), ctx.as_of))
        return metric_values(totals(db, ctx, w))

    base_run = runs.get("NORMAL_DAY")
    base = day_values(base_run) if base_run else None
    rows = []
    for code in ["NORMAL_DAY", "OER_DEGRADATION", "PRESS_VIBRATION_ANOMALY", "STEAM_PRESSURE_DEVIATION", "TRUCK_QUEUE_CONGESTION", "ENERGY_EFFICIENCY_DROP"]:
        run = runs.get(code)
        if run is None:
            continue
        vals = day_values(run)
        if vals is None:
            continue
        kpis = []
        for k in COMPARE_KEYS:
            label, unit, good, src = KPI_META.get(k) or EXTRA_SERIES[k]
            kpis.append(kpi_value(ctx, k, label, vals.get(k), unit, src, previous=(base or {}).get(k), good_direction=good))
        rows.append({"scenario_code": code, "label": run.name_en, "kpis": kpis,
                     "focus_day": to_local(ctx, iso_utc(run.focus_ts)).date().isoformat()})  # fmt: skip
    return {
        "baseline": "NORMAL_DAY",
        "rows": rows,
        "note": "Values are measured on each scenario's focus business day (cut at as_of); 'previous' = NORMAL_DAY. "
        "Scenarios whose focus time is after as_of are omitted. Effects are computed, not the episodes' design intent.",
    }


# ---------------------------------------------------------------------------- business impact cards
def impact_cards(db: Session, ctx: DemoContext, period: Period = Period.today) -> list[dict[str, Any]]:
    """Business-impact cards (what_if ESTIMATES with formulas) for the period ending at as_of.

    lost_cpo_t       = ffb_processed_t x max(0, baseline_oer - oer) / 100      baseline = trailing 28-day OER before the period
    lost_cpo_value   = lost_cpo_t x 1000 x CPO price (THB/kg, prices table, as_of day; illustrative)
    downtime_ffb_t   = plant_downtime_h x throughput_tph   (processing opportunity; if the mill is supply-limited the FFB is
                       deferred, not lost - KPI_DEFINITIONS 4.10)
    excess_kwh       = actual - production-adjusted expected kWh (energy.daily_markers), summed over the period's days, >= 0
    """
    from app.services.energy import daily_markers  # noqa: PLC0415
    from app.services.kpi_common import price_map, price_on  # noqa: PLC0415

    cur, _ = period_windows(ctx, period)
    t = totals(db, ctx, cur)
    mv = metric_values(t)
    base = oer_baseline(db, ctx, cur.start)
    ffb = t.get("ffb_processed_t") or 0.0
    gap = max(0.0, (base or 0) - (mv["oer_pct"] or 0)) if base is not None and mv["oer_pct"] is not None else None
    lost = ffb * gap / 100.0 if gap is not None else None
    price = price_on(price_map(db, "cpo"), ctx.business_date, param("cpo_price_thb_per_t") / 1000.0)
    value = lost * 1000.0 * price if lost is not None else None
    down = t.get("downtime_h") or 0.0
    tph = mv["throughput_tph"]
    dt_ffb = down * tph if tph else None
    markers = daily_markers(db, ctx, cur)
    excess = sum(max(0.0, (m["actual_kwh"] or 0) - (m["expected_kwh"] or 0)) for m in markers) if markers else None
    pv = provenance("what_if", "process_hourly + energy_consumption + prices (estimate)", ctx)

    def card(key, label, v, unit, expr, inputs, nd=2):
        return {"key": key, "label": label, "value": rnd(v, nd), "unit": unit,
                "formula": {"key": key, "label": label, "expression": expr, "inputs": inputs, "result": rnd(v, nd), "unit": unit}, "provenance": pv}

    return [
        card("lost_cpo_t", "CPO not recovered vs 28-day OER baseline", lost, "t", "lost_cpo_t = ffb_processed_t * max(0, baseline_oer_pct - oer_pct) / 100",
             {"ffb_processed_t": rnd(ffb, 2), "baseline_oer_pct": rnd(base, 3), "oer_pct": rnd(mv["oer_pct"], 3)}),
        card("lost_cpo_value_thb", "Value of CPO not recovered (illustrative price)", value, "THB", "lost_cpo_value_thb = lost_cpo_t * 1000 * cpo_price_thb_per_kg",
             {"lost_cpo_t": rnd(lost, 3), "cpo_price_thb_per_kg": rnd(price, 3)}, 0),
        card("downtime_processing_opportunity_t", "FFB processing opportunity during downtime", dt_ffb, "t",
             "downtime_ffb_t = plant_downtime_h * throughput_tph (deferred, not lost, when the mill is supply-limited)",
             {"plant_downtime_h": rnd(down, 2), "throughput_tph": rnd(tph, 2)}),
        card("excess_electricity_kwh", "Electricity above production-adjusted expectation", excess, "kWh",
             "excess_kwh = sum_days max(0, actual_kwh - (a*hours + b*ffb_t))  (OLS on the prior 28 days)", {"days": len(markers)}, 0),
    ]  # fmt: skip
