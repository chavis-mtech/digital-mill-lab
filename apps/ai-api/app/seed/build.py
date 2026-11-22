"""Orchestrates the full deterministic build: simulate -> rows -> database -> checksum -> manifest."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import numpy as np

from app.config import REPO_ROOT
from app.seed.alerts import build_alerts
from app.seed.assumptions import DEFAULT_SEED, GENERATOR_VERSION, P
from app.seed.calendar import build_prices
from app.seed.core import run_core
from app.seed.energy import energy_balance, equipment_state
from app.seed.maintenance import build_maintenance
from app.seed.outputs import build_energy_rows, build_logistics, build_production
from app.seed.registry import STAGES, sensor_specs
from app.seed.sensors import QUALITY, build_sensor_series
from app.seed.timebase import TimeBase
from app.seed.writer import content_checksum, is_empty, reset_schema, write_all

MANIFEST_PATH = REPO_ROOT / "data/synthetic/MANIFEST.json"


def _strip(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def generate(anchor: date, days: int, seed: int) -> dict:
    """Pure in-memory generation. Returns {'tables': {...}, 'readings': {...}, 'core': core, ...}."""
    tb = TimeBase(anchor, days)
    core = run_core(tb, seed)
    stage_ids = {code: i for i, (code, *_r) in enumerate(STAGES, start=1)}
    ids = {"facility": 1, "line": 1, "stage": stage_ids, "equip": {e.code: e.id for e in core.equip}}
    t: dict[str, list[dict]] = {}
    t["companies"] = [{"id": 1, "code": "DEMO-PALM-CO", "name": "Demo Palm Oil Co. (fictional)", "is_fictional": True, "data_kind": "synthetic"}]
    t["facilities"] = [{"id": 1, "company_id": 1, "code": "MILL-A", "name": "Demo Palm Mill A", "facility_type": "palm_oil_mill",
                        "capacity_tph": float(P("mill_capacity_t_ffb_per_h")), "timezone": "Asia/Bangkok",
                        "region": "Southern Thailand (synthetic location)", "data_kind": "synthetic"}]
    t["production_lines"] = [{"id": 1, "facility_id": 1, "code": "MILL-A-L1", "name": "Processing line 1", "capacity_tph": float(P("mill_capacity_t_ffb_per_h"))}]
    t["process_stages"] = [{"id": stage_ids[c], "facility_id": 1, "code": c, "name_en": en, "name_th": th, "sequence": seq, "kind": kind,
                            "description": None} for c, en, th, seq, kind in STAGES]
    t["equipment"] = [{"id": e.id, "facility_id": 1, "line_id": 1 if e.stage not in ("BOILER_STEAM", "POWER", "WATER_TREATMENT", "POME_TREATMENT") else None,
                       "process_stage_id": stage_ids[e.stage], "code": e.code, "name": e.name, "equipment_type": e.etype,
                       "manufacturer": "Generic (synthetic)", "install_date": date(2008 + (e.id * 7) % 14, 1 + (e.id * 5) % 12, 1),
                       "criticality": e.criticality, "rated_power_kw": e.rated_kw, "rated_capacity": e.rated_capacity,
                       "rated_capacity_unit": e.cap_unit, "is_active": True, "data_kind": "synthetic"} for e in core.equip]
    sensors = sensor_specs(core.equip)
    t["sensors"] = [{"id": s.id, "equipment_id": s.equip.id, "code": s.code, "name": s.name, "sensor_type": s.stype, "unit": s.unit,
                     "normal_min": s.normal_min, "normal_max": s.normal_max, "warn_limit": s.warn, "crit_limit": s.crit,
                     "low_is_bad": s.low_is_bad, "sampling_seconds": s.sampling_s, "data_kind": "synthetic"} for s in sensors]
    t["suppliers"] = [{"id": s.id, "code": s.code, "name": s.name, "supplier_type": s.stype, "province": "Southern Thailand (synthetic)",
                       "registered_on": s.registered_on, "is_active": True, "sustainability_status": s.sustainability, "quality_tier": s.tier,
                       "data_kind": "synthetic"} for s in core.suppliers]
    t["plantations"] = [{**p, "data_kind": "synthetic"} for p in core.plantations]
    t["technicians"] = []
    prices = build_prices(tb, core.rngs)
    t["prices"] = prices
    pbd = {c: np.array([p["price"] for p in prices if p["commodity"] == c]) for c in ("electricity", "diesel")}
    eq_state = equipment_state(core)
    eb = energy_balance(core, eq_state, pbd)
    log = build_logistics(core, 1)
    for k in ("truck_trips", "weighbridge_tickets", "ffb_deliveries", "ffb_batches", "queue_events"):
        t[k] = log[k]
    prod = build_production(core, ids, eq_state, log)
    for k in ("process_hourly", "production_shifts", "production_batches", "byproduct_outputs", "batch_inputs", "cpo_output_lots",
              "lot_compositions", "quality_measurements"):
        t[k] = prod[k]
    t["energy_consumption"] = build_energy_rows(core, ids, stage_ids, eq_state, eb)
    series = build_sensor_series(core, sensors, eq_state, eb, prod)
    alerts = build_alerts(core, ids, sensors, series, prod, eb)
    maint = build_maintenance(core, ids, alerts)
    for k, v in maint.items():
        t[k] = v
    t["alerts"] = _strip(alerts)
    # scenario runs
    t["scenario_runs"] = [{
        "id": i, "code": s.code, "name_en": s.name_en, "name_th": s.name_th, "description": s.description, "start_ts": tb.ts(s.start),
        "end_ts": tb.ts(s.end), "focus_ts": tb.ts(s.focus), "baseline_ts": tb.ts(s.baseline) if s.baseline is not None else None,
        "primary_stage_code": s.stage, "primary_equipment_id": ids["equip"].get(s.equipment_code) if s.equipment_code else None,
        "expected_effects_json": json.dumps(s.effects, ensure_ascii=False), "seed": seed, "data_kind": "synthetic",
    } for i, s in enumerate(sorted(core.scenarios, key=lambda s: s.focus), start=1)]
    # injected events (ground truth, PRIVATE)
    sensor_id = {s.code: s.id for s in sensors}
    sup_id = {s.code: s.id for s in core.suppliers}
    inj_rows = []
    for k, i in enumerate(sorted(core.injected, key=lambda x: (x.start, x.code)), start=1):
        ent_id = None
        if i.entity_type == "equipment":
            ent_id = ids["equip"].get(i.entity_code)
        elif i.entity_type == "sensor":
            ent_id = sensor_id.get(i.entity_code)
        elif i.entity_type == "supplier":
            ent_id = sup_id.get(i.entity_code)
        elif i.entity_type == "process_stage":
            ent_id = stage_ids.get(i.entity_code)
        elif i.entity_type == "facility":
            ent_id = 1
        inj_rows.append({"id": k, "code": i.code, "scenario_code": i.scenario_code, "event_type": i.event_type, "domain": i.domain,
                         "entity_type": i.entity_type, "entity_id": ent_id, "equipment_id": ids["equip"].get(i.equipment_code) if i.equipment_code else None,
                         "process_stage_id": stage_ids.get(i.stage_code) if i.stage_code else None, "start_ts": tb.ts(i.start),
                         "end_ts": tb.ts(min(i.end, tb.minutes)), "magnitude": i.magnitude,
                         "params_json": json.dumps({**i.params, "entity_code": i.entity_code}, sort_keys=True), "notes": i.notes})
    for lab in core.outlier_labels:
        tr = core.trucks[lab["truck_idx"]]
        inj_rows.append({"id": len(inj_rows) + 1, "code": f"INJ-BG-WEIGHT-{tr.idx + 1:05d}", "scenario_code": None, "event_type": "implausible_weight",
                         "domain": "logistics", "entity_type": "truck_trip", "entity_id": tr.idx + 1, "equipment_id": ids["equip"]["WB-01"],
                         "process_stage_id": stage_ids["FFB_RECEPTION"], "start_ts": tb.ts(tr.arrival), "end_ts": tb.ts(tr.exit if tr.exit is not None else tr.arrival),
                         "magnitude": round(lab["payload_kg"] / lab["class_max_kg"], 3), "params_json": json.dumps({**lab, "severity": "low"}, sort_keys=True),
                         "notes": "Net weight above the truck-class payload maximum (data plausibility check; not an accusation)."})
    t["injected_events"] = inj_rows
    # sensor readings (flattened, ordered by sensor then time)
    sid_l, ts_l, v_l, q_l = [], [], [], []
    for s in sensors:
        ser = series[s.id]
        sid_l.append(np.full(ser["t"].size, s.id, dtype=np.int64))
        ts_l.append(ser["t"])
        v_l.append(ser["v"])
        q_l.append(ser["q"])
    tmin = np.concatenate(ts_l)
    readings = {"sensor_id": np.concatenate(sid_l), "ts_text": tb.ts_strings(tmin), "value": np.concatenate(v_l).astype(float),
                "quality": QUALITY[np.concatenate(q_l)]}
    base = np.datetime64(tb.start_utc.replace(tzinfo=None), "us")
    readings["ts_dt"] = base + (np.round(tmin * 60).astype(np.int64) * 1_000_000).astype("timedelta64[us]")
    return {"tables": t, "readings": readings, "core": core, "series": series, "sensors": sensors, "eb": eb, "prod": prod}


def build(db_url: str, *, seed: int = DEFAULT_SEED, anchor: date | None = None, days: int | None = None, if_empty: bool = False,
          write_manifest: bool = True, manifest_path: Path | None = None, log=print) -> dict:
    from app.config import get_settings
    from app.db.session import get_engine

    settings = get_settings()
    anchor = anchor or settings.demo_anchor
    days = days or settings.dataset_days
    engine = get_engine(db_url)
    if if_empty and not is_empty(engine):
        log("seed: database already populated - nothing to do (--if-empty)")
        return {"skipped": True}
    t0 = time.perf_counter()
    gen = generate(anchor, days, seed)
    t1 = time.perf_counter()
    reset_schema(engine)
    counts = write_all(engine, gen["tables"], gen["readings"])
    t2 = time.perf_counter()
    checksum, per_table = content_checksum(engine)
    t3 = time.perf_counter()
    core = gen["core"]
    tb = core.tb
    size = None
    if db_url.startswith("sqlite:///"):
        p = Path(db_url[len("sqlite:///"):])
        size = p.stat().st_size if p.exists() else None
    summary = {
        "generator_version": GENERATOR_VERSION, "seed": seed, "anchor": anchor.isoformat(), "days": days,
        "window_start_utc": tb.start_utc.isoformat(), "window_end_utc": tb.end_utc.isoformat(), "checksum_sha256": checksum,
        "row_counts": dict(sorted(counts.items())), "total_rows": int(sum(counts.values())),
        "timing_s": {"generate": round(t1 - t0, 1), "write": round(t2 - t1, 1), "checksum": round(t3 - t2, 1), "total": round(t3 - t0, 1)},
        "db_size_mb": round(size / 1e6, 1) if size else None, "quota_iterations": core.quota_iterations,
        "scenarios": [{"code": s.code, "start_local": tb.iso_local(s.start), "end_local": tb.iso_local(s.end), "focus_local": tb.iso_local(s.focus),
                       "baseline_local": tb.iso_local(s.baseline) if s.baseline is not None else None, "start_utc": tb.ts(s.start).isoformat() + "Z",
                       "end_utc": tb.ts(s.end).isoformat() + "Z", "focus_utc": tb.ts(s.focus).isoformat() + "Z",
                       "primary_equipment": s.equipment_code} for s in sorted(core.scenarios, key=lambda s: s.focus)],
        "recommended_ml_split": {"train_end_local": tb.iso_local(max(0, (tb.days - 37)) * 1440),
                                 "note": "Temporal split: >= 2 labelled scenario episodes + background events on each side (see docs/DATA_GENERATION.md)."},
        "per_table_sha256": per_table,
    }
    log(f"seed: {summary['total_rows']:,} rows in {summary['timing_s']['total']} s (generate {summary['timing_s']['generate']} s, "
        f"write {summary['timing_s']['write']} s), db {summary['db_size_mb']} MB, checksum {checksum[:16]}...")
    if write_manifest:
        mp = manifest_path or MANIFEST_PATH
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        log(f"seed: wrote {mp}")
    return summary
