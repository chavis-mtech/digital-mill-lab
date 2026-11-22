"""Rule/threshold alerts derived from the stored readings, like a plant alarm system (NOT from ML).

Sensor rules: value beyond the sensor's warn/crit limit (low_is_bad for pressures/temperatures that must stay up)
for >= 3 consecutive samples while the equipment (or, for process tags, the mill) is running -> alert; repeated
firings of the same (sensor, level) within 12 h are merged into one alert (KPI_DEFINITIONS 4.8 de-duplication);
resolved after 6 consecutive samples back inside the limit. Process rules: 4-hour OER vs the trailing 28-day
baseline (KPI_DEFINITIONS 4.4 thresholds), daily energy/steam intensity (KPI_DEFINITIONS 5), queue length and
truck wait, FFB wait-to-process, CPO lot FFA. Schema enum has 'rule' (not 'rule_threshold'): we store source='rule'
and evidence_json.rule_type='rule_threshold' (see docs/status/data-engine.md, Requests).
"""

from __future__ import annotations

import json

import numpy as np

from app.seed.logistics import queue_lengths

SCENARIO_LINKS = {
    "PRESS_VIBRATION_ANOMALY": ({"PRS-03"}, {"production"}),
    "STEAM_PRESSURE_DEVIATION": ({"FWP-01", "BLR-01", "TG-01", "DIG-01", "DIG-02", "DIG-03", "DIG-04", "STR-01", "STR-02", "STR-03", "STR-04", "STR-05"}, {"production", "energy"}),
    "OER_DEGRADATION": ({"CLR-01", "PRS-01", "PRS-02", "PRS-03", "PRS-04"}, {"production", "quality"}),
    "TRUCK_QUEUE_CONGESTION": ({"WB-01", "WB-02", "LR-CNV-01"}, {"logistics", "production", "quality"}),
    "ENERGY_EFFICIENCY_DROP": ({"BLR-01", "BLR-FAN-01", "FWP-01"}, {"energy"}),
}

MODULE_OF_KIND = {"vib": "maintenance", "brg_temp": "maintenance", "current": "maintenance", "cone": "maintenance",
                  "drum_p": "production", "hdr_p": "production", "dig_temp": "production", "clr_temp": "production",
                  "ves_p": "production", "tank_level": "production", "tank_temp": "quality", "flue_temp": "energy",
                  "steam_flow": "energy", "tg_load": "energy"}
WARN_SEV = {"vib": "medium", "brg_temp": "high", "current": "medium", "drum_p": "high", "hdr_p": "high", "dig_temp": "medium",
            "clr_temp": "medium", "flue_temp": "medium"}


def _episodes(cond: np.ndarray, t: np.ndarray, merge_gap_min: float, debounce: int, clear_n: int, t_end: float):
    """Return [(raise_idx, last_true_idx, resolved_time or None)]."""
    idx = np.flatnonzero(cond)
    if idx.size == 0:
        return []
    groups = []
    start = 0
    for k in range(1, idx.size + 1):
        if k == idx.size or t[idx[k]] - t[idx[k - 1]] > merge_gap_min:
            groups.append(idx[start:k])
            start = k
    out = []
    dt = float(np.median(np.diff(t))) if t.size > 1 else 60.0
    for g in groups:
        raise_i = None
        for j in range(g.size - debounce + 1):
            if g[j + debounce - 1] - g[j] == debounce - 1:
                raise_i = int(g[j + debounce - 1])
                break
        if raise_i is None:
            continue
        last = int(g[-1])
        res = t[last] + clear_n * dt
        out.append((raise_i, last, res if res < t_end and last + clear_n < t.size else None))
    return out


