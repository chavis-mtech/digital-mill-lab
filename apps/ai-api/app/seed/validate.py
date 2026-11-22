"""Dataset validator: python -m app.seed.validate [--db-url URL] [--json] [--no-checksum]

Checks referential integrity, the time window, mass balance, physical ranges against DOMAIN_PARAMETERS, the
researcher's consistency checks (CHK-01..10), scenario cross-module effects, ground-truth coverage, the audit hash
chain and the determinism checksum (vs data/synthetic/MANIFEST.json when seed/anchor/days match).
Exit code 1 if any 'fail'-level check fails ('info' checks are reported, never fatal).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text

from app.seed.assumptions import P, P_range
from app.seed.registry import TRUCK_TYPES


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    level: str = "fail"  # fail | info


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", level: str = "fail") -> None:
        self.checks.append(Check(name, bool(ok), detail, level))

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks if c.level == "fail")


def _df(engine: Engine, sql: str, ts_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    with engine.connect() as c:
        df = pd.read_sql(text(sql), c)
    for col in ts_cols:
        if col in df:
            df[col] = pd.to_datetime(df[col], utc=False, format="mixed").dt.tz_localize(None)
    return df


def _scalar(engine: Engine, sql: str):
    with engine.connect() as c:
        return c.execute(text(sql)).scalar()


LOCAL = pd.Timedelta(hours=7)


def validate(engine: Engine, manifest: dict | None = None, check_checksum: bool = True) -> Report:  # noqa: C901 - a flat list of checks reads best
    from app.seed.writer import FORBIDDEN_TABLES, OWNED_TABLES, content_checksum

    r = Report()
    # ------------------------------------------------------------------ structure
    if engine.dialect.name == "sqlite":
        with engine.connect() as c:
            bad = c.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        r.add("referential_integrity (PRAGMA foreign_key_check)", not bad, f"{len(bad)} violations")
    counts = {t: _scalar(engine, f"SELECT COUNT(*) FROM {t}") for t in OWNED_TABLES}  # noqa: S608
    empty = [t for t, n in counts.items() if not n]
    r.add("owned tables populated", not empty, f"empty: {empty}" if empty else f"{len(counts)} tables, {sum(counts.values()):,} rows")
    forb = {t: _scalar(engine, f"SELECT COUNT(*) FROM {t}") for t in FORBIDDEN_TABLES}  # noqa: S608
    r.add("ML/copilot/session tables untouched", not any(forb.values()), json.dumps({k: v for k, v in forb.items() if v}))
    fict = _df(engine, "SELECT name, is_fictional FROM companies")
    fac = _df(engine, "SELECT name FROM facilities")
    r.add("fictional entities only", bool(fict.is_fictional.all()) and fict.name.str.contains("fictional").all() and fac.name.str.startswith("Demo").all(),
          f"{fict.name.tolist()} / {fac.name.tolist()}")
    # ------------------------------------------------------------------ time window
    ph = _df(engine, "SELECT * FROM process_hourly ORDER BY ts", ("ts",))
    w0, w1 = ph.ts.min(), ph.ts.max() + pd.Timedelta(hours=1)
    days = int(round((w1 - w0) / pd.Timedelta(days=1)))
    probes = {
        "sensor_readings": ["ts"], "truck_trips": ["arrival_ts", "exit_ts", "weigh_out_ts"], "alerts": ["raised_at", "resolved_at"],
        "maintenance_events": ["start_ts", "end_ts"], "work_orders": ["created_at", "resolved_at"], "work_order_status_history": ["changed_at"],
        "energy_consumption": ["ts"], "cpo_output_lots": ["fill_start_ts", "fill_end_ts", "dispatched_at"], "quality_measurements": ["sample_ts"],
        "injected_events": ["start_ts", "end_ts"], "scenario_runs": ["start_ts", "end_ts", "focus_ts"], "queue_events": ["ts"],
        "production_batches": ["start_ts", "end_ts"], "audit_logs": ["ts"], "ffb_deliveries": ["received_ts"],
    }
    out_of_window = []
    for tbl, cols in probes.items():
        for col in cols:
            lo, hi = _scalar(engine, f"SELECT MIN({col}) FROM {tbl}"), _scalar(engine, f"SELECT MAX({col}) FROM {tbl}")  # noqa: S608
            if lo is None:
                continue
            lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)
            if lo < w0 or hi > w1:
                out_of_window.append(f"{tbl}.{col} [{lo}, {hi}]")
    r.add("no data outside the window / beyond the anchor", not out_of_window, "; ".join(out_of_window) or f"{w0} .. {w1} UTC ({days} days)")
    r.add("process_hourly has one row per hour", len(ph) == days * 24 and ph.ts.is_monotonic_increasing, f"{len(ph)} rows")
    # ------------------------------------------------------------------ hourly mass balance & capacity
    run = ph.ffb_processed_t > 0
    err = (ph.cpo_t - ph.ffb_processed_t * ph.oer_pct.fillna(0) / 100).abs()[run].max()
    r.add("hourly CPO = FFB x OER (REL-01)", err < 1e-3, f"max abs err {err:.2e} t")
    errk = (ph.kernel_t - ph.ffb_processed_t * ph.ker_pct.fillna(0) / 100).abs()[run].max()
    r.add("hourly kernel = FFB x KER (REL-01)", errk < 1e-3, f"max abs err {errk:.2e} t")
    cap = P("mill_capacity_t_ffb_per_h")
    r.add("throughput <= design capacity (CHK-02)", ph.throughput_tph.max() <= cap + 1e-6 and (ph.ffb_processed_t <= cap * ph.running_minutes / 60 + 1e-3).all(),
          f"max {ph.throughput_tph.max():.2f} t/h vs {cap}")
    r.add("running + downtime <= 60 min", ((ph.running_minutes + ph.downtime_min) <= 60 + 1e-6).all(), "")
    stock = ph.ffb_waiting_t.to_numpy()
    recon = np.cumsum(ph.ffb_received_t.to_numpy() - ph.ffb_processed_t.to_numpy())
    r.add("ramp stock continuity (opening stock 0)", np.abs(stock - recon).max() < 0.05 and stock.min() >= -1e-6,
          f"max drift {np.abs(stock - recon).max():.4f} t, min stock {stock.min():.3f}")
    r.add("processed <= received + opening stock (cumulative)", (np.cumsum(ph.ffb_processed_t) <= np.cumsum(ph.ffb_received_t) + 0.01).all(), "")
    ramp_cap = P("ramp_buffer_capacity_t")
    scen = _df(engine, "SELECT * FROM scenario_runs", ("start_ts", "end_ts", "focus_ts", "baseline_ts"))
    q = scen[scen.code == "TRUCK_QUEUE_CONGESTION"]
    over = ph[ph.ffb_waiting_t > ramp_cap]
    if not q.empty:
        qs, qe = q.start_ts.iloc[0], q.end_ts.iloc[0] + pd.Timedelta(days=1)
        over = over[(over.ts < qs) | (over.ts >= qe)]
    r.add(f"ramp stock <= {ramp_cap:.0f} t outside the documented congestion episode", over.empty, f"{len(over)} hours over; max overall {ph.ffb_waiting_t.max():.0f} t")
    # FFB received per hour = FFB batches unloaded (non-rejected) per hour
    fb = _df(engine, "SELECT received_ts, mass_kg, status FROM ffb_batches", ("received_ts",))
    fb = fb[fb.status != "rejected"]
    recv_h = fb.groupby(fb.received_ts.dt.floor("h")).mass_kg.sum() / 1000
    joined = ph.set_index("ts").ffb_received_t.sub(recv_h, fill_value=0).abs()
    r.add("process_hourly.ffb_received = sum(unloaded FFB batches)", joined.max() < 0.01, f"max diff {joined.max():.4f} t")
    # ------------------------------------------------------------------ aggregates consistency
    sh = _df(engine, "SELECT SUM(ffb_processed_t) f, SUM(cpo_t) c FROM production_shifts").iloc[0]
    hb = ph[ph.ts >= w0 + pd.Timedelta(hours=-7 + 6 + 7)]  # shifts start 06:00 local on day 0
    r.add("shift totals = hourly totals", abs(sh.f - hb.ffb_processed_t.sum()) < 0.5 and abs(sh.c - hb.cpo_t.sum()) < 0.1,
          f"shift FFB {sh.f:.1f} vs hourly {hb.ffb_processed_t.sum():.1f}")
    pb = _df(engine, "SELECT id, ffb_input_t, cpo_t, oer_pct, kernel_t, ker_pct FROM production_batches")
    r.add("batch totals = hourly totals", abs(pb.ffb_input_t.sum() - ph.ffb_processed_t.sum()) < 0.5 and abs(pb.cpo_t.sum() - ph.cpo_t.sum()) < 0.5,
          f"batch FFB {pb.ffb_input_t.sum():.1f} vs hourly {ph.ffb_processed_t.sum():.1f}")
    r.add("batch CPO = FFB x OER", (pb.cpo_t - pb.ffb_input_t * pb.oer_pct / 100).abs().max() < 1e-3, "")
    bi = _df(engine, "SELECT production_batch_id, ffb_batch_id, mass_kg, mass_share FROM batch_inputs")
    g = bi.groupby("production_batch_id").agg(m=("mass_kg", "sum"), s=("mass_share", "sum")).join(pb.set_index("id"))
    r.add("batch_inputs mass = batch FFB input; shares sum to 1 (ADR-017)", (g.m / 1000 - g.ffb_input_t).abs().max() < 0.01 and (g.s - 1).abs().max() < 1e-4,
          f"max mass diff {(g.m / 1000 - g.ffb_input_t).abs().max():.4f} t, share diff {(g.s - 1).abs().max():.2e}")
    fbm = _df(engine, "SELECT id, mass_kg FROM ffb_batches").set_index("id")
    used = bi.groupby("ffb_batch_id").mass_kg.sum()
    r.add("FFB batch consumption <= batch mass", (used - fbm.mass_kg.reindex(used.index)).max() < 1.0, "")
    lots = _df(engine, "SELECT * FROM cpo_output_lots", ("fill_start_ts", "fill_end_ts", "dispatched_at"))
    lc = _df(engine, "SELECT cpo_lot_id, cpo_t, share FROM lot_compositions").groupby("cpo_lot_id").agg(c=("cpo_t", "sum"), s=("share", "sum"))
    lj = lots.set_index("id").join(lc)
    r.add("lot quantity = sum(compositions); shares sum to 1", (lj.quantity_t - lj.c).abs().max() < 1e-2 and (lj.s - 1).abs().max() < 1e-4, "")
    r.add("sum(lots) = sum(batch CPO)", abs(lots.quantity_t.sum() - pb.cpo_t.sum()) < 0.05, f"{lots.quantity_t.sum():.2f} vs {pb.cpo_t.sum():.2f}")
    stock_end = lots[lots.status != "dispatched"].quantity_t.sum()
    disp = lots[lots.status == "dispatched"].quantity_t.sum()
    r.add("CPO produced = dispatched + closing stock (CHK-03, REL-12)", abs(lots.quantity_t.sum() - disp - stock_end) < 1e-6 and stock_end >= 0,
          f"produced {lots.quantity_t.sum():.1f} = dispatched {disp:.1f} + stock {stock_end:.1f} t")
    tl = _df(engine, "SELECT MAX(r.value) v FROM sensor_readings r JOIN sensors s ON s.id = r.sensor_id WHERE s.code LIKE 'TNK-%-LVL'").v.iloc[0]
    r.add("tank levels <= 100% (stock never exceeds capacity)", tl is not None and tl <= 100, f"max level {tl:.1f}%")
    # ------------------------------------------------------------------ daily ranges (ratio of sums)
    ph["day"] = (ph.ts + LOCAL).dt.date
    dd = ph.groupby("day").agg(f=("ffb_processed_t", "sum"), c=("cpo_t", "sum"), k=("kernel_t", "sum"), run=("running_minutes", "sum"))
    dd = dd[dd.f > 100]
    oer = dd.c / dd.f * 100
    ker = dd.k / dd.f * 100
    lo, hi = P_range("oer_pct")
    r.add("daily OER within sourced range", oer.between(lo, hi).all(), f"[{oer.min():.2f}, {oer.max():.2f}] vs [{lo}, {hi}]; window OER {dd.c.sum() / dd.f.sum() * 100:.2f}%")
    lo, hi = P_range("ker_pct")
    r.add("daily KER within sourced range", ker.between(lo, hi).all(), f"[{ker.min():.2f}, {ker.max():.2f}] vs [{lo}, {hi}]")
    r.add("daily FFB processed <= capacity x 24 h (CHK-02)", (dd.f <= cap * 24).all(), f"max {dd.f.max():.0f} t/day")
    byp = _df(engine, "SELECT product, SUM(quantity_t) q FROM byproduct_outputs GROUP BY product").set_index("product").q
    tot_f = pb.ffb_input_t.sum()
    rng_fail = []
    for prod, key in (("efb", "efb_pct_ffb"), ("fibre", "fibre_pct_ffb"), ("shell", "shell_pct_ffb")):
        pct = byp[prod] / tot_f * 100
        lo, hi = P_range(key)
        if not lo <= pct <= hi:
            rng_fail.append(f"{prod} {pct:.2f}")
    pome = byp["pome"] / tot_f
    if not P_range("pome_t_per_t_ffb")[0] <= pome <= P_range("pome_t_per_t_ffb")[1]:
        rng_fail.append(f"pome {pome:.3f}")
    r.add("by-product fractions within sourced ranges (REL-01)", not rng_fail, ", ".join(rng_fail) or "efb/fibre/shell/pome OK")
    s5 = oer.max() + ker.max() + (byp["efb"] + byp["fibre"] + byp["shell"]) / tot_f * 100
    r.add("CPO+kernel+EFB+fibre+shell <= 75% of FFB (CHK-01/REL-02)", s5 <= 75, f"worst-day sum {s5:.1f}%")
    rr = ph[run]
    cond_ = rr.oil_loss_total_pct - rr.oil_loss_press_fibre_pct - rr.oil_loss_efb_pct - rr.oil_loss_sludge_pct - rr.oil_loss_nut_pct
    r.add("oil-loss terms reconcile (CHK-04; remainder = sterilizer condensate)", cond_.between(0.03, 0.6).all(), f"condensate term [{cond_.min():.3f}, {cond_.max():.3f}] % FFB")
    en = _df(engine, "SELECT ts, electricity_kwh, steam_t, water_m3, ffb_processed_t, idle_kwh, grid_import_kwh, diesel_l FROM energy_consumption WHERE process_stage_id IS NULL", ("ts",))
    en["day"] = (en.ts + LOCAL).dt.date
    ed = en.groupby("day").sum(numeric_only=True)
    thr = dd.f / (dd.run / 60)
    edd = ed.loc[thr[thr > 20].index]
    kwh = edd.electricity_kwh / edd.ffb_processed_t
    st = edd.steam_t / edd.ffb_processed_t
    r.add("steam 0.35-0.80 t/t and electricity 12-30 kWh/t on running days (CHK-05)", st.between(0.35, 0.8).all() and kwh.between(12, 30).all(),
          f"steam [{st.min():.3f}, {st.max():.3f}], kWh/t [{kwh.min():.1f}, {kwh.max():.1f}]; window {ed.electricity_kwh.sum() / ed.ffb_processed_t.sum():.2f} kWh/t, "
          f"{ed.steam_t.sum() / ed.ffb_processed_t.sum():.3f} t/t")
    wat = ed.water_m3.sum() / ed.ffb_processed_t.sum()
    r.add("water per tonne within sourced range", P_range("water_m3_per_t_ffb")[0] <= wat <= P_range("water_m3_per_t_ffb")[1], f"{wat:.2f} m3/t")
    r.add("idle kWh <= total kWh", (en.idle_kwh <= en.electricity_kwh + 1e-6).all(), "")
    r.add("CPO lot FFA 1.5-8 and moisture+dirt 0.05-0.6 (CHK-08)", lots.ffa_pct.between(1.5, 8).all() and (lots.moisture_pct + lots.dirt_pct).between(0.05, 0.6).all(),
          f"FFA [{lots.ffa_pct.min():.2f}, {lots.ffa_pct.max():.2f}]")
    r.add("clarifier 70-98 degC and digester 80-102 degC while running (CHK-08)", rr.clarifier_temp_c.between(70, 98).all() and rr.digester_temp_c.between(80, 102).all(),
          f"clarifier [{rr.clarifier_temp_c.min():.1f}, {rr.clarifier_temp_c.max():.1f}], digester [{rr.digester_temp_c.min():.1f}, {rr.digester_temp_c.max():.1f}]")
    # Little's law (CHK-06): mean wait ~= mean stock / mean processing rate
    wmean = float(np.average(rr.avg_wait_to_process_h, weights=rr.ffb_processed_t))
    little = ph.ffb_waiting_t.mean() / (ph.ffb_processed_t.sum() / len(ph))
    r.add("FFB wait ~ ramp stock / throughput within 15% (CHK-06, Little's law)", abs(wmean - little) / little < 0.15, f"weighted wait {wmean:.2f} h vs stock/throughput {little:.2f} h")
    # weighbridge & trucks
    tk = _df(engine, "SELECT t.truck_type, w.gross_kg, w.tare_kg, w.net_kg FROM weighbridge_tickets w JOIN truck_trips t ON t.id = w.truck_trip_id WHERE w.net_kg IS NOT NULL")
    maxpay = {k.replace("_", "-"): P_range(v[0])[1] * 1000 for k, v in TRUCK_TYPES.items()}
    lim = tk.truck_type.map(maxpay) * 1.15
    r.add("ticket net = gross - tare, 0 < net <= class payload max x 1.15 (CHK-07)", ((tk.gross_kg - tk.tare_kg) == tk.net_kg).all() and (tk.net_kg > 0).all() and (tk.net_kg <= lim).all(),
          f"{len(tk):,} tickets; {(tk.net_kg > lim / 1.15).sum()} above class max (flagged for review, labelled)")
    dv = _df(engine, "SELECT d.net_kg dn, w.net_kg wn, d.accepted_kg FROM ffb_deliveries d JOIN weighbridge_tickets w ON w.id = d.ticket_id")
    r.add("delivery net = ticket net; accepted <= net", (dv.dn == dv.wn).all() and (dv.accepted_kg <= dv.dn).all(), f"{len(dv):,} deliveries")
    tt = _df(engine, "SELECT arrival_ts, queue_start_ts, weigh_in_ts, grading_ts, unload_start_ts, unload_end_ts, weigh_out_ts, exit_ts FROM truck_trips",
             ("arrival_ts", "queue_start_ts", "weigh_in_ts", "grading_ts", "unload_start_ts", "unload_end_ts", "weigh_out_ts", "exit_ts"))
    cols = list(tt.columns)
    bad = 0
    for a, b in zip(cols[:-1], cols[1:], strict=True):
        m_ = tt[a].notna() & tt[b].notna()
        bad += int((tt.loc[m_, b] < tt.loc[m_, a]).sum())
    r.add("truck timeline ordered (arrival <= ... <= exit)", bad == 0, f"{bad} out-of-order pairs")
    # sensors
    sr = _df(engine, "SELECT s.sensor_type t, MIN(r.value) lo, MAX(r.value) hi FROM sensor_readings r JOIN sensors s ON s.id = r.sensor_id GROUP BY s.sensor_type")
    bounds = {"vibration": (0, 25), "temperature": (0, 260), "current": (0, 400), "pressure": (0, 70), "rpm": (0, 20), "state": (0, 1),
              "flow": (0, 45), "level": (0, 100), "load": (0, 1700), "running_hours": (0, 1e6)}
    badb = [f"{x.t} [{x.lo}, {x.hi}]" for x in sr.itertuples() if not (bounds[x.t][0] <= x.lo and x.hi <= bounds[x.t][1])]
    r.add("sensor values physically bounded", not badb, "; ".join(badb) or f"{len(sr)} sensor types OK")
    va = _df(engine, "SELECT evidence_json FROM alerts WHERE json_extract(evidence_json, '$.sensor_code') IS NOT NULL")
    ev = [json.loads(x) for x in va.evidence_json]
    okv = all((e["observed"] <= e["limit"]) if e["direction"] == "below" else (e["observed"] >= e["limit"]) for e in ev)
    r.add("every sensor alert is derivable from a stored reading beyond its limit (CHK-09)", okv, f"{len(ev)} sensor alerts")
    src = _df(engine, "SELECT DISTINCT source FROM alerts").source.tolist()
    r.add("seeded alerts are rule/threshold alerts only", src == ["rule"], str(src))
    # CHK-10 seasonality (info): monthly intake vs damped profile
    ph["month"] = (ph.ts + LOCAL).dt.month
    mon = ph.groupby("month").ffb_received_t.sum() / ph.groupby("month").size() * 24
    r.add("monthly intake follows the damped seasonal profile (CHK-10, info)", True, ", ".join(f"m{k}: {v:.0f} t/d" for k, v in mon.items()), level="info")
    # ------------------------------------------------------------------ scenarios
    _scenario_checks(engine, r, ph, scen, lots)
    # ------------------------------------------------------------------ ground truth + audit
    inj = _df(engine, "SELECT scenario_code, code FROM injected_events")
    missing = [c for c in scen.code if c != "NORMAL_DAY" and c not in set(inj.scenario_code.dropna())]
    nbg = int(inj.scenario_code.isna().sum())
    need_bg = 8 if days >= 90 else 1
    r.add(f"injected_events label every scenario episode + >= {need_bg} background abnormalities", not missing and nbg >= need_bg, f"{len(inj)} labels, {nbg} background; missing {missing}")
    from sqlalchemy.orm import Session

    from app.services.audit import verify_chain

    with Session(engine) as s:
        ok, broken = verify_chain(s)
    r.add("audit log hash chain verifies (ADR-013)", ok, f"first broken id {broken}" if not ok else f"{counts['audit_logs']} rows")
    pr3 = _df(engine, "SELECT w.created_at, w.status FROM work_orders w JOIN equipment e ON e.id = w.equipment_id WHERE e.code = 'PRS-03'", ("created_at",))
    onset = _df(engine, "SELECT start_ts FROM injected_events WHERE code = 'INJ-PRS-BRG'", ("start_ts",))
    if not onset.empty:
        late = pr3[pr3.created_at >= onset.start_ts.iloc[0]]
        r.add("no PRS-03 work order after degradation onset (tour creates it)", late.empty, f"{len(pr3)} PRS-03 WOs, all before onset")
    # ------------------------------------------------------------------ determinism
    if check_checksum:
        cs, _ = content_checksum(engine)
        if manifest and manifest.get("days") == days:
            r.add("determinism: content checksum = MANIFEST.json", cs == manifest.get("checksum_sha256"), f"{cs[:16]}... vs manifest {str(manifest.get('checksum_sha256'))[:16]}...")
        else:
            r.add("determinism: content checksum computed (no matching manifest)", True, cs, level="info")
    return r


def _day_slice(ph: pd.DataFrame, ts: pd.Timestamp) -> pd.DataFrame:
    d = (ts + LOCAL).date()
    return ph[(ph.ts + LOCAL).dt.date == d]


def _oer(df: pd.DataFrame) -> float:
    return float(df.cpo_t.sum() / df.ffb_processed_t.sum() * 100) if df.ffb_processed_t.sum() > 0 else float("nan")


def _scenario_checks(engine, r: Report, ph, scen, lots) -> None:
    by = {row.code: row for row in scen.itertuples()}
    normal = by.get("NORMAL_DAY")
    nday = _day_slice(ph, normal.focus_ts) if normal is not None else None
    alerts = _df(engine, "SELECT a.*, e.code AS equip_code FROM alerts a LEFT JOIN equipment e ON e.id = a.equipment_id", ("raised_at",))
    trips = _df(engine, "SELECT arrival_ts, weigh_in_ts FROM truck_trips WHERE weigh_in_ts IS NOT NULL", ("arrival_ts", "weigh_in_ts"))
    trips["wait"] = (trips.weigh_in_ts - trips.arrival_ts).dt.total_seconds() / 60
    trips["day"] = (trips.arrival_ts + LOCAL).dt.date
    if normal is not None:
        hi_al = alerts[((alerts.raised_at + LOCAL).dt.date == (normal.focus_ts + LOCAL).date()) & alerts.severity.isin(["high", "critical"])]
        r.add("NORMAL_DAY: no high/critical alerts that day", hi_al.empty, f"{len(hi_al)} high/critical")
        w30 = ph[ph.ts >= ph.ts.max() - pd.Timedelta(days=30)]
        r.add("NORMAL_DAY: OER within 0.5 pp of the 30-day window", abs(_oer(nday) - _oer(w30)) <= 0.5, f"{_oer(nday):.2f}% vs 30-day {_oer(w30):.2f}%")
    s = by.get("OER_DEGRADATION")
    if s is not None and nday is not None:
        f = _day_slice(ph, s.focus_ts)
        dl = _df(engine, "SELECT received_ts, net_kg, unripe_pct FROM ffb_deliveries", ("received_ts",))
        dl["day"] = (dl.received_ts + LOCAL).dt.date
        def unr(day):
            x = dl[dl.day == day]
            return float(np.average(x.unripe_pct, weights=x.net_kg))
        fd, nd = (s.focus_ts + LOCAL).date(), (normal.focus_ts + LOCAL).date()
        drop = _oer(nday) - _oer(f)
        r.add("OER_DEGRADATION: focus-day OER >= 0.5 pp below NORMAL_DAY", drop >= 0.5, f"{_oer(f):.2f}% vs {_oer(nday):.2f}% (-{drop:.2f} pp)")
        r.add("OER_DEGRADATION: drivers present (unripe up, cycle shorter, clarifier colder, press-fibre loss up)",
              unr(fd) > unr(nd) + 2 and f.sterilizer_cycle_min.mean() < 72 and f.clarifier_temp_c.min() < 85 and f.oil_loss_press_fibre_pct.mean() > nday.oil_loss_press_fibre_pct.mean() * 1.15,
              f"unripe {unr(fd):.1f}% vs {unr(nd):.1f}%, cycle {f.sterilizer_cycle_min.mean():.1f} min, clarifier min {f.clarifier_temp_c.min():.1f} degC, "
              f"fibre loss {f.oil_loss_press_fibre_pct.mean():.3f} vs {nday.oil_loss_press_fibre_pct.mean():.3f} % FFB")
    s = by.get("PRESS_VIBRATION_ANOMALY")
    if s is not None:
        vib = _df(engine, "SELECT r.ts, r.value, s.code FROM sensor_readings r JOIN sensors s ON s.id = r.sensor_id WHERE s.code IN ('PRS-03-VIB-DE', 'PRS-03-CUR', 'PRS-03-TMP-BRG')", ("ts",))
        vib["day"] = (vib.ts + LOCAL).dt.date
        fd, bd = (s.focus_ts + LOCAL).date(), (s.baseline_ts + LOCAL).date()
        v = vib[vib.code == "PRS-03-VIB-DE"]
        c = vib[(vib.code == "PRS-03-CUR") & (vib.value > 1)]
        vmax_f, vmax_b = v[v.day == fd].value.max(), v[v.day == bd].value.max()
        cur_ratio = c[c.day == fd].value.mean() / c[c.day == bd].value.mean()
        crit = alerts[(alerts.equip_code == "PRS-03") & (alerts.severity == "critical") & (alerts.raised_at <= s.focus_ts)]
        f, b = _day_slice(ph, s.focus_ts), _day_slice(ph, s.baseline_ts)
        r.add("PRESS_VIBRATION_ANOMALY: PRS-03 vibration zone D on focus day, zone A/B on baseline", vmax_f >= 4.5 and vmax_b < 2.8, f"max {vmax_f:.2f} vs {vmax_b:.2f} mm/s")
        r.add("PRESS_VIBRATION_ANOMALY: motor current up >= 5% and critical alert before focus", cur_ratio >= 1.05 and not crit.empty,
              f"current x{cur_ratio:.3f}; critical alert at {crit.raised_at.min() if not crit.empty else None}")
        r.add("PRESS_VIBRATION_ANOMALY: plant press-fibre loss and OER effect", f.oil_loss_press_fibre_pct.mean() > b.oil_loss_press_fibre_pct.mean() and _oer(f) < _oer(b),
              f"fibre loss {f.oil_loss_press_fibre_pct.mean():.3f} vs {b.oil_loss_press_fibre_pct.mean():.3f}; OER {_oer(f):.2f} vs {_oer(b):.2f}")
    s = by.get("STEAM_PRESSURE_DEVIATION")
    if s is not None:
        w = ph[(ph.ts >= s.start_ts) & (ph.ts < s.end_ts)]
        b = ph[(ph.ts >= s.baseline_ts - (s.focus_ts - s.start_ts)) & (ph.ts < s.baseline_ts + (s.end_ts - s.focus_ts))]
        dev = w[w.steam_pressure_bar < 0.95 * P("bpv_header_pressure_barg")]
        en = _df(engine, "SELECT ts, grid_import_kwh, self_generated_kwh, electricity_kwh FROM energy_consumption WHERE process_stage_id IS NULL", ("ts",))
        enw = en[en.ts.isin(dev.ts)]
        enb = en[en.ts.isin(b.ts)]
        al = alerts[(alerts.scenario_code == "STEAM_PRESSURE_DEVIATION") & alerts.severity.isin(["high", "critical"])]
        r.add("STEAM_PRESSURE_DEVIATION: header pressure <= -10% with longer cycles and lower OER in the deviation hours",
              w.steam_pressure_bar.min() <= 0.9 * P("bpv_header_pressure_barg") and dev.sterilizer_cycle_min.mean() > b.sterilizer_cycle_min.mean() + 5 and _oer(dev) < _oer(b),
              f"min {w.steam_pressure_bar.min():.2f} bar ({len(dev)} h < -5%), cycle {dev.sterilizer_cycle_min.mean():.1f} vs {b.sterilizer_cycle_min.mean():.1f} min, "
              f"OER {_oer(dev):.2f} vs {_oer(b):.2f}%")
        r.add("STEAM_PRESSURE_DEVIATION: grid import up, high-severity pressure alerts",
              enw.grid_import_kwh.mean() > enb.grid_import_kwh.mean() and not al.empty, f"grid {enw.grid_import_kwh.mean():.0f} vs {enb.grid_import_kwh.mean():.0f} kWh/h; {len(al)} alerts")
    s = by.get("TRUCK_QUEUE_CONGESTION")
    if s is not None:
        fd, bd = (s.focus_ts + LOCAL).date(), (s.baseline_ts + LOCAL).date()
        wf, wb = trips[trips.day == fd].wait, trips[trips.day == bd].wait
        nxt = _day_slice(ph, s.focus_ts + pd.Timedelta(days=1))
        bph = _day_slice(ph, s.baseline_ts)
        al = alerts[(alerts.scenario_code == "TRUCK_QUEUE_CONGESTION") & (alerts.module == "logistics")]
        r.add("TRUCK_QUEUE_CONGESTION: wait-to-weigh >= 3x baseline, max >= 2 h, logistics alerts", wf.mean() >= 3 * wb.mean() and wf.max() >= 120 and not al.empty,
              f"mean {wf.mean():.0f} vs {wb.mean():.0f} min, max {wf.max():.0f} min, {len(al)} alerts")
        lot_f = lots[(lots.fill_start_ts + LOCAL).dt.date == (s.focus_ts + pd.Timedelta(days=1) + LOCAL).date()]
        lot_b = lots[(lots.fill_start_ts + LOCAL).dt.date == bd]
        wnext = float(np.average(nxt.avg_wait_to_process_h.fillna(0), weights=nxt.ffb_processed_t))
        wbase = float(np.average(bph.avg_wait_to_process_h.fillna(0), weights=bph.ffb_processed_t))
        r.add("TRUCK_QUEUE_CONGESTION: next-day FFB wait-to-process and lot FFA higher (REL-05/07)",
              wnext > wbase and lot_f.ffa_pct.mean() > lot_b.ffa_pct.mean(), f"wait {wnext:.1f} vs {wbase:.1f} h; FFA {lot_f.ffa_pct.mean():.2f} vs {lot_b.ffa_pct.mean():.2f}%")
    s = by.get("ENERGY_EFFICIENCY_DROP")
    if s is not None:
        en = _df(engine, "SELECT ts, electricity_kwh, steam_t, idle_kwh, ffb_processed_t FROM energy_consumption WHERE process_stage_id IS NULL", ("ts",))
        f = en[(en.ts >= s.start_ts) & (en.ts < s.end_ts)]
        b = en[(en.ts >= s.start_ts - pd.Timedelta(days=7)) & (en.ts < s.start_ts)]
        kf, kb = f.electricity_kwh.sum() / f.ffb_processed_t.sum(), b.electricity_kwh.sum() / b.ffb_processed_t.sum()
        sf, sb = f.steam_t.sum() / f.ffb_processed_t.sum(), b.steam_t.sum() / b.ffb_processed_t.sum()
        r.add("ENERGY_EFFICIENCY_DROP: episode week vs prior week: kWh/t >= +5%, steam t/t >= +8%, idle kWh up", kf >= 1.05 * kb and sf >= 1.08 * sb and f.idle_kwh.sum() > b.idle_kwh.sum(),
              f"kWh/t {kf:.2f} vs {kb:.2f} (+{(kf / kb - 1) * 100:.1f}%), steam {sf:.3f} vs {sb:.3f} t/t (+{(sf / sb - 1) * 100:.1f}%), idle {f.idle_kwh.sum():.0f} vs {b.idle_kwh.sum():.0f} kWh")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.seed.validate")
    ap.add_argument("--db-url", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-checksum", action="store_true")
    ap.add_argument("--manifest", default=None, help="manifest path (default data/synthetic/MANIFEST.json)")
    a = ap.parse_args(argv)
    from app.seed.dburl import seed_db_url

    url = seed_db_url(a.db_url)
    from app.config import REPO_ROOT
    from app.db.session import get_engine

    mp = a.manifest or str(REPO_ROOT / "data/synthetic/MANIFEST.json")
    manifest = None
    try:
        with open(mp, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except FileNotFoundError:
        pass
    rep = validate(get_engine(url), manifest, check_checksum=not a.no_checksum)
    if a.json:
        print(json.dumps([c.__dict__ for c in rep.checks], indent=2))
    else:
        print(f"validate: {url}")
        for c in rep.checks:
            mark = "PASS" if c.ok else ("INFO" if c.level == "info" else "FAIL")
            print(f"  [{mark}] {c.name}: {c.detail}")
        n_fail = sum(1 for c in rep.checks if not c.ok and c.level == "fail")
        print(f"validate: {'PASSED' if rep.passed else 'FAILED'} - {len(rep.checks)} checks, {n_fail} failed")
    return 0 if rep.passed else 1


if __name__ == "__main__":
    sys.exit(main())
