"""Causal batch detection pipeline (owner: ml).

Writes, into the DB named by DATABASE_URL: model_registry, ai_predictions, anomaly_events, ai_recommendations (advisory)
and ML alerts. Every detector score at hour t uses data <= t only (expanding baselines / walk-forward refits), and each
anomaly row stores `detected_at` (end of the hour in which the persistence rule fired) in evidence_json because the
frozen anomaly_events table has no detected_at column. The full per-hour score trajectory is stored too, so the API
can show an event exactly as it looked at any `as_of` (no peak / end values from the future).

Idempotent: rows owned by the ML layer are identified by code prefixes / detector names / model ids and replaced.
`scenario_code` on anomaly rows is a playback tag from scenario_runs windows (public demo metadata), never a detector input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.ml.common import MODEL_VERSION, SPLIT_TS, ModelResult, utc_dt
from app.ml.events import Event, score01, severity_for
from app.models.ai import (
    AiPrediction,
    AiRecommendation,
    Alert,
    AlertStatusChange,
    AnomalyEvent,
    AnomalyStatusChange,
    ModelRegistry,
    RecommendationDecision,
)
from app.models.maintenance import WorkOrder

ML_ALERT_PREFIX = "MLA-"
ML_ANOMALY_PREFIX = "ANM-"
ML_REC_PREFIX = "REC-ML-"
SOURCE_BY_DOMAIN = {"production": "production_anomaly", "equipment": "equipment_anomaly", "energy": "energy_anomaly",
                    "logistics": "logistics_anomaly"}
MODULE_BY_DOMAIN = {"production": "production", "equipment": "maintenance", "energy": "energy", "logistics": "logistics"}


@dataclass
class Record:
    domain: str
    detector: str
    model_name: str
    entity_type: str
    entity_id: int | None
    equipment_id: int | None
    process_stage_id: int | None
    start: pd.Timestamp
    end: pd.Timestamp | None
    peak: pd.Timestamp
    detected_at: pd.Timestamp
    score: float
    title: str
    evidence: dict[str, Any]
    contributing: list[str]
    investigation: list[str]
    sensors: list[str] = field(default_factory=list)
    rec_type: str | None = None
    rec_title: str | None = None
    threshold: float | None = None
    raise_alert: bool = True  # truck-level review flags stay anomaly_events only


def _scenario_tag(windows: pd.DataFrame, t: pd.Timestamp) -> str | None:
    for r in windows.itertuples(index=False):
        if r.start_ts <= t < r.end_ts and r.code != "NORMAL_DAY":
            return r.code
    return None


def _evidence_json(ev: dict[str, Any], detected_at: pd.Timestamp, threshold: float | None, detector: str) -> str:
    out = {"detected_at": detected_at.isoformat(), "threshold_raw": threshold, "detector": detector,
           "split": "test" if detected_at >= SPLIT_TS else "train", **ev}
    return json.dumps(out, default=str)


def production_records(detail: dict, stage_ids: dict[str, int]) -> list[Record]:
    from app.ml.production import FACTOR_HINTS, INVESTIGATION, SIGNALS, describe_event  # noqa: PLC0415

    recs = []
    thr = detail["threshold"]
    stage_for = {"steam_pressure_bar": "BOILER_STEAM", "sterilizer_cycle_min": "STERILIZATION", "digester_temp_c": "DIGESTION",
                 "clarifier_temp_c": "CLARIFICATION", "oil_loss_total_pct": "PRESSING", "throughput_tph": "PRESSING"}
    for ev in detail["events"]:
        d = describe_event(ev, detail)
        tot: dict[str, float] = {}
        for p in d["trajectory"]:
            for k, v in p["signals"].items():
                tot[k] = max(tot.get(k, 0), v["z"])
        top = sorted(tot, key=lambda k: -tot[k])[:3]
        main = top[0] if top else None
        recs.append(Record(
            domain="production", detector="robust_z_production", model_name="production_anomaly", entity_type="facility", entity_id=1,
            equipment_id=None, process_stage_id=stage_ids.get(stage_for.get(main or "", ""), None),
            start=ev.start, end=ev.end, peak=ev.peak_ts, detected_at=ev.detected_at, score=float(score01(ev.peak_raw, thr)),
            title=f"Production anomaly: {SIGNALS[main][2] if main else 'process state'}",
            evidence={**d, "signals_meta": {k: {"label": SIGNALS[k][2], "unit": SIGNALS[k][3], "direction": SIGNALS[k][0]} for k in SIGNALS}},
            contributing=[FACTOR_HINTS[k] for k in top], investigation=[INVESTIGATION[k] for k in top], sensors=top,
            rec_type="process_investigation", rec_title=f"Investigate: {SIGNALS[main][2] if main else 'process deviation'}",
            threshold=thr,
        ))
    return recs


def equipment_records(det: dict, wide: pd.DataFrame, equipment: pd.DataFrame) -> list[Record]:
    from app.ml.equipment import REC_BY_TYPE, describe_event  # noqa: PLC0415

    eq = equipment.set_index("code")
    stype = dict(zip(det["sel"]["code"], det["sel"]["sensor_type"], strict=True))
    sunit = dict(zip(det["sel"]["code"], det["sel"]["unit"], strict=True))
    thr = det["threshold"]
    recs = []
    for ev in list(det["events"]) + list(det["health"]):
        if ev.key not in eq.index:
            continue
        e = eq.loc[ev.key]
        d = describe_event(ev, det, wide)
        if ev.info.get("sensor_health"):
            kind = ev.info["sensor_health"]
            sensors = [ev.info["sensor"]]
            rec_type, rec_text = REC_BY_TYPE["sensor"]
            contributing = [f"sensor signal {kind.replace('_', ' ')} on {ev.info['sensor']} (data-quality issue, not necessarily equipment)"]
            score, detector, title = 0.6, "sensor_health_rules", f"{ev.key}: sensor {kind.replace('_', ' ')} ({ev.info['sensor']})"
            d["sensor_meta"] = {ev.info["sensor"]: {"type": ev.info["sensor_type"], "unit": sunit.get(ev.info["sensor"], "")}}
        else:
            tot: dict[str, float] = {}
            for p in d["trajectory"]:
                for k, v in p["signals"].items():
                    tot[k] = max(tot.get(k, 0), v["z"])
            sensors = sorted(tot, key=lambda k: -tot[k])[:3]
            main_t = stype.get(sensors[0], "vibration") if sensors else "vibration"
            rec_type, rec_text = REC_BY_TYPE[main_t]
            contributing = [f"{s} ({stype.get(s)}) above its usual running range" for s in sensors]
            score, detector = float(score01(ev.peak_raw, thr)), "robust_z_equipment"
            title = f"{ev.key}: abnormal {', '.join(sorted({stype.get(s, '') for s in sensors}))}"
            d["sensor_meta"] = {s: {"type": stype.get(s), "unit": sunit.get(s, "")} for s in sensors}
        recs.append(Record(
            domain="equipment", detector=detector, model_name="equipment_anomaly", entity_type="equipment", entity_id=int(e["id"]),
            equipment_id=int(e["id"]), process_stage_id=None if pd.isna(e["process_stage_id"]) else int(e["process_stage_id"]),
            start=ev.start, end=ev.end, peak=ev.peak_ts, detected_at=ev.detected_at, score=score, title=title, evidence=d,
            contributing=contributing, investigation=[rec_text], sensors=sensors, rec_type=rec_type,
            rec_title=f"{ev.key}: {rec_text.split(';')[0]}", threshold=None if ev.info.get("sensor_health") else thr,
        ))
    return recs


def generic_records(events: list[Event], thr: float, describe, **kw) -> list[Record]:
    """For energy / logistics detectors: `describe(ev)` returns dict(evidence, contributing, investigation, title, ...)."""
    out = []
    for ev in events:
        info = describe(ev)
        out.append(Record(start=ev.start, end=ev.end, peak=ev.peak_ts, detected_at=ev.detected_at,
                          score=float(score01(ev.peak_raw, thr)), threshold=thr, **{**kw, **info}))
    return out


# ---------------------------------------------------------------------------- DB write
def write_all(db: Session, results: list[ModelResult], records: list[Record], predictions: list[dict], windows: pd.DataFrame,
              window_end: pd.Timestamp) -> dict[str, int]:
    names = [r.name for r in results]
    old_models = db.execute(select(ModelRegistry.id).where(ModelRegistry.name.in_(names))).scalars().all()
    old_anoms = db.execute(select(AnomalyEvent.id).where(AnomalyEvent.code.like(f"{ML_ANOMALY_PREFIX}%"))).scalars().all()
    old_recs = db.execute(select(AiRecommendation.id).where(AiRecommendation.code.like(f"{ML_REC_PREFIX}%"))).scalars().all()
    old_alerts = db.execute(select(Alert.id).where(Alert.code.like(f"{ML_ALERT_PREFIX}%"))).scalars().all()
    # detach anything referencing rows we are about to replace (session-scoped visitor rows)
    if old_alerts or old_recs or old_anoms:
        db.execute(update(WorkOrder).where(WorkOrder.alert_id.in_(old_alerts)).values(alert_id=None))
        db.execute(update(WorkOrder).where(WorkOrder.recommendation_id.in_(old_recs)).values(recommendation_id=None))
        db.execute(update(WorkOrder).where(WorkOrder.anomaly_event_id.in_(old_anoms)).values(anomaly_event_id=None))
        db.execute(delete(AlertStatusChange).where(AlertStatusChange.alert_id.in_(old_alerts)))
        db.execute(delete(RecommendationDecision).where(RecommendationDecision.recommendation_id.in_(old_recs)))
        db.execute(delete(AnomalyStatusChange).where(AnomalyStatusChange.anomaly_event_id.in_(old_anoms)))
        db.execute(delete(Alert).where(Alert.id.in_(old_alerts)))
        db.execute(update(Alert).where(Alert.anomaly_event_id.in_(old_anoms)).values(anomaly_event_id=None))
        db.execute(update(Alert).where(Alert.recommendation_id.in_(old_recs)).values(recommendation_id=None))
        db.execute(delete(AiRecommendation).where(AiRecommendation.id.in_(old_recs)))
        db.execute(delete(AnomalyEvent).where(AnomalyEvent.id.in_(old_anoms)))
    if old_models:
        db.execute(delete(AiPrediction).where(AiPrediction.model_id.in_(old_models)))
        db.execute(update(AnomalyEvent).where(AnomalyEvent.model_id.in_(old_models)).values(model_id=None))
        db.execute(update(AiRecommendation).where(AiRecommendation.model_id.in_(old_models)).values(model_id=None))
        db.execute(delete(ModelRegistry).where(ModelRegistry.id.in_(old_models)))
    db.flush()

    model_ids: dict[str, int] = {}
    for r in results:
        row = ModelRegistry(
            name=r.name, version=MODEL_VERSION, task=r.task, algorithm=r.algorithm[:64], features_json=json.dumps(r.features),
            metrics_json=json.dumps({"headline": r.headline, "summary": _summary(r)}, default=str), beats_baseline=r.beats_baseline,
            train_window_start=utc_dt(r.train_window[0]), train_window_end=utc_dt(r.train_window[1]),
            test_window_start=utc_dt(r.test_window[0]), test_window_end=utc_dt(r.test_window[1]),
            artifact_path=f"data/models/{r.name}/{MODEL_VERSION}/model.joblib",
            model_card_path=f"docs/ai/model-cards/{r.name}.md", status="active", data_kind="synthetic",
        )
        db.add(row)
        db.flush()
        model_ids[r.name] = row.id

    recs_sorted = sorted(records, key=lambda x: (x.detected_at, x.domain, x.entity_id or 0))
    n_alerts = 0
    for i, rc in enumerate(recs_sorted, start=1):
        sev = severity_for(rc.score)
        ended = rc.end is not None and rc.end < window_end - pd.Timedelta(hours=1)
        a = AnomalyEvent(
            code=f"{ML_ANOMALY_PREFIX}{rc.domain[:3].upper()}-{i:05d}", detector=rc.detector, model_id=model_ids.get(rc.model_name),
            domain=rc.domain, entity_type=rc.entity_type, entity_id=rc.entity_id, equipment_id=rc.equipment_id,
            process_stage_id=rc.process_stage_id, start_ts=utc_dt(rc.start), end_ts=utc_dt(rc.end) if ended else None,
            peak_ts=utc_dt(rc.peak), score=round(min(1.0, max(0.0, rc.score)), 4), severity=sev,
            evidence_json=_evidence_json({**rc.evidence, "title": rc.title, "investigation": rc.investigation, "sensors": rc.sensors},
                                         rc.detected_at, rc.threshold, rc.detector),
            contributing_json=json.dumps(rc.contributing), status="new", scenario_code=_scenario_tag(windows, rc.detected_at),
            data_kind="synthetic",
        )
        db.add(a)
        db.flush()
        rec_id = None
        if rc.rec_type:
            rec = AiRecommendation(
                code=f"{ML_REC_PREFIX}{i:05d}", rec_type=rc.rec_type[:32], title=(rc.rec_title or rc.title)[:200],
                rationale=("Advisory only - possible contributing factors: " + "; ".join(rc.contributing))[:2000],
                evidence_json=json.dumps({"anomaly_code": a.code, "score": a.score, "detected_at": rc.detected_at.isoformat()}),
                equipment_id=rc.equipment_id, process_stage_id=rc.process_stage_id, anomaly_event_id=a.id,
                model_id=model_ids.get(rc.model_name), priority=sev, risk_score=None, advisory=True, status="proposed",
                created_at=utc_dt(rc.detected_at), data_kind="synthetic",
            )
            db.add(rec)
            db.flush()
            rec_id = rec.id
        if not rc.raise_alert:
            continue
        db.add(Alert(
            code=f"{ML_ALERT_PREFIX}{i:05d}", source=SOURCE_BY_DOMAIN[rc.domain], module=MODULE_BY_DOMAIN[rc.domain], severity=sev,
            status="new", title=rc.title[:200],
            message=("ML anomaly (advisory, needs human verification). Possible contributing factors: " + "; ".join(rc.contributing))[:2000],
            raised_at=utc_dt(rc.detected_at), resolved_at=utc_dt(rc.end) if ended else None, facility_id=1, equipment_id=rc.equipment_id,
            process_stage_id=rc.process_stage_id, anomaly_event_id=a.id, recommendation_id=rec_id,
            truck_trip_id=rc.entity_id if rc.entity_type == "truck_trip" else None,
            evidence_json=json.dumps({"detector": rc.detector, "anomaly_code": a.code, "score": a.score, "model_version": MODEL_VERSION,
                                      "rule_type": "ml_anomaly"}),
            scenario_code=a.scenario_code, data_kind="synthetic",
        ))
        n_alerts += 1

    n_pred = 0
    batch = []
    for p in predictions:
        mid = model_ids.get(p.pop("model"))
        if mid is None:
            continue
        batch.append({**p, "model_id": mid, "data_kind": "forecast"})
        if len(batch) >= 5000:
            db.execute(AiPrediction.__table__.insert(), batch)
            n_pred += len(batch)
            batch = []
    if batch:
        db.execute(AiPrediction.__table__.insert(), batch)
        n_pred += len(batch)
    db.commit()
    return {"models": len(model_ids), "anomaly_events": len(recs_sorted), "alerts": n_alerts, "predictions": n_pred}


def _summary(r: ModelResult) -> dict:
    m = r.metrics
    keys = ("served_model", "best_baseline", "threshold_z", "rows", "intervals", "press_vibration_lead_time")
    out = {k: m[k] for k in keys if k in m}
    if "test" in m and isinstance(m["test"], dict) and "per_label" in m["test"]:
        out["test"] = {k: v for k, v in m["test"].items() if k != "per_label"}
    elif "test" in m:
        out["test"] = m["test"]
    return out


def to_dt(x: Any) -> datetime | None:
    return utc_dt(x)
