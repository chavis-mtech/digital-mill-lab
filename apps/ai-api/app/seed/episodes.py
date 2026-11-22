"""Scenario schedule (ADR-011) and background abnormalities -> driver modifiers + ground-truth labels.

Episodes only set *drivers* (supplier quality, a pump's condition, a sterilizer cycle setpoint, a bearing's health,
an outage window, ...). Every observable effect (OER, throughput, losses, steam, energy, queues, FFA, alerts) is
computed downstream by the same model equations as normal operation (mill.py, logistics.py, energy.py, sensors.py).

All scenario dates are offsets from the anchor day A (= last day of the window), so a smaller test build keeps the
episodes that fit inside its window and drops the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.seed.assumptions import P
from app.seed.timebase import TimeBase

MIN_PER_DAY = 1440


@dataclass
class Injected:
    code: str
    scenario_code: str | None
    event_type: str
    domain: str  # production | equipment | energy | logistics | quality
    entity_type: str
    entity_code: str | None
    equipment_code: str | None
    stage_code: str | None
    start: float
    end: float
    magnitude: float | None
    params: dict
    notes: str


@dataclass
class ScenarioDef:
    code: str
    name_en: str
    name_th: str
    description: str
    start: float
    end: float
    focus: float
    baseline: float | None
    stage: str | None
    equipment_code: str | None
    effects: list[dict]


@dataclass
class Breakdown:
    code: str
    equipment_code: str
    start: float
    end: float
    impact: str  # plant | press | thresher | none
    unit_index: int | None
    event_type: str  # breakdown | corrective
    description: str
    scenario_code: str | None = None
    planned: bool = False


@dataclass
class SensorFault:
    sensor_code: str
    kind: str  # flatline | spike | dropout
    start: float
    end: float
    params: dict = field(default_factory=dict)


class Modifiers:
    def __init__(self, tb: TimeBase, n_sup: int, n_press: int) -> None:
        H, D = tb.hours, tb.days
        self.tb = tb
        self.t_mid = (np.arange(H) + 0.5) * 60.0
        self.intake_mult = np.ones(D)
        self.sharpen = np.ones(D)
        self.grading_mult = np.ones(D)
        self.unripe_shift = np.zeros((n_sup, D))
        self.h2m_shift = np.zeros((n_sup, D))
        self.ster_cycle = np.full(H, float(P("sterilizer_cycle_min")))
        self.boiler_cap = np.ones(H)
        self.steam_extra = np.zeros(H)
        self.boiler_eff_delta = np.zeros(H)
        self.clar_offset = np.zeros(H)
        self.press_wear = np.zeros(H)  # relative extra press-fibre oil loss on all presses (worn screws)
        self.idle_running = np.zeros(H, dtype=bool)
        self.rate_adj = np.zeros(H)
        self.press_sev = np.zeros((n_press, H))
        self.overlays: dict[str, dict[str, np.ndarray]] = {}
        self.flue_add = np.zeros(H)
        self.fan_mult = np.ones(H)
        self.fwp_mult = np.ones(H)
        self.misc_add_kw = np.zeros(H)
        self.wb_outages: list[tuple[int, float, float]] = []
        self.bay_outages: list[tuple[int, float, float]] = []
        self.wb_svc_mult = np.ones(H)
        self.quota = np.ones(D)  # supplier delivery quota set by the mill when the ramp is full (feedback, see build.py)
        self.quota_exempt: set[int] = set()
        self.noise_free_days: set[int] = set()
        self.plant_stop_min = np.zeros(H)
        self.planned_stop_min = np.zeros(H)
        self.cap_factor = np.ones(H)
        self.press_avail = np.ones((n_press, H))
        self.forced_rain: dict[int, float] = {}
        self.forced_dry: set[int] = set()
        self.sensor_faults: list[SensorFault] = []
        self.breakdowns: list[Breakdown] = []
        self.supplier_bad_days: list[tuple[int, int, float]] = []

    # ---- helpers -------------------------------------------------------------
    def trapezoid(self, s: float, ps: float, pe: float, e: float) -> np.ndarray:
        t = self.t_mid
        y = np.zeros_like(t)
        up = (t >= s) & (t < ps)
        y[up] = (t[up] - s) / max(ps - s, 1e-9)
        y[(t >= ps) & (t < pe)] = 1.0
        dn = (t >= pe) & (t < e)
        y[dn] = 1 - (t[dn] - pe) / max(e - pe, 1e-9)
        return y

    def power_curve(self, onset: float, peak: float, expo: float, end: float | None = None) -> np.ndarray:
        """Degradation severity 0..1: ((t - onset)/(peak - onset))^expo, held at 1 after peak, 0 after `end` (repair)."""
        t = self.t_mid
        y = np.clip((t - onset) / (peak - onset), 0, 1) ** expo
        if end is not None:
            y[t >= end] = 0.0
        return y

    def overlay(self, code: str) -> dict[str, np.ndarray]:
        H = self.tb.hours
        if code not in self.overlays:
            self.overlays[code] = {"vib_add": np.zeros(H), "temp_add": np.zeros(H), "cur_mult": np.ones(H)}
        return self.overlays[code]

    def add_stop(self, arr: np.ndarray, s: float, e: float) -> None:
        h0, h1 = int(s // 60), int(np.ceil(e / 60))
        for h in range(max(h0, 0), min(h1, self.tb.hours)):
            ov = min(e, (h + 1) * 60) - max(s, h * 60)
            if ov > 0:
                arr[h] += ov

    def hour_mask(self, s: float, e: float) -> np.ndarray:
        return (self.t_mid >= s) & (self.t_mid < e)


SCENARIO_NAMES = {
    "NORMAL_DAY": ("Normal operating day", "วันทำงานปกติ"),
    "OER_DEGRADATION": ("OER degradation (multi-driver)", "อัตราสกัดน้ำมัน (OER) ลดลงจากหลายปัจจัย"),
    "PRESS_VIBRATION_ANOMALY": ("Screw press PRS-03 bearing vibration anomaly", "ความสั่นสะเทือนผิดปกติของเครื่องหีบ PRS-03"),
    "STEAM_PRESSURE_DEVIATION": ("Steam pressure deviation (feed-water pump)", "แรงดันไอน้ำเบี่ยงเบน (ปั๊มน้ำป้อนหม้อไอน้ำ)"),
    "TRUCK_QUEUE_CONGESTION": ("Truck queue congestion at the weighbridge", "คิวรถบรรทุกแออัดที่ตาชั่ง"),
    "ENERGY_EFFICIENCY_DROP": ("Energy efficiency drop", "ประสิทธิภาพการใช้พลังงานลดลง"),
}


def _first_weekday_on_or_after(tb: TimeBase, d: int, weekday: int) -> int:
    while tb.weekday(d) != weekday:
        d += 1
    return d


def build_schedule(tb: TimeBase, rngs, suppliers, equip_codes: list[str]):
    """Returns (mods, scenarios, injected, protected_days)."""
    n_press = int(P("press_count"))
    mods = Modifiers(tb, len(suppliers), n_press)
    rng = rngs.get("episodes")
    A = tb.days - 1
    M = MIN_PER_DAY
    scen: list[ScenarioDef] = []
    inj: list[Injected] = []
    protected: set[int] = set()
    windows: list[tuple[float, float]] = []

    def day_ok(d: int) -> bool:
        return 0 <= d <= A

    def at(d: int, hh: float) -> float:
        return d * M + hh * 60

    def label(code, scn, etype, domain, etype_ent, ent, eq, stage, s, e, mag, params, notes):
        inj.append(Injected(code, scn, etype, domain, etype_ent, ent, eq, stage, s, e, mag, params, notes))

    sup_by_type = {}
    for i, sp in enumerate(suppliers):
        sup_by_type.setdefault(sp.stype, []).append(i)

    # ------------------------------------------------------------------ planned weekly stops (Sundays 05:00-13:00)
    stop_h = P("planned_stop_hours_per_week")
    for d in range(tb.days):
        if tb.weekday(d) == 6:
            s, e = at(d, 5), at(d, 5 + stop_h)
            mods.add_stop(mods.planned_stop_min, s, e)

    # ------------------------------------------------------------------ NORMAL_DAY (A-30)
    dn = A - 30
    if day_ok(dn):
        protected |= {dn - 1, dn, dn + 1}
        scen.append(ScenarioDef(
            "NORMAL_DAY", *SCENARIO_NAMES["NORMAL_DAY"],
            "A representative normal weekday: dry weather, typical supplier mix, all equipment healthy, no episode drivers "
            "active. Use it as the reference for before/after comparisons.",
            at(dn, 0), at(dn + 1, 0), at(dn, 15), at(dn, 15), None, None,
            [{"module": "production_kpi", "description": "OER, KER, throughput and energy/t near their 30-day medians", "entity_code": None},
             {"module": "maintenance_alert", "description": "No high/critical threshold alerts on the day", "entity_code": None},
             {"module": "logistics", "description": "Truck wait-to-weigh around the normal ~8-15 min", "entity_code": None}]))
        windows.append((at(dn, 0), at(dn + 1, 0)))

    # ------------------------------------------------------------------ OER_DEGRADATION (A-51 .. A-46)
    ds = A - 51
    if day_ok(ds - 2):
        s, e = at(ds, 0), at(ds + 6, 0)
        focus = at(ds + 2, 16)
        base_d = ds - 7
        protected |= {base_d}
        mods.forced_rain[ds - 2] = 38.0
        mods.forced_rain[ds - 1] = 31.0
        for d in range(ds, ds + 3):
            mods.intake_mult[d] *= 1.12  # post-rain harvest catch-up at the crop peak
        # supplier quality drop: lowest-quality dealers + smallholder groups (harvest rounds disrupted by rain)
        dealers = sup_by_type.get("dealer", [])
        small = sup_by_type.get("smallholder", [])
        estates = sup_by_type.get("estate", [])
        shape = np.zeros(tb.days)
        for k, d in enumerate(range(ds, ds + 5)):
            shape[d] = [0.6, 1.0, 1.0, 0.8, 0.4][k]
        for i in dealers:
            mods.unripe_shift[i] += 8.0 * shape
            mods.h2m_shift[i] += 12.0 * shape
        for i in small:
            mods.unripe_shift[i] += 5.0 * shape
            mods.h2m_shift[i] += 6.0 * shape
        for i in estates:
            mods.unripe_shift[i] += 1.5 * shape
        label("INJ-OER-SUPQ", "OER_DEGRADATION", "ffb_quality_drop", "quality", "supplier_group", "dealers+smallholders",
              None, "FFB_RECEPTION", at(ds, 0), at(ds + 5, 0), 8.0,
              {"unripe_add_pp_dealers": 8.0, "unripe_add_pp_smallholders": 5.0, "unripe_add_pp_estates": 1.5, "harvest_to_mill_add_h": 12.0,
               "dealers": [suppliers[i].code for i in dealers], "severity": "medium"},
              "Rain-disrupted harvest rounds: more unripe bunches and longer harvest-to-mill time from dealers and smallholder groups.")
        # operators shorten sterilizer cycles to keep up with the peak intake -> under-cooking
        cyc = mods.trapezoid(at(ds + 1, 6), at(ds + 1, 9), at(ds + 4, 10), at(ds + 4, 14))
        mods.ster_cycle -= (P("sterilizer_cycle_min") - 66.0) * cyc
        mods.rate_adj += 2.0 * cyc
        label("INJ-OER-STER", "OER_DEGRADATION", "sterilizer_cycle_shortened", "production", "process_stage", "STERILIZATION",
              None, "STERILIZATION", at(ds + 1, 6), at(ds + 4, 14), 14.0,
              {"cycle_min_from": P("sterilizer_cycle_min"), "cycle_min_to": 66.0, "severity": "medium"},
              "Sterilizer cycle setpoint shortened from 80 to 66 min to raise throughput during peak intake (under-cooking).")
        # worn press screws pushed at high feed: all presses lose more oil in the cake, motor current slightly up
        wear = mods.trapezoid(at(ds, 0), at(ds + 1, 0), at(ds + 4, 6), at(ds + 4, 12))
        mods.press_wear += 0.40 * wear
        for k in range(n_press):
            ov = mods.overlay(f"PRS-0{k + 1}")
            ov["cur_mult"] *= 1 + 0.04 * wear
        label("INJ-OER-PRESS", "OER_DEGRADATION", "press_screw_wear", "production", "process_stage", "PRESSING", None, "PRESSING",
              at(ds, 0), at(ds + 4, 12), 0.40, {"fibre_loss_rel_increase": 0.40, "press_current_rise_pct": 4, "severity": "medium"},
              "Press screws near end of life run at high feed: press-cake oil +40% relative (~+0.14 pp of FFB), current +4%; "
              "screws rebuilt/adjusted at the end of the window.")
        mods.breakdowns.append(Breakdown("BD-OER-PRS", "PRS-02", at(ds + 4, 6), at(ds + 4, 12), "none", None, "corrective",
                                         "Press screws/cone adjusted and worn worm segments rebuilt (presses rotated through the service).", "OER_DEGRADATION"))
        # clarifier steam-coil control valve sticks -> oil temperature -6 degC -> sludge oil loss x1.6
        clr = mods.trapezoid(at(ds + 2, 2), at(ds + 2, 5), at(ds + 3, 17), at(ds + 3, 20))
        mods.clar_offset -= 6.0 * clr
        label("INJ-OER-CLR", "OER_DEGRADATION", "clarifier_temp_drop", "production", "equipment", "CLR-01", "CLR-01", "CLARIFICATION",
              at(ds + 2, 2), at(ds + 3, 20), 6.0, {"temp_drop_c": 6.0, "severity": "high"},
              "Clarifier steam-coil control valve stuck partly closed; oil temperature fell ~6 degC (repaired by work order).")
        mods.breakdowns.append(Breakdown("BD-OER-CLR", "CLR-01", at(ds + 3, 17), at(ds + 3, 19.5), "none", None, "corrective",
                                         "Clarifier steam-coil control valve freed and re-calibrated (temperature restored).", "OER_DEGRADATION"))
        scen.append(ScenarioDef(
            "OER_DEGRADATION", *SCENARIO_NAMES["OER_DEGRADATION"],
            "Peak-season OER loss with several simultaneous drivers: rain-disrupted harvest (more unripe FFB, longer "
            "harvest-to-mill time from 4 dealers and smallholders), shortened sterilizer cycles to chase throughput "
            "(under-cooking -> EFB/condensate oil loss) and a stuck clarifier steam valve (lower oil temperature -> sludge "
            "oil loss). OER is computed from these drivers by the loss model, not set directly.",
            s, e, focus, at(base_d, 16), "CLARIFICATION", "CLR-01",
            [{"module": "production_kpi", "description": "Daily OER ~0.7-1.1 pp below NORMAL_DAY on the focus day", "entity_code": None},
             {"module": "process_twin", "description": "Sterilizer cycle ~66 min; clarifier temperature ~84 degC", "entity_code": "CLR-01"},
             {"module": "anomaly", "description": "OER below expected given throughput; oil losses (EFB, sludge) above normal range", "entity_code": None},
             {"module": "traceability", "description": "Production batches and CPO lots of the window carry higher unripe share / FFA", "entity_code": None},
             {"module": "maintenance_alert", "description": "Clarifier low-temperature threshold alert; OER-below-target alerts", "entity_code": "CLR-01"},
             {"module": "copilot", "description": "Why did OER drop? -> unripe share, sterilizer cycle, sludge loss evidence", "entity_code": None},
             {"module": "impact", "description": "Lost CPO = FFB processed x OER gap", "entity_code": None}]))
        windows.append((s, e))

    # ------------------------------------------------------------------ ENERGY_EFFICIENCY_DROP (week ending a Sunday ~A-67)
    sun = _first_weekday_on_or_after(tb, max(A - 69, 0), 6) if A - 69 >= 0 else None
    if sun is not None and day_ok(sun - 9):
        s, e = at(sun - 6, 0), at(sun + 1, 0)
        clean = at(sun, 5.5)
        focus = at(sun - 3, 15)
        base_d = sun - 13
        protected |= {base_d}
        foul = mods.power_curve(at(sun - 9, 0), at(sun, 5), 1.3, end=clean)
        mods.boiler_eff_delta -= 0.08 * foul
        mods.flue_add += 45.0 * foul
        mods.fan_mult += 0.25 * foul
        mods.fwp_mult += 0.12 * foul
        leak = mods.trapezoid(at(sun - 6, 0), at(sun - 5, 0), at(sun, 5), clean)
        mods.steam_extra += P("scn_energy_steam_increase_pct") / 100 * leak
        ov = mods.overlay("BLR-FAN-01")
        ov["vib_add"] += 0.6 * foul
        ov["cur_mult"] *= 1 + 0.25 * foul
        for d in range(sun - 5, sun):
            mods.idle_running[mods.hour_mask(at(d, 0), at(d + 1, 0))] = True
        air = mods.trapezoid(at(sun - 6, 0), at(sun - 5, 12), at(sun, 5), at(sun, 9))
        mods.misc_add_kw += 75.0 * air
        label("INJ-ENG-AIR", "ENERGY_EFFICIENCY_DROP", "compressed_air_leak", "energy", "process_stage", "POWER", None, "POWER",
              at(sun - 6, 0), at(sun, 9), 75.0, {"extra_base_load_kw": 75, "severity": "low"},
              "Compressed-air leaks (failed drain valves, hoses) keep the compressors loaded: ~+75 kW base load around the clock.")
        label("INJ-ENG-FOUL", "ENERGY_EFFICIENCY_DROP", "boiler_fouling", "energy", "equipment", "BLR-01", "BLR-01", "BOILER_STEAM",
              at(sun - 9, 0), clean, 0.08, {"boiler_efficiency_drop": 0.08, "flue_gas_rise_c": 45, "id_fan_load_rise": 0.25, "severity": "medium"},
              "Boiler tube fouling: efficiency 0.60 -> 0.52, flue gas +45 degC, ID-fan load +25%; cleaned at the Sunday stop.")
        label("INJ-ENG-STEAM", "ENERGY_EFFICIENCY_DROP", "steam_trap_leak", "energy", "process_stage", "STERILIZATION", "STR-02", "STERILIZATION",
              at(sun - 6, 0), clean, P("scn_energy_steam_increase_pct") / 100, {"steam_per_t_increase_pct": P("scn_energy_steam_increase_pct"), "severity": "medium"},
              "Failed steam traps / condensate valves on sterilizers STR-02 and STR-04: +15% steam per tonne FFB.")
        label("INJ-ENG-IDLE", "ENERGY_EFFICIENCY_DROP", "idle_running", "energy", "process_stage", "THRESHING", None, "THRESHING",
              at(sun - 5, 0), at(sun, 0), 1.0, {"motors": ["LR-CNV-01", "THR-01", "THR-02", "CNV-02", "DIG-01..04"], "severity": "low"},
              "Conveyors, threshers and digesters left running at no load during no-feed gaps (shift handover practice).")
        mods.breakdowns.append(Breakdown("BD-ENG-BLR", "BLR-01", clean, at(sun, 12), "none", None, "corrective",
                                         "Boiler tube cleaning / soot blowing during the planned Sunday stop.", "ENERGY_EFFICIENCY_DROP", planned=True))
        mods.breakdowns.append(Breakdown("BD-ENG-STR", "STR-02", at(sun, 6), at(sun, 10), "none", None, "corrective",
                                         "Steam traps and condensate valves on STR-02/STR-04 replaced during the planned Sunday stop.", "ENERGY_EFFICIENCY_DROP", planned=True))
        scen.append(ScenarioDef(
            "ENERGY_EFFICIENCY_DROP", *SCENARIO_NAMES["ENERGY_EFFICIENCY_DROP"],
            "Energy per tonne rises over a week from three identifiable causes visible in sensors: boiler tube fouling "
            "(flue gas temperature and ID-fan current up, more fibre+shell per tonne of steam), leaking sterilizer steam "
            "traps (+15% steam per tonne) and motors left running at no load during no-feed gaps (idle kWh). Ends with "
            "boiler cleaning and trap replacement at the Sunday stop.",
            s, e, focus, at(base_d, 15), "BOILER_STEAM", "BLR-01",
            [{"module": "energy", "description": "kWh/t FFB and steam t/t FFB above the baseline week; idle kWh up", "entity_code": None},
             {"module": "process_twin", "description": "Boiler flue gas temperature and ID-fan current trending up", "entity_code": "BLR-01"},
             {"module": "maintenance_alert", "description": "Flue gas temperature and energy-per-tonne threshold alerts", "entity_code": "BLR-01"},
             {"module": "anomaly", "description": "Energy high relative to production volume", "entity_code": None},
             {"module": "copilot", "description": "Why did energy/t rise? -> idle running, boiler efficiency, steam/t evidence", "entity_code": None},
             {"module": "impact", "description": "Extra energy cost and biomass fuel use per tonne", "entity_code": None}]))
        windows.append((s, e))

    # ------------------------------------------------------------------ STEAM_PRESSURE_DEVIATION (A-22)
    dsd = A - 22
    if day_ok(dsd - 7):
        s, e = at(dsd, 4), at(dsd, 22)
        base_d = dsd - 7
        protected |= {base_d, dsd}
        mods.forced_rain[dsd - 1] = 42.0  # heavy rain the night before -> wet fibre fuel
        sev = mods.trapezoid(at(dsd, 5), at(dsd, 8), at(dsd, 14), at(dsd, 15.5))
        mods.boiler_cap -= 0.55 * sev
        ov = mods.overlay("FWP-01")
        ov["vib_add"] += 2.2 * sev
        ov["cur_mult"] *= 1 - 0.10 * sev
        ov["temp_add"] += 6.0 * sev
        label("INJ-STM-FWP", "STEAM_PRESSURE_DEVIATION", "feedwater_pump_cavitation", "equipment", "equipment", "FWP-01", "FWP-01", "BOILER_STEAM",
              at(dsd, 5), at(dsd, 15.5), 0.55, {"boiler_capacity_loss": 0.55, "severity": "high", "contributing": "wet fibre fuel after heavy rain"},
              "Clogged feed-water pump suction strainer -> cavitation, limited feed-water -> firing reduced -> steam pressure falls.")
        mods.breakdowns.append(Breakdown("BD-STM-FWP", "FWP-01", at(dsd, 14), at(dsd, 15.5), "none", None, "corrective",
                                         "FWP-01 suction strainer cleaned, pump re-primed (standby pump in service during cleaning).", "STEAM_PRESSURE_DEVIATION"))
        scen.append(ScenarioDef(
            "STEAM_PRESSURE_DEVIATION", *SCENARIO_NAMES["STEAM_PRESSURE_DEVIATION"],
            "A clogged feed-water pump suction strainer (FWP-01 cavitation: vibration up) limits boiler output; drum and "
            "BPV header pressure fall ~15% for ~8 h, sterilizer cycles are extended, steam-limited throughput drops, "
            "digester temperature falls, under-cooking raises EFB/condensate oil loss and the turbine output drop is "
            "covered by grid/diesel. Wet fibre fuel after overnight rain is a contributing factor.",
            s, e, at(dsd, 12), at(base_d, 12), "BOILER_STEAM", "FWP-01",
            [{"module": "process_twin", "description": "Boiler drum and BPV header pressure ~15% below setpoint", "entity_code": "BLR-01"},
             {"module": "maintenance_alert", "description": "Low steam pressure threshold alerts (drum + header); FWP-01 vibration", "entity_code": "FWP-01"},
             {"module": "production_kpi", "description": "Throughput and OER down during the deviation hours", "entity_code": None},
             {"module": "energy", "description": "Turbine output down, grid/diesel import and energy cost up", "entity_code": "TG-01"},
             {"module": "anomaly", "description": "Steam pressure deviation with sterilizer cycle extension", "entity_code": None},
             {"module": "copilot", "description": "What happened to steam pressure? -> FWP-01 evidence", "entity_code": "FWP-01"}]))
        windows.append((s, e))

    # ------------------------------------------------------------------ TRUCK_QUEUE_CONGESTION (A-8 .. A-5)
    dq = A - 6
    if day_ok(dq - 9):
        s, e = at(dq - 2, 0), at(dq + 2, 0)
        base_d = dq - 9
        protected |= {base_d, dq}
        mods.forced_rain[dq - 2] = 35.0
        mods.forced_rain[dq - 1] = 28.0
        mods.forced_dry |= {dq, dq + 1}
        mods.intake_mult[dq] *= 1.6
        mods.intake_mult[dq + 1] *= 1.12
        mods.sharpen[dq] = 1.7
        mods.grading_mult[dq] = 1.4
        mods.quota_exempt |= {dq - 1, dq, dq + 1}
        mods.wb_outages.append((1, at(dq, 6.0), at(dq, 14.0)))
        mods.wb_svc_mult[mods.hour_mask(at(dq, 6.0), at(dq, 14.0))] = 2.0  # manual ticketing on WB-01 while the system is re-configured
        mods.bay_outages.append((2, at(dq, 10), at(dq, 17)))
        label("INJ-QUE-SURGE", "TRUCK_QUEUE_CONGESTION", "arrival_surge", "logistics", "facility", "MILL-A", None, "FFB_RECEPTION",
              at(dq, 0), at(dq + 2, 0), 1.45, {"intake_multiplier": 1.6, "arrival_peak_sharpening": 1.7, "severity": "high"},
              "Post-rain harvest surge: intake x1.6 with convoy-style arrivals concentrated in late morning/afternoon.")
        label("INJ-QUE-WB", "TRUCK_QUEUE_CONGESTION", "weighbridge_outage", "logistics", "equipment", "WB-02", "WB-02", "FFB_RECEPTION",
              at(dq, 6.0), at(dq, 14.0), 8.0, {"outage_h": 8.0, "severity": "high"},
              "Weighbridge WB-02 load-cell fault: out of service 06:00-14:00, single-bridge operation with manual ticketing.")
        label("INJ-QUE-BAY", "TRUCK_QUEUE_CONGESTION", "unloading_bay_outage", "logistics", "process_stage", "FFB_RECEPTION", "LR-CNV-01", "FFB_RECEPTION",
              at(dq, 10), at(dq, 17), 7.0, {"bays_out": 1, "outage_h": 7.0, "severity": "medium"},
              "Unloading bay 3 hydraulic door fault 10:00-17:00 (2 of 3 bays available).")
        mods.breakdowns.append(Breakdown("BD-QUE-WB", "WB-02", at(dq, 6.0), at(dq, 14.0), "none", None, "breakdown",
                                         "WB-02 load cell junction box water ingress; cell replaced and bridge re-calibrated.", "TRUCK_QUEUE_CONGESTION"))
        scen.append(ScenarioDef(
            "TRUCK_QUEUE_CONGESTION", *SCENARIO_NAMES["TRUCK_QUEUE_CONGESTION"],
            "Two rain days hold back harvesting; on the first dry day suppliers deliver a surge (x1.6) in convoys while "
            "weighbridge WB-02 is out of service for 8 h (manual ticketing on WB-01) and one unloading bay is down. Wait-to-weigh, queue length and turnaround rise; the ramp "
            "stock builds, FFB waits longer before sterilization (Little's law), which raises FFA of the following CPO "
            "lots and slightly lowers OER.",
            s, e, at(dq, 10), at(base_d, 10), "FFB_RECEPTION", "WB-02",
            [{"module": "logistics", "description": "Wait-to-weigh and queue length several times the normal day", "entity_code": "WB-02"},
             {"module": "production_kpi", "description": "Ramp stock and FFB wait-before-processing up; OER slightly down next day", "entity_code": None},
             {"module": "traceability", "description": "CPO lots of the focus/next day show higher FFA", "entity_code": None},
             {"module": "maintenance_alert", "description": "Queue-length and wait-time threshold alerts", "entity_code": None},
             {"module": "anomaly", "description": "Excessive waiting time (never an accusation)", "entity_code": None},
             {"module": "copilot", "description": "How many trucks are waiting / why? -> surge + WB-02 outage", "entity_code": "WB-02"}]))
        windows.append((s, e))

    # ------------------------------------------------------------------ PRESS_VIBRATION_ANOMALY (onset A-14, window A-4 .. A)
    if day_ok(A - 15):
        onset = at(A - 14, 3)
        peak = at(A, 10)
        s, e = at(A - 4, 0), at(A + 1, 0)
        base_d = A - 15
        protected |= {base_d, A}
        mods.press_sev[2] = np.maximum(mods.press_sev[2], mods.power_curve(onset, peak, 2.75))
        label("INJ-PRS-BRG", "PRESS_VIBRATION_ANOMALY", "bearing_wear", "equipment", "equipment", "PRS-03", "PRS-03", "PRESSING",
              onset, at(A + 1, 0), P("scn_press_degradation_vib_peak_mm_s"),
              {"vib_peak_mm_s": P("scn_press_degradation_vib_peak_mm_s"), "current_rise_pct": P("scn_press_degradation_current_rise_pct"),
               "bearing_temp_rise_c": 24, "throughput_derate_pct": P("scn_press_degradation_throughput_derate_pct"),
               "lead_days": P("scn_press_degradation_lead_days"), "severity": "critical"},
              "PRS-03 gearbox/thrust bearing wear: vibration 1.6 -> 4.8 mm/s (ISO zone D), bearing temperature +24 degC, motor "
              "current +12%; feed to PRS-03 reduced; cake oil loss up. No work order yet at the anchor (the tour creates it).")
        scen.append(ScenarioDef(
            "PRESS_VIBRATION_ANOMALY", *SCENARIO_NAMES["PRESS_VIBRATION_ANOMALY"],
            "Progressive bearing wear on screw press PRS-03 over ~14 days: drive-end vibration rises into ISO zone C and "
            "then D, bearing temperature and motor current follow, operators cut its feed, its press-cake oil loss rises "
            "(plant OER slightly lower, energy per tonne slightly higher). Threshold alerts fire; no work order exists yet "
            "for PRS-03 at the anchor, so the guided tour can create one.",
            s, e, at(A, 15), at(base_d, 15), "PRESSING", "PRS-03",
            [{"module": "process_twin", "description": "Pressing node shows PRS-03 vibration in ISO zone D, bearing temp ~85 degC", "entity_code": "PRS-03"},
             {"module": "anomaly", "description": "Equipment anomaly on PRS-03 (vibration + temperature + current corroborate)", "entity_code": "PRS-03"},
             {"module": "maintenance_alert", "description": "Vibration warning (zone C) then critical (zone D) threshold alerts", "entity_code": "PRS-03"},
             {"module": "production_kpi", "description": "PRS-03 feed reduced; press fibre oil loss up; plant OER ~0.1 pp lower", "entity_code": "PRS-03"},
             {"module": "traceability", "description": "Production batches / CPO lots of the last days processed with degraded PRS-03", "entity_code": "PRS-03"},
             {"module": "copilot", "description": "Which machine to inspect first? -> PRS-03 with sensor evidence", "entity_code": "PRS-03"},
             {"module": "impact", "description": "Downtime what-if for a bearing replacement vs run-to-failure", "entity_code": "PRS-03"}]))
        windows.append((s, e))

    # ------------------------------------------------------------------ background abnormalities (no scenario code)
    for d in list(protected):
        mods.forced_dry.add(d)
    for sc in scen:
        mods.noise_free_days.add(int(sc.focus // M))
        if sc.baseline is not None:
            mods.noise_free_days.add(int(sc.baseline // M))

    def free_day(lo: int, hi: int, margin: int = 1) -> int | None:
        lo, hi = max(lo, 1), min(hi, A - 1)
        cands = []
        for d in range(lo, hi + 1):
            if any(abs(d - p) <= margin for p in protected):
                continue
            if any(ws - margin * M <= d * M < we + margin * M for ws, we in windows):
                continue
            cands.append(d)
        if not cands:
            return None
        return int(rng.choice(cands))

    def reserve(d: int, n: int = 1) -> None:
        windows.append((d * M, (d + n) * M))

    # PRS-01 bearing wear (history; alert -> work order -> repaired at the next Sunday stop)
    d0 = free_day(A - 112, A - 100, margin=2)
    if d0 is not None:
        rep = _first_weekday_on_or_after(tb, d0 + 7, 6)
        if rep <= A:
            onset, repair = at(d0, 8), at(rep, 6)
            mods.press_sev[0] = np.maximum(mods.press_sev[0], 0.62 * mods.power_curve(onset, at(rep, 0), 2.0, end=repair))
            label("INJ-BG-PRS01", None, "bearing_wear", "equipment", "equipment", "PRS-01", "PRS-01", "PRESSING", onset, repair, 3.6,
                  {"vib_peak_mm_s": 3.6, "severity": "medium"}, "PRS-01 bearing wear reaching ISO zone C; bearing replaced at the Sunday stop.")
            mods.breakdowns.append(Breakdown("BD-BG-PRS01", "PRS-01", repair, at(rep, 11), "none", None, "corrective",
                                             "PRS-01 drive-end bearing replaced and shaft alignment checked (planned stop).", None, planned=True))
            reserve(d0, rep - d0 + 1)
    # DIG-02 motor bearing overheating (no alarm; fixed by lubrication)
    d0 = free_day(A - 92, A - 80, margin=2)
    if d0 is not None:
        rep = _first_weekday_on_or_after(tb, d0 + 3, 6)
        if rep <= A:
            ov = mods.overlay("DIG-02")
            sev = mods.power_curve(at(d0, 6), at(rep, 0), 1.0, end=at(rep, 6))
            ov["temp_add"] += 14.0 * sev
            ov["cur_mult"] *= 1 + 0.08 * sev
            ov["vib_add"] += 0.5 * sev
            label("INJ-BG-DIG02", None, "lubrication_deficit", "equipment", "equipment", "DIG-02", "DIG-02", "DIGESTION", at(d0, 6), at(rep, 6), 14.0,
                  {"bearing_temp_rise_c": 14, "severity": "low"}, "DIG-02 drive bearing running hot (lubrication deficit); re-greased at the Sunday stop.")
            reserve(d0, rep - d0 + 1)
    # minor steam dip (below alarm threshold)
    d0 = free_day(A - 100, A - 78)
    if d0 is not None:
        hh = float(rng.uniform(9, 15))
        sev = mods.trapezoid(at(d0, hh), at(d0, hh + 0.7), at(d0, hh + 2.5), at(d0, hh + 3.2))
        mods.boiler_cap -= 0.40 * sev
        label("INJ-BG-STEAM", None, "steam_dip_minor", "production", "equipment", "BLR-01", "BLR-01", "BOILER_STEAM",
              at(d0, hh), at(d0, hh + 3.2), 0.40, {"severity": "low"}, "Short boiler output dip (fuel feed screw choke); pressure recovers in ~3 h.")
        reserve(d0)
    # CTF-01 imbalance (test side, subtle: below the ISO warning limit)
    d0 = free_day(A - 19, A - 15, margin=0)
    if d0 is not None:
        rep = _first_weekday_on_or_after(tb, d0 + 2, 6)
        if rep <= A:
            ov = mods.overlay("CTF-01")
            sev = mods.power_curve(at(d0, 10), at(rep, 0), 1.2, end=at(rep, 7))
            ov["vib_add"] += 2.1 * sev
            ov["cur_mult"] *= 1 + 0.04 * sev
            label("INJ-BG-CTF01", None, "rotor_imbalance", "equipment", "equipment", "CTF-01", "CTF-01", "CLARIFICATION", at(d0, 10), at(rep, 7), 2.1,
                  {"vib_add_mm_s": 2.1, "severity": "low"}, "CTF-01 bowl imbalance (sludge build-up); cleaned and balanced at the Sunday stop.")
            reserve(d0, rep - d0 + 1)
    # supplier bad delivery day (quality)
    d0 = free_day(A - 95, A - 60)
    if d0 is not None:
        i = int(rng.choice(sup_by_type.get("dealer", [0])))
        mods.supplier_bad_days.append((i, d0, 12.0))
        label("INJ-BG-SUPQ", None, "ffb_quality_drop", "quality", "supplier", suppliers[i].code, None, "FFB_RECEPTION", at(d0, 0), at(d0 + 1, 0), 12.0,
              {"unripe_add_pp": 12.0, "severity": "low"}, "One dealer delivered a high share of unripe bunches for a day.")
        reserve(d0)
    # idle running night (test side)
    d0 = free_day(A - 40, A - 32)
    if d0 is not None:
        m = mods.hour_mask(at(d0, 0), at(d0 + 1, 8))
        mods.idle_running[m] = True
        label("INJ-BG-IDLE", None, "idle_running", "energy", "process_stage", "THRESHING", None, "THRESHING", at(d0, 0), at(d0 + 1, 8), 1.0,
              {"severity": "low"}, "Motors left running at no load through a no-feed night.")
        reserve(d0, 2)
    # sensor faults (data-quality abnormalities)
    for code, kind, lo, hi, dur in (("DIG-03-TMP-PROC", "flatline", A - 105, A - 60, 10.0), ("PRS-02-VIB-DE", "spike", A - 45, A - 20, 0.0),
                                    ("CLR-01-TMP", "dropout", A - 20, A - 8, 6.0), ("TG-01-LOAD", "flatline", A - 70, A - 55, 5.0)):
        eq_code = next((c for c in sorted(equip_codes, key=len, reverse=True) if code.startswith(c + "-")), None)
        if eq_code is None:
            continue
        d0 = free_day(lo, hi, margin=0)
        if d0 is None:
            continue
        hh = float(rng.uniform(1, 12))
        s_, e_ = at(d0, hh), at(d0, hh + max(dur, 0.5))
        mods.sensor_faults.append(SensorFault(code, kind, s_, e_, {"n_spikes": 3} if kind == "spike" else {}))
        label(f"INJ-BG-SF-{code}", None, f"sensor_{kind}", "equipment", "sensor", code, eq_code, None, s_, e_, None, {"severity": "low"}, f"Instrument data-quality fault ({kind}) on {code}; process unaffected.")

    # ------------------------------------------------------------------ random breakdowns (~6 unplanned events/month)
    rate_month = P("unplanned_stop_events_per_month")
    n_events = int(rng.poisson(rate_month * tb.days / 30.0 * 0.9))
    pools = [
        ("plant", ["LR-CNV-01", "CNV-02", "BLR-FAN-01", "PMP-CO-01"], 0.45),
        ("press", ["PRS-01", "PRS-02", "PRS-04", "DIG-01", "DIG-03", "DIG-04"], 0.25),
        ("thresher", ["THR-01", "THR-02"], 0.1),
        ("none", ["KRN-01", "RPL-01", "CTF-02", "WTP-PMP-01", "POME-PMP-01"], 0.2),
    ]
    mean_h = P("unplanned_stop_duration_h_mean")
    sig = 0.6
    for k in range(n_events):
        d0 = free_day(1, A - 1, margin=0)
        if d0 is None:
            break
        u = rng.random()
        cum = np.cumsum([w for _, _, w in pools])
        impact, eqs, _w = pools[min(int(np.searchsorted(cum, u)), len(pools) - 1)]
        eq = str(rng.choice(eqs))
        hh = float(rng.uniform(9, 26))
        dur_h = float(np.clip(rng.lognormal(np.log(mean_h) - sig**2 / 2, sig), 0.5, 8.0))
        s_, e_ = at(d0, hh), at(d0, hh + dur_h)
        if e_ >= tb.minutes:
            continue
        idx = None
        if impact == "press":
            idx = int(eq[-1]) - 1
        elif impact == "thresher":
            idx = int(eq[-1]) - 1
        desc = {
            "plant": "Unplanned stop: {eq} trip (drive/chain fault); mill stopped until repaired.",
            "press": "Unplanned stop of {eq} (screw/bearing/drive fault); press line out of service.",
            "thresher": "Unplanned stop of {eq} (drum drive fault); half threshing capacity.",
            "none": "Breakdown of {eq}; no direct throughput loss (standby/buffer).",
        }[impact].format(eq=eq)
        code = f"BD-{k + 1:03d}"
        mods.breakdowns.append(Breakdown(code, eq, s_, e_, impact, idx, "breakdown", desc))
        label(f"INJ-{code}", None, "equipment_breakdown", "production" if impact != "none" else "equipment", "equipment", eq, eq, None, s_, e_,
              round(dur_h, 2), {"impact": impact, "duration_h": round(dur_h, 2), "severity": "medium" if impact == "plant" else "low"}, desc)
        reserve(d0)

    # apply breakdown impacts to hourly capacity arrays
    for b in mods.breakdowns:
        if b.impact == "plant":
            mods.add_stop(mods.plant_stop_min, b.start, b.end)
        elif b.impact == "press" and b.unit_index is not None:
            m = np.zeros(tb.hours)
            mods.add_stop(m, b.start, b.end)
            mods.press_avail[b.unit_index] = np.minimum(mods.press_avail[b.unit_index], 1 - m / 60.0)
        elif b.impact == "thresher":
            m = np.zeros(tb.hours)
            mods.add_stop(m, b.start, b.end)
            mods.cap_factor = np.minimum(mods.cap_factor, 1 - 0.5 * m / 60.0)
    # supplier bad days
    for i, d0, add in mods.supplier_bad_days:
        mods.unripe_shift[i, d0] += add
    return mods, scen, inj, protected
