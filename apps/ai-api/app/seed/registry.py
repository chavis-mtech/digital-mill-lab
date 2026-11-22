"""Static plant registry: company, facility, line, stages, equipment, sensors, technicians, suppliers, plantations.

All entities are FICTIONAL ("Demo Palm Oil Co. (fictional)", "Demo Palm Mill A"); names never refer to real sites.
Equipment ratings are Engineering Assumptions sized so the running electrical load is ~17 kWh/t FFB
(P electricity_kwh_per_t_ffb) at the operator target rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.seed.assumptions import MOTOR_EFF, SQRT3, VOLTAGE_V, A, P

STAGES = [
    # code, en, th, seq, kind
    ("FFB_RECEPTION", "FFB Reception & Loading Ramp", "รับผลปาล์มและลานเท", 1, "main"),
    ("STERILIZATION", "Sterilization", "การนึ่งผลปาล์ม", 2, "main"),
    ("THRESHING", "Threshing", "การแยกผลออกจากทะลาย", 3, "main"),
    ("DIGESTION", "Digestion", "การย่อยผลปาล์ม", 4, "main"),
    ("PRESSING", "Pressing", "การหีบน้ำมัน", 5, "main"),
    ("CLARIFICATION", "Clarification", "การทำใสน้ำมัน", 6, "main"),
    ("CPO_STORAGE", "CPO Storage & Dispatch", "ถังเก็บน้ำมันปาล์มดิบ", 7, "main"),
    ("KERNEL_RECOVERY", "Kernel Recovery", "การแยกเมล็ดใน", 101, "support"),
    ("BOILER_STEAM", "Boiler & Steam", "หม้อไอน้ำและไอน้ำ", 102, "support"),
    ("POWER", "Power Generation", "ระบบผลิตไฟฟ้า", 103, "support"),
    ("WATER_TREATMENT", "Water Treatment", "ระบบปรับปรุงคุณภาพน้ำ", 104, "support"),
    ("POME_TREATMENT", "POME Treatment", "ระบบบำบัดน้ำเสีย (POME)", 105, "support"),
]


@dataclass
class EquipSpec:
    code: str
    name: str
    etype: str
    stage: str
    criticality: str
    rated_kw: float | None
    rated_capacity: float | None
    cap_unit: str | None
    load_kind: str  # process | press | digester | thresher | utility_steam | utility_const | none | vessel | boiler | tg | dg | tank | clarifier
    vib_class: str | None = None  # rigid2 | flex2 | rigid1
    vib_healthy: float | None = None
    id: int = 0
    index: int = 0  # for presses/digesters/threshers/sterilizers/tanks: 0-based unit index
    extra: dict = field(default_factory=dict)

    @property
    def fla_a(self) -> float | None:
        """Full-load current of the drive motor (A) from rated kW (3-phase 400 V, pf 0.85, eff 0.92)."""
        if not self.rated_kw:
            return None
        return self.rated_kw * 1000 / (SQRT3 * VOLTAGE_V * P("motor_power_factor") * MOTOR_EFF)


def equipment_specs() -> list[EquipSpec]:
    v = P
    s: list[EquipSpec] = []
    s.append(EquipSpec("WB-01", "Weighbridge 1 (inbound)", "weighbridge", "FFB_RECEPTION", "B", None, 60, "t", "none"))
    s.append(EquipSpec("WB-02", "Weighbridge 2 (outbound)", "weighbridge", "FFB_RECEPTION", "B", None, 60, "t", "none"))
    s.append(EquipSpec("LR-CNV-01", "Loading ramp scraper conveyor", "conveyor", "FFB_RECEPTION", "A", 22, 70, "t/h", "process", "rigid2", v("vib_healthy_conveyor_drive_mm_s")))
    for i in range(5):
        s.append(EquipSpec(f"STR-0{i + 1}", f"Horizontal sterilizer {i + 1}", "sterilizer", "STERILIZATION", "A", None,
                           v("sterilizer_cage_capacity_t") * v("sterilizer_cages_per_vessel"), "t/cycle", "vessel", index=i))
    for i in range(2):
        s.append(EquipSpec(f"THR-0{i + 1}", f"Rotary drum thresher {i + 1}", "thresher", "THRESHING", "A", 30, 35, "t/h", "thresher", "rigid2", v("vib_healthy_conveyor_drive_mm_s") + 0.2, index=i))
    s.append(EquipSpec("CNV-02", "Fruit & EFB conveyor", "conveyor", "THRESHING", "B", 18.5, 70, "t/h", "process", "rigid2", v("vib_healthy_conveyor_drive_mm_s")))
    n_press = int(v("press_count"))
    for i in range(int(v("digester_count"))):
        s.append(EquipSpec(f"DIG-0{i + 1}", f"Digester {i + 1}", "digester", "DIGESTION", "A", 37, 15, "t FFB/h", "digester", "rigid2", v("vib_healthy_motor_mm_s") + 0.3, index=i))
    for i in range(n_press):
        s.append(EquipSpec(f"PRS-0{i + 1}", f"Twin-screw press {i + 1}", "screw_press", "PRESSING", "A", 75, v("press_unit_capacity_t_ffb_per_h"), "t FFB/h", "press", "rigid2", v("vib_healthy_press_gearbox_mm_s"), index=i))
    s.append(EquipSpec("CLR-01", "Vertical continuous clarifier tank", "clarifier_tank", "CLARIFICATION", "A", None, 90, "m3", "clarifier"))
    for i in range(2):
        s.append(EquipSpec(f"CTF-0{i + 1}", f"Oil purifier centrifuge {i + 1}", "centrifuge", "CLARIFICATION", "B", 30, 8, "m3/h", "process", "flex2", v("vib_healthy_centrifuge_mm_s"), index=i))
    s.append(EquipSpec("PMP-CO-01", "Crude oil transfer pump", "pump", "CLARIFICATION", "B", 15, 30, "m3/h", "process", "rigid2", v("vib_healthy_pump_mm_s")))
    for i in range(int(v("cpo_storage_tank_count"))):
        s.append(EquipSpec(f"TNK-0{i + 1}", f"CPO storage tank {i + 1}", "storage_tank", "CPO_STORAGE", "C", None, v("cpo_storage_tank_capacity_t"), "t", "tank", index=i))
    s.append(EquipSpec("KRN-01", "Nut cracking & kernel separation plant", "kernel_plant", "KERNEL_RECOVERY", "B", 110, 6, "t nuts/h", "process", "flex2", v("vib_healthy_centrifuge_mm_s")))
    s.append(EquipSpec("RPL-01", "Ripple mill", "other_rotating", "KERNEL_RECOVERY", "C", 22, 6, "t nuts/h", "process", "flex2", v("vib_healthy_fan_mm_s") - 0.4))
    s.append(EquipSpec("BLR-01", "Water-tube biomass boiler", "boiler", "BOILER_STEAM", "A", None, v("boiler_installed_t_steam_per_h"), "t steam/h", "boiler"))
    s.append(EquipSpec("BLR-FAN-01", "Boiler induced-draft fan", "other_rotating", "BOILER_STEAM", "A", 132, None, None, "utility_steam", "flex2", v("vib_healthy_fan_mm_s")))
    s.append(EquipSpec("FWP-01", "Boiler feed-water pump", "pump", "BOILER_STEAM", "A", 55, 45, "m3/h", "utility_steam", "rigid2", v("vib_healthy_pump_mm_s")))
    s.append(EquipSpec("TG-01", "Back-pressure steam turbine generator", "turbine", "POWER", "A", None, v("turbine_generator_kw"), "kW", "tg", "rigid1", v("vib_healthy_turbine_gen_mm_s")))
    s.append(EquipSpec("DG-01", "Diesel standby genset", "generator", "POWER", "C", None, v("diesel_genset_kw"), "kW", "dg"))
    s.append(EquipSpec("WTP-PMP-01", "Raw water pump", "pump", "WATER_TREATMENT", "B", 45, 120, "m3/h", "utility_const", "rigid2", v("vib_healthy_pump_mm_s")))
    s.append(EquipSpec("POME-PMP-01", "POME transfer pump", "pump", "POME_TREATMENT", "C", 30, 60, "m3/h", "utility_const", "rigid2", v("vib_healthy_pump_mm_s")))
    for k, e in enumerate(s, start=1):
        e.id = k
    return s


VIB_LIMITS = {
    # (normal_max = warn = ISO zone B/C boundary, crit = zone C/D boundary), from the ISO 10816-3 rows of DOMAIN_PARAMETERS
    "rigid2": ("iso10816_3_group2_rigid_zone_bc_mm_s", "iso10816_3_group2_rigid_zone_cd_mm_s"),
    "flex2": ("iso10816_3_group2_flexible_zone_bc_mm_s", "iso10816_3_group2_flexible_zone_cd_mm_s"),
    "rigid1": ("iso10816_3_group1_rigid_zone_bc_mm_s", "iso10816_3_group1_rigid_zone_cd_mm_s"),
}


@dataclass
class SensorSpec:
    code: str
    equip: EquipSpec
    name: str
    stype: str
    unit: str
    kind: str  # vib | brg_temp | current | rpm | cone | state | run_hours | dig_temp | drum_p | steam_flow | flue_temp | hdr_p | tg_load | dg_load | ves_p | ves_temp | clr_temp | clr_level | tank_level | tank_temp
    sampling_s: int
    normal_min: float | None = None
    normal_max: float | None = None
    warn: float | None = None
    crit: float | None = None
    low_is_bad: bool = False
    id: int = 0


def sensor_specs(equip: list[EquipSpec]) -> list[SensorSpec]:
    out: list[SensorSpec] = []
    brg_n, brg_alarm, brg_trip = P("bearing_temp_normal_c"), P("bearing_temp_alarm_c"), P("bearing_temp_trip_c")
    for e in equip:
        fast = e.code.startswith(("PRS", "FWP"))
        rot_s = 600 if fast else 900
        if e.vib_class:
            bc, cd = (P(k) for k in VIB_LIMITS[e.vib_class])
            out.append(SensorSpec(f"{e.code}-VIB-DE", e, f"{e.name} drive-end vibration (RMS velocity)", "vibration", "mm/s", "vib", rot_s, 0.0, bc, bc, cd))
            out.append(SensorSpec(f"{e.code}-TMP-BRG", e, f"{e.name} bearing temperature", "temperature", "degC", "brg_temp", rot_s, 25.0, brg_n + 13, brg_alarm, brg_trip))
        if e.rated_kw:
            fla = e.fla_a
            out.append(SensorSpec(f"{e.code}-CUR", e, f"{e.name} motor current", "current", "A", "current", rot_s, 0.0,
                                  round(0.95 * fla, 1), round(P("motor_current_alarm_fraction") * fla, 1), round(1.15 * fla, 1)))
        if e.load_kind == "press":
            out.append(SensorSpec(f"{e.code}-RPM", e, f"{e.name} screw shaft speed", "rpm", "rpm", "rpm", 600, 9.0, 13.0))
            out.append(SensorSpec(f"{e.code}-P-CONE", e, f"{e.name} cone hydraulic pressure", "pressure", "bar", "cone", 600, 30.0, 50.0, 55.0, 60.0))
            out.append(SensorSpec(f"{e.code}-STATE", e, f"{e.name} run state (1 = running)", "state", "state", "state", 600))
            out.append(SensorSpec(f"{e.code}-RH", e, f"{e.name} running-hours counter", "running_hours", "h", "run_hours", 3600))
        if e.load_kind == "digester":
            out.append(SensorSpec(f"{e.code}-TMP-PROC", e, f"{e.name} mash temperature", "temperature", "degC", "dig_temp", 900, 88.0, 98.0, 85.0, 80.0, True))
        if e.load_kind == "vessel":
            out.append(SensorSpec(f"{e.code}-P-VES", e, f"{e.name} vessel pressure", "pressure", "bar", "ves_p", 600, 0.0, 3.2, 3.4, 3.6))
            out.append(SensorSpec(f"{e.code}-TMP-VES", e, f"{e.name} vessel temperature", "temperature", "degC", "ves_temp", 900, 30.0, 145.0))
        if e.load_kind == "boiler":
            sp = P("boiler_pressure_barg")
            dev = P("steam_pressure_alarm_deviation_pct") / 100
            out.append(SensorSpec(f"{e.code}-P-DRUM", e, "Boiler drum pressure", "pressure", "bar", "drum_p", 600, round(sp - 2, 1), round(sp + 2, 1), round(sp * (1 - dev), 2), round(sp * (1 - 2 * dev), 2), True))
            out.append(SensorSpec(f"{e.code}-FLOW-STM", e, "Boiler main steam flow", "flow", "t/h", "steam_flow", 600, 0.0, 36.0, 38.0, 40.0))
            out.append(SensorSpec(f"{e.code}-TMP-FLUE", e, "Boiler flue gas temperature (economiser outlet)", "temperature", "degC", "flue_temp", 900, 150.0, 200.0, 220.0, 250.0))
            out.append(SensorSpec(f"{e.code}-RH", e, "Boiler running-hours counter", "running_hours", "h", "run_hours", 3600))
        if e.load_kind == "tg":
            sp = P("bpv_header_pressure_barg")
            dev = P("steam_pressure_alarm_deviation_pct") / 100
            out.append(SensorSpec(f"{e.code}-LOAD", e, "Turbine generator electrical output", "load", "kW", "tg_load", 900, 0.0, 1450.0, 1500.0, 1600.0))
            out.append(SensorSpec(f"{e.code}-P-HDR", e, "Back-pressure vessel (BPV) steam header pressure", "pressure", "bar", "hdr_p", 600, round(sp * (1 - dev), 2), round(sp * (1 + dev), 2), round(sp * (1 - dev), 2), round(sp * (1 - 2 * dev), 2), True))
            out.append(SensorSpec(f"{e.code}-RH", e, "Turbine running-hours counter", "running_hours", "h", "run_hours", 3600))
        if e.load_kind == "dg":
            out.append(SensorSpec(f"{e.code}-LOAD", e, "Diesel genset electrical output", "load", "kW", "dg_load", 3600, 0.0, 800.0))
            out.append(SensorSpec(f"{e.code}-RH", e, "Genset running-hours counter", "running_hours", "h", "run_hours", 3600))
        if e.load_kind == "clarifier":
            out.append(SensorSpec(f"{e.code}-TMP", e, "Clarifier oil temperature", "temperature", "degC", "clr_temp", 900, 85.0, 95.0, 85.0, 80.0, True))
            out.append(SensorSpec(f"{e.code}-LVL", e, "Clarifier level", "level", "%", "clr_level", 3600, 50.0, 85.0))
        if e.load_kind == "tank":
            out.append(SensorSpec(f"{e.code}-LVL", e, f"{e.name} level", "level", "%", "tank_level", 3600, 0.0, 95.0, 95.0, 98.0))
            out.append(SensorSpec(f"{e.code}-TMP", e, f"{e.name} oil temperature", "temperature", "degC", "tank_temp", 3600, 40.0, 55.0, 60.0, 65.0))
    for k, sp in enumerate(out, start=1):
        sp.id = k
    return out


TECHNICIANS = [
    ("TEC-M01", "Technician M-01 (fictional)", "mechanical", "A"),
    ("TEC-M02", "Technician M-02 (fictional)", "mechanical", "A"),
    ("TEC-M03", "Technician M-03 (fictional)", "mechanical", "B"),
    ("TEC-M04", "Technician M-04 (fictional)", "mechanical", "B"),
    ("TEC-M05", "Technician M-05 (fictional)", "mechanical", "D"),
    ("TEC-E01", "Technician E-01 (fictional)", "electrical", "A"),
    ("TEC-E02", "Technician E-02 (fictional)", "electrical", "B"),
    ("TEC-E03", "Technician E-03 (fictional)", "electrical", "D"),
    ("TEC-I01", "Technician I-01 (fictional)", "instrument", "A"),
    ("TEC-I02", "Technician I-02 (fictional)", "instrument", "D"),
    ("TEC-G01", "Technician G-01 (fictional)", "general", "A"),
    ("TEC-G02", "Technician G-02 (fictional)", "general", "B"),
]


@dataclass
class SupplierSpec:
    id: int
    code: str
    name: str
    stype: str
    tier: str
    share: float  # expected share of daily intake
    reliability: float  # probability of delivering on a given day
    unripe_mean: float
    overripe_mean: float
    long_stalk_mean: float
    h2m_mean: float  # harvest-to-mill hours
    truck_mix: dict[str, float]
    plantation_ids: list[int] = field(default_factory=list)
    plates: list[str] = field(default_factory=list)
    registered_on: date | None = None
    sustainability: str = "not_assessed"


TRUCK_TYPES = {
    # type: (payload key, tare_kg nominal)
    "pickup": ("truck_payload_pickup_t", 2100),
    "six_wheel": ("truck_payload_6wheel_t", 6200),
    "ten_wheel": ("truck_payload_10wheel_t", 9800),
    "trailer": ("truck_payload_trailer_t", 15500),
}


def build_suppliers(rng: np.random.Generator, n_total: int | None = None) -> tuple[list[SupplierSpec], list[dict]]:
    """45 fictional suppliers (P supplier_count_active) with persistent quality/reliability traits + plantations."""
    n_total = n_total or int(P("supplier_count_active"))
    plan = [("own_estate", 2), ("estate", 4), ("dealer", 12)]
    plan.append(("smallholder", n_total - sum(n for _, n in plan)))
    type_share = {"own_estate": 0.16, "estate": 0.20, "dealer": 0.36, "smallholder": 0.28}
    reliab = {"own_estate": 0.97, "estate": 0.95, "dealer": 0.88, "smallholder": 0.55}
    h2m = {"own_estate": 9.0, "estate": 12.0, "dealer": 26.0, "smallholder": 19.0}
    mix = {
        "own_estate": {"ten_wheel": 0.55, "trailer": 0.35, "six_wheel": 0.10},
        "estate": {"ten_wheel": 0.60, "trailer": 0.25, "six_wheel": 0.15},
        "dealer": {"ten_wheel": 0.50, "trailer": 0.15, "six_wheel": 0.35},
        "smallholder": {"pickup": 0.50, "six_wheel": 0.42, "ten_wheel": 0.08},
    }
    tier_unripe = {"A": 2.4, "B": 4.3, "C": 7.0}
    sd_unripe = P("supplier_unripe_share_sd_pp") * 0.35  # within-tier spread; tiers carry most of the 3 pp spread
    suppliers: list[SupplierSpec] = []
    plantations: list[dict] = []
    sid = 0
    pid = 0
    names = {"own_estate": "Demo Own Estate", "estate": "Demo Estate", "dealer": "Demo FFB Dealer", "smallholder": "Demo Smallholder Group"}
    for stype, n in plan:
        for k in range(n):
            sid += 1
            if stype in ("own_estate", "estate"):
                tier = "A" if (stype == "own_estate" or rng.random() < 0.6) else "B"
            elif stype == "dealer":
                tier = rng.choice(["A", "B", "C"], p=[0.2, 0.5, 0.3])
            else:
                tier = rng.choice(["A", "B", "C"], p=[0.25, 0.5, 0.25])
            tier = str(tier)
            share = type_share[stype] / n * float(rng.lognormal(0, 0.25))
            sp = SupplierSpec(
                id=sid,
                code=f"SUP-{sid:03d}",
                name=f"{names[stype]} {k + 1:02d} (fictional)",
                stype=stype,
                tier=tier,
                share=share,
                reliability=reliab[stype],
                unripe_mean=max(0.8, tier_unripe[tier] + float(rng.normal(0, sd_unripe))),
                overripe_mean=float(np.clip({"A": 6.5, "B": 8.0, "C": 10.0}[tier] + rng.normal(0, 1.2), 3, 16)),
                long_stalk_mean=float(np.clip({"A": 1.0, "B": 2.5, "C": 5.0}[tier] + rng.normal(0, 0.6), 0.2, 9)),
                h2m_mean=float(h2m[stype] * rng.lognormal(0, 0.15)),
                truck_mix=mix[stype],
                registered_on=date(2015 + int(rng.integers(0, 10)), int(rng.integers(1, 13)), int(rng.integers(1, 28))),
                sustainability=str(rng.choice(["not_assessed", "data_collected", "gap_identified", "documented"], p=[0.45, 0.3, 0.15, 0.1])),
            )
            n_fleet = {"own_estate": 6, "estate": 4, "dealer": 5, "smallholder": 2}[stype]
            sp.plates = [f"XX-{int(rng.integers(1000, 9999)):04d}" for _ in range(n_fleet)]
            n_pl = {"own_estate": 3, "estate": 2, "dealer": 4, "smallholder": 1}[stype]
            for _j in range(n_pl):
                pid += 1
                area = {"own_estate": 900, "estate": 600, "dealer": 150, "smallholder": 60}[stype] * float(rng.lognormal(0, 0.35))
                plantations.append(
                    {
                        "id": pid,
                        "supplier_id": sid,
                        "code": f"PLT-{pid:03d}",
                        "name": f"Demo Plantation {pid:03d} (fictional)",
                        "area_ha": round(area, 1),
                        "district": f"Synthetic District {int(rng.integers(1, 9))}",
                        "lat": round(float(8.6 + rng.random() * 0.9), 3),
                        "lon": round(float(98.9 + rng.random() * 0.9), 3),
                        "planting_year": int(rng.integers(1998, 2019)),
                        "sustainability_json": None,
                    }
                )
                sp.plantation_ids.append(pid)
            suppliers.append(sp)
    tot = sum(s.share for s in suppliers)
    for s_ in suppliers:
        s_.share /= tot
    return suppliers, plantations


def stage_ids() -> dict[str, int]:
    return {code: i for i, (code, *_rest) in enumerate(STAGES, start=1)}


def misc_kw() -> float:
    return A("misc_base_kw")