class AlertBuilder:
    def __init__(self, core, ids) -> None:
        self.core, self.ids = core, ids
        self.rows: list[dict] = []

    def scenario_for(self, t_min: float, equip_code: str | None, module: str) -> str | None:
        for s in self.core.scenarios:
            if s.code not in SCENARIO_LINKS:
                continue
            lo, hi = s.start, s.end
            if s.code == "PRESS_VIBRATION_ANOMALY":
                lo = s.start - 3 * 1440  # warning alerts precede the visible window
            if not (lo <= t_min < hi):
                continue
            eqs, mods_ = SCENARIO_LINKS[s.code]
            if (equip_code and equip_code in eqs) or (equip_code is None and module in mods_):
                return s.code
        return None

    def add(self, t_raise, t_res, module, severity, title, message, evidence, equip_code=None, stage_code=None, impact=None, supplier_id=None, truck_trip_id=None):
        tb = self.core.tb
        n = len(self.rows) + 1
        self.rows.append({
            "id": n, "code": f"ALR-{tb.date_of(t_raise):%Y%m%d}-{n:04d}", "source": "rule", "module": module, "severity": severity,
            "status": "resolved" if t_res is not None else "new", "title": title, "message": message, "raised_at": tb.ts(t_raise),
            "resolved_at": tb.ts(t_res) if t_res is not None else None, "facility_id": self.ids["facility"],
            "equipment_id": self.ids["equip"].get(equip_code) if equip_code else None,
            "process_stage_id": self.ids["stage"].get(stage_code) if stage_code else None, "anomaly_event_id": None, "recommendation_id": None,
            "supplier_id": supplier_id, "truck_trip_id": truck_trip_id,
            "business_impact_json": json.dumps(impact, sort_keys=True) if impact else None,
            "evidence_json": json.dumps({"rule_type": "rule_threshold", **evidence}, sort_keys=True, default=float),
            "scenario_code": self.scenario_for(t_raise, equip_code, module), "data_kind": "synthetic",
            "_t": t_raise, "_equip": equip_code,
        })


def build_alerts(core, ids, sensors, series, prod, eb) -> list[dict]:
    tb, m = core.tb, core.mill
    ab = AlertBuilder(core, ids)
    T_END = tb.minutes
    for sp in sensors:
        if sp.warn is None or sp.kind not in MODULE_OF_KIND:
            continue
        s = series[sp.id]
        t, v, mask = s["t"], s["v"], s["alarm_mask"]
        good = s["q"] == 0
        for level, lim, sev in (("warn", sp.warn, WARN_SEV.get(sp.kind, "medium")), ("crit", sp.crit, "critical")):
            if lim is None:
                continue
            cond = ((v <= lim) if sp.low_is_bad else (v >= lim)) & mask & good
            for ri, li, res in _episodes(cond, t, 12 * 60, 3, 6, T_END):
                seg = v[ri:li + 1][mask[ri:li + 1]]
                worst = float(seg.min() if sp.low_is_bad else seg.max()) if seg.size else float(v[ri])
                dirn = "below" if sp.low_is_bad else "above"
                if level == "crit":
                    lvl = "LOW-LOW (critical)" if sp.low_is_bad else "HIGH-HIGH (critical)"
                else:
                    lvl = "LOW" if sp.low_is_bad else "HIGH"
                title = f"{sp.code} {lvl}: {sp.name}"
                msg = (f"{sp.code} read {v[ri]:.2f} {sp.unit}, {dirn} the {level} limit {lim} {sp.unit} for 3 consecutive samples "
                       f"(normal {sp.normal_min}-{sp.normal_max}). Worst value in the episode {worst:.2f}. Threshold rule only - "
                       f"verify on site; an alert is not a diagnosis.")
                ab.add(t[ri], res, MODULE_OF_KIND[sp.kind], sev, title, msg,
                       {"rule": f"{sp.kind}_{level}", "sensor_code": sp.code, "observed": round(float(v[ri]), 3), "worst": round(worst, 3),
                        "limit": lim, "direction": dirn, "normal_range": [sp.normal_min, sp.normal_max], "debounce_samples": 3,
                        "sampling_seconds": sp.sampling_s},
                       equip_code=sp.equip.code, stage_code=sp.equip.stage)
    # ---- production: 4-hour OER vs trailing 28-day baseline (ratio of sums)
    proc, cpo = m["processed_t"], m["cpo_t"]
    D = tb.days
    dproc = proc.reshape(D, 24).sum(1)
    dcpo = cpo.reshape(D, 24).sum(1)
    H = tb.hours
    cond_m = np.zeros(H, bool)
    cond_h = np.zeros(H, bool)
    gap = np.zeros(H)
    base = np.full(H, np.nan)
    for h in range(H):
        d = h // 24
        lo = max(0, d - 28)
        if d - lo < 7:
            continue
        b = dcpo[lo:d].sum() / max(dproc[lo:d].sum(), 1) * 100
        p4, c4 = proc[max(0, h - 3):h + 1].sum(), cpo[max(0, h - 3):h + 1].sum()
        if p4 < 60 or proc[h] <= 0:
            continue
        o4 = c4 / p4 * 100
        base[h] = b
        gap[h] = b - o4
        cond_m[h] = gap[h] > 0.8
        cond_h[h] = gap[h] > 1.3
    th = (np.arange(H) + 1) * 60.0
    for cond, sev, label in ((cond_m, "medium", "more than 0.8 pp"), (cond_h, "high", "more than 1.3 pp")):
        for ri, li, res in _episodes(cond, th, 6 * 60, 2, 3, T_END):
            lost = float(np.sum(proc[ri:li + 1] * np.maximum(gap[ri:li + 1], 0) / 100))
            ab.add(th[ri], res, "production", sev, f"OER below baseline ({label})",
                   f"4-hour OER {base[ri] - gap[ri]:.2f}% vs trailing 28-day baseline {base[ri]:.2f}% (gap {gap[ri]:.2f} pp). "
                   "Check FFB ripeness mix, sterilizer cycles, press and clarifier losses. Possible contributing factors, not a proven cause.",
                   {"rule": f"oer_4h_gap_{sev}", "observed_oer_pct": round(float(base[ri] - gap[ri]), 3), "baseline_oer_pct": round(float(base[ri]), 3),
                    "gap_pp": round(float(gap[ri]), 3), "window_h": 4},
                   impact={"kind": "what_if", "estimated_lost_cpo_t": round(lost, 2),
                           "assumptions": ["lost CPO = FFB processed x (baseline OER - observed OER) over the alert hours", "illustrative, synthetic data"]})
    # ---- production: FFB wait-to-process
    wait = np.nan_to_num(m["avg_wait_h"], nan=0.0)
    for ri, _li, res in _episodes(wait > 12, th, 6 * 60, 2, 3, T_END):
        ab.add(th[ri], res, "production", "medium", "FFB wait-to-process above 12 h",
               f"Tonnage-weighted FFB wait before sterilization reached {wait[ri]:.1f} h (amber > 12 h). Ramp stock {m['waiting_t'][ri]:.0f} t.",
               {"rule": "ffb_wait_gt_12h", "observed_h": round(float(wait[ri]), 2), "limit_h": 12, "ramp_stock_t": round(float(m["waiting_t"][ri]), 1)},
               stage_code="FFB_RECEPTION")
    # ---- energy: daily intensity (raised at the end of the business day)
    el = eb["elec"].reshape(D, 24).sum(1)
    stm = m["boiler_steam_t"].reshape(D, 24).sum(1)
    tday = (np.arange(D) + 1) * 1440.0 - 10
    for arr, unit, amber, red, name in ((el, "kWh/t", 18.5, 21.0, "Electricity per tonne FFB"), (stm, "t/t", 0.55, 0.62, "Steam per tonne FFB")):
        inten = np.divide(arr, dproc, out=np.zeros(D), where=dproc > 0)
        okd = dproc >= 1000  # near-nominal load only: fixed loads inflate intensity on low-throughput days (KPI_DEFINITIONS 4.6)
        for cond, sev, lim in ((okd & (inten > amber), "medium", amber), (okd & (inten > red), "high", red)):
            for ri, _li, res in _episodes(cond, tday, 1440 * 1.5, 1, 1, T_END):
                ab.add(tday[ri], res, "energy", sev, f"{name} above {lim} {unit}",
                       f"{name} for business day {tb.day_date(ri)} = {inten[ri]:.3f} {unit} (limit {lim}). Compare with the expected intensity at the same throughput before concluding.",
                       {"rule": f"daily_{'kwh' if unit == 'kWh/t' else 'steam'}_per_t_{sev}", "observed": round(float(inten[ri]), 4), "limit": lim,
                        "ffb_processed_t": round(float(dproc[ri]), 1)},
                       stage_code="BOILER_STEAM" if unit == "t/t" else "POWER")
    # ---- logistics: queue length and truck waiting time (flow problem, never an accusation)
    grid = np.arange(0, tb.minutes, 10.0)
    ql = queue_lengths(core.trucks, grid)
    for lim, sev in ((12, "medium"), (25, "high")):
        for ri, li, res in _episodes(ql >= lim, grid, 3 * 60, 2, 3, T_END):
            ab.add(grid[ri], res, "logistics", sev, f"Truck queue at the weighbridge >= {lim}",
                   f"{int(ql[ri])} trucks waiting for weigh-in (peak {int(ql[ri:li + 1].max())}). Flow problem to analyse - not an accusation of any supplier or driver.",
                   {"rule": f"queue_len_ge_{lim}", "observed": int(ql[ri]), "peak": int(ql[ri:li + 1].max()), "limit": lim}, stage_code="FFB_RECEPTION")
    waits = [(t.weigh_in, t.weigh_in - t.arrival, t.idx) for t in core.trucks if t.weigh_in is not None]
    waits.sort()
    tw = np.array([w[0] for w in waits])
    long = np.array([w[1] > 60 for w in waits])
    for ri, li, res in _episodes(long, tw, 3 * 60, 1, 3, T_END):
        seg = [w[1] for w in waits[ri:li + 1]]
        ab.add(tw[ri], res, "logistics", "high", "Truck wait-to-weigh above 60 min",
               f"{sum(1 for x in seg if x > 60)} trucks waited more than 60 min before weigh-in (max {max(seg):.0f} min). Flow problem to analyse, never an accusation.",
               {"rule": "truck_wait_gt_60min", "observed_min": round(float(waits[ri][1]), 1), "max_min": round(float(max(seg)), 1), "limit_min": 60},
               stage_code="FFB_RECEPTION", truck_trip_id=waits[ri][2] + 1)
    # ---- quality: CPO lot FFA
    for lt in prod["_lots"]:
        if lt["ffa_pct"] is None:
            continue
        for lim, sev in ((4.0, "medium"), (5.0, "high")):
            if lt["ffa_pct"] > lim:
                d = lt["_day"]
                t_r = min((d + 1) * 1440.0 - 5, tb.minutes - 1)
                t_res = None
                if lt["dispatched_at"] is not None:
                    t_res = (lt["dispatched_at"] - tb.start_utc.replace(tzinfo=None)).total_seconds() / 60
                ab.add(t_r, t_res, "quality", sev, f"CPO lot FFA above {lim}%",
                       f"Lot {lt['code']} FFA {lt['ffa_pct']:.2f}% (spec max {5.0}%).", {"rule": f"lot_ffa_gt_{lim}", "observed": lt["ffa_pct"], "limit": lim, "lot": lt["code"]},
                       stage_code="CPO_STORAGE")
    rows = sorted(ab.rows, key=lambda r: (r["_t"], r["code"]))
    for i, r in enumerate(rows, start=1):
        r["id"] = i
        r["code"] = f"ALR-{tb.date_of(r['_t']):%Y%m%d}-{i:04d}"
    return rows
