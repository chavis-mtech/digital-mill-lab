"""Inference / read service for the AI endpoints (owner: ml).

as_of contract: actuals and features are read with ts + 1 h <= as_of (an hourly row is complete at the end of its hour);
anomaly events are visible only when evidence.detected_at <= as_of, and are rendered from their stored trajectory
truncated at as_of (no end / peak from the future). Artifacts are loaded once per process (lru_cache).
injected_events are never read here.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.ml import cards as card_data
from app.ml.common import MODEL_NAMES, MODEL_VERSION, MODELS_DIR, load_metrics
from app.ml.events import score01, severity_for
from app.models.ai import AnomalyEvent, AnomalyStatusChange, ModelRegistry
from app.models.core import Equipment, ProcessStage
from app.services.demo_context import DemoContext, provenance, session_filter

REPO = MODELS_DIR.parents[1]


def data_guard(fn):
    """Unseeded / unmigrated DB -> 503 envelope instead of a 500."""
    import functools  # noqa: PLC0415

    from sqlalchemy.exc import OperationalError, ProgrammingError  # noqa: PLC0415

    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except (pd.errors.DatabaseError, OperationalError, ProgrammingError) as exc:
            raise ApiError(503, "data_unavailable", "Demo data is not available - run `make seed` and `make models`.",
                           {"model_layer": "ml"}) from exc

    return wrapper


# ---------------------------------------------------------------------------- artifacts & model info
@lru_cache(maxsize=16)
def artifact(name: str) -> dict:
    p = MODELS_DIR / name / MODEL_VERSION / "model.joblib"
    if not p.exists():
        raise ApiError(503, "model_not_trained", f"Model '{name}' has no trained artifact. Run `make models`.", {"model": name})
    return joblib.load(p)


def _metrics(name: str) -> dict:
    m = load_metrics(name)
    if m is None:
        raise ApiError(503, "model_not_trained", f"Model '{name}' has no metrics. Run `make models`.", {"model": name})
    return m


def model_info(db: Session | None, name: str) -> dict:
    if name not in MODEL_NAMES:
        not_found("model", name)
    m = _metrics(name)
    trained_at = None
    status = "trained"
    if db is not None:
        try:
            row = db.execute(select(ModelRegistry).where(ModelRegistry.name == name, ModelRegistry.version == MODEL_VERSION)).scalar_one_or_none()
        except Exception:  # noqa: BLE001 - table may be missing in an unseeded DB
            db.rollback()
            row = None
        if row is not None:
            trained_at, status = row.trained_at, row.status
    if trained_at is None:
        p = MODELS_DIR / name / MODEL_VERSION / "metrics.json"
        trained_at = datetime.fromtimestamp(p.stat().st_mtime).astimezone()
    metrics = []
    for h in m["headline"]:
        bb = None
        if h.get("model") is not None and h.get("baseline") is not None:
            if h["better_is"] == "lower":
                bb = h["model"] < h["baseline"]
            elif h["better_is"] == "higher":
                bb = h["model"] > h["baseline"]
        metrics.append({"name": h["name"], "model": h.get("model"), "baseline": h.get("baseline"), "baseline_name": h.get("baseline_name"),
                        "better_is": h["better_is"], "beats_baseline": bb})
    return {"name": name, "version": MODEL_VERSION, "task": m["task"], "algorithm": m["algorithm"], "trained_at": trained_at,
            "train_window": [pd.Timestamp(x).to_pydatetime() for x in m["train_window"]],
            "test_window": [pd.Timestamp(x).to_pydatetime() for x in m["test_window"]], "metrics": metrics, "status": status,
            "data_kind": "synthetic"}


def model_card(db: Session | None, name: str) -> dict:
    info = model_info(db, name)
    c = card_data.CARDS[name]
    m = _metrics(name)
    md_path = REPO / "docs" / "ai" / "model-cards" / f"{name}.md"
    return {**info, "purpose": c["purpose"], "input_features": m["features"], "training_data": c["training_data"],
            "synthetic_data_assumptions": card_data.COMMON_ASSUMPTIONS + c["assumptions"], "evaluation_method": c["evaluation"],
            "limitations": c["limitations"], "known_failure_modes": c["failure_modes"], "deployment_status": c["status"],
            "card_markdown": md_path.read_text() if md_path.exists() else None}


def mv(name: str) -> str:
    return f"{name}@{MODEL_VERSION}"


# ---------------------------------------------------------------------------- helpers
def _raw(db: Session):
    return db.connection().connection.driver_connection


def _ts(t: datetime | pd.Timestamp) -> str:
    return pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S.%f")  # matches the stored text format


def _last_complete_hour(as_of: datetime) -> pd.Timestamp:
    return pd.Timestamp(as_of).tz_convert("UTC").floor("h") - pd.Timedelta(hours=1)


def _series(key: str, label: str, unit: str, pts: list[tuple], prov: dict) -> dict:
    return {"key": key, "label": label, "unit": unit, "points": [{"t": t, "v": None if v is None or pd.isna(v) else round(float(v), 4)}
                                                                 for t, v in pts], "provenance": prov}


# ---------------------------------------------------------------------------- OER
def _oer_recent(db: Session, ctx: DemoContext, hours: int = 96) -> pd.DataFrame:
    from app.ml import oer  # noqa: PLC0415

    last = _last_complete_hour(ctx.as_of)
    start = last - pd.Timedelta(hours=hours)
    df = oer.build_frame(_raw(db), start=_ts(start), end=_ts(last))
    return df[df.index <= last]


@data_guard
def oer_forecast(db: Session, ctx: DemoContext, horizon_h: int) -> dict:
    from app.ml import oer  # noqa: PLC0415

    art = artifact("oer_forecast")
    df = _oer_recent(db, ctx)
    rows = oer.model_rows(df).dropna(subset=art["features"])
    prov_a = provenance("synthetic_actual", "process_hourly.oer_pct", ctx)
    prov_f = provenance("forecast", "oer_forecast", ctx, mv("oer_forecast"))
    actual = df[df["is_model_row"]]["oer_pct"].iloc[-48:]
    if rows.empty:
        raise ApiError(409, "insufficient_data", "No running hours with complete features before as_of", {"as_of": ctx.as_of.isoformat()})
    last = rows.iloc[-1].copy()
    q = art["conformal_half_width"]
    level = float(actual.iloc[-24:].mean())
    base_t = _last_complete_hour(ctx.as_of)
    pts, bl = [], []
    xs = []
    for h in range(1, horizon_h + 1):
        t = base_t + pd.Timedelta(hours=h)
        r = last.copy()
        loc = t + pd.Timedelta(hours=7)
        r["hour_local"], r["weekday_local"], r["day_of_year"] = loc.hour, loc.weekday(), loc.day_of_year
        for f in art["features"]:
            if f.endswith("_d24"):
                r[f] = 0.0  # persistence of conditions: no change vs trailing mean
        r["oer_level_lag24"] = level
        xs.append(r)
    X = pd.DataFrame(xs)
    pred = art["model"].predict(X)
    for i, h in enumerate(range(1, horizon_h + 1)):
        t = base_t + pd.Timedelta(hours=h)
        pts.append({"t": t.to_pydatetime(), "v": round(float(pred[i]), 4), "lower": round(float(pred[i] - q), 4),
                    "upper": round(float(pred[i] + q), 4)})
        bl.append((t.to_pydatetime(), level))
    return {
        "horizon_h": horizon_h,
        "forecast": {"key": "oer_forecast", "label": "Expected OER (conditions held at last observed hour)", "unit": "%", "points": pts,
                     "interval": f"90% split-conformal interval (+/- {q:.2f} pp, test coverage "
                                 f"{_metrics('oer_forecast')['metrics']['intervals']['split_conformal']['test_coverage']}); does not widen with horizon",
                     "provenance": prov_f},
        "actual": _series("oer_actual", "OER (synthetic actual)", "%", [(t.to_pydatetime(), v) for t, v in actual.items()], prov_a),
        "baseline": _series("oer_baseline_rolling24", "Naive baseline: mean of last 24 running hours", "%", bl,
                            provenance("forecast", "naive_rolling_24h", ctx, None)),
        "model": model_info(db, "oer_forecast"),
        "granularity_note": _metrics("oer_forecast")["metrics"].get("granularity_verdict"),
    }


def _nowcast(df: pd.DataFrame, art: dict) -> dict | None:
    from app.ml import oer_agg  # noqa: PLC0415

    nc = art.get("nowcast")
    if nc is None:
        return None
    d = df[df["is_model_row"]].dropna(subset=oer_agg.DRIVERS + ["oer_pct"])
    if d.empty:
        return None
    day = (d.index + pd.Timedelta(hours=7)).floor("D")
    for target in sorted(day.unique(), reverse=True)[:2]:
        blk = d[day == target]
        if blk["ffb_processed_t"].sum() >= 150 or target == day.min():
            break
    w = blk["ffb_processed_t"]
    row = (blk[oer_agg.DRIVERS + ["oer_pct"]].mul(w, axis=0).sum() / w.sum())
    base, pred, contrib = oer_agg.contributions(nc["model"], row)
    resid = float(row["oer_pct"]) - pred
    band = nc["residual_band"]
    return {"granularity": "day", "period_start": blk.index.min().to_pydatetime(), "period_end": (blk.index.max() + pd.Timedelta(hours=1)).to_pydatetime(),
            "running_hours": int(len(blk)), "actual_oer_pct": round(float(row["oer_pct"]), 4), "expected_oer_pct": round(pred, 4),
            "typical_conditions_oer_pct": round(base, 4), "residual_pp": round(resid, 4), "residual_band_pp": round(band, 4),
            "outside_band": bool(abs(resid) > band),
            "contributions": [{"feature": c["feature"], "label": c["label"], "value": c["value"], "contribution": c["contribution"],
                               "importance": None} for c in contrib[:8]],
            "note": "Business day so far (complete hours <= as_of), FFB-weighted. Ridge on observable drivers only; contributions are vs "
                    "average training conditions. Out-of-sample attribution was unreliable on OER_DEGRADATION (see model card); "
                    "use the residual as a flag, not the attribution as a cause. Days before 2026-10-15 are IN-SAMPLE for this model."}


@data_guard
def oer_explanation(db: Session, ctx: DemoContext) -> dict:
    from app.ml import oer  # noqa: PLC0415

    art = artifact("oer_forecast")
    df = _oer_recent(db, ctx)
    rows = oer.model_rows(df).dropna(subset=art["features"])
    if rows.empty:
        raise ApiError(409, "insufficient_data", "No running hours with complete features before as_of", {"as_of": ctx.as_of.isoformat()})
    row = rows.iloc[-1]
    pred, contribs = oer.explain(art, row)
    q = art["conformal_half_width"]
    return {"target_ts": rows.index[-1].to_pydatetime(), "predicted_oer_pct": round(pred, 4), "expected_range": [round(pred - q, 4), round(pred + q, 4)],
            "contributions": contribs[:12],
            "method": "permutation importance on the test period (global) + local occlusion: prediction change when one feature is set to its "
                      "training median",
            "caveat": "Associations learned from synthetic data; not proven causes.", "model": model_info(db, "oer_forecast"),
            "nowcast": _nowcast(df, art), "granularity_note": _metrics("oer_forecast")["metrics"].get("granularity_verdict")}


# ---------------------------------------------------------------------------- anomalies
def _effective_status(db: Session, ctx: DemoContext, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    q = (select(AnomalyStatusChange).where(AnomalyStatusChange.anomaly_event_id.in_(ids), session_filter(AnomalyStatusChange.session_id, ctx))
         .order_by(AnomalyStatusChange.changed_at, AnomalyStatusChange.id))
    out: dict[int, str] = {}
    for ch in db.execute(q).scalars():
        if ch.session_id is not None:
            out[ch.anomaly_event_id] = ch.to_status
    return out


def _visible(ev: dict, as_of: datetime) -> bool:
    d = ev.get("detected_at")
    return d is not None and pd.Timestamp(d) <= pd.Timestamp(as_of)


def anomaly_out(a: AnomalyEvent, ctx: DemoContext, eq: Equipment | None, stage_code: str | None, status: str | None) -> dict:
    ev = json.loads(a.evidence_json or "{}")
    as_of = pd.Timestamp(ctx.as_of)
    traj = [p for p in ev.get("trajectory", []) if pd.Timestamp(p["t"]) + pd.Timedelta(hours=1) <= as_of] or \
           [p for p in ev.get("trajectory", []) if pd.Timestamp(p["t"]) <= as_of]
    thr = ev.get("threshold_raw")
    score, peak_ts = a.score, a.peak_ts
    if traj:
        pk = max(traj, key=lambda p: p["raw"] or 0)
        peak_ts = pd.Timestamp(pk["t"]).floor("s").to_pydatetime()
        if thr:
            score = float(score01(pk["raw"] or 0, thr))
    else:
        pk = None
    ended = a.end_ts is not None and pd.Timestamp(a.end_ts) <= as_of
    meta = {**ev.get("signals_meta", {}), **ev.get("sensor_meta", {})}
    evidence = []
    if pk:
        for k, v in pk.get("signals", {}).items():
            m = meta.get(k, {})
            unit = m.get("unit", "")
            nr = None
            if v.get("median") is not None and v.get("mad") is not None:
                nr = {"low": round(v["median"] - 3 * v["mad"], 4), "high": round(v["median"] + 3 * v["mad"], 4), "unit": unit,
                      "basis": "robust baseline: median +/- 3 x MAD of this signal's own history older than 2 days (causal)"}
            elif m.get("high") is not None:
                nr = {"low": None, "high": m["high"], "unit": unit, "basis": "training-period envelope (P99 / P99.5)"}
            evidence.append({"metric": k, "label": m.get("label", k), "observed": v.get("observed"), "expected": v.get("median"),
                             "normal_range": nr, "unit": unit, "window_start": a.start_ts, "window_end": peak_ts,
                             "note": None if v.get("z") is None else f"robust z = {v['z']}"})
    entity = None
    if a.entity_type and a.entity_id is not None:
        entity = {"type": a.entity_type, "id": a.entity_id, "code": eq.code if (eq and a.entity_type == "equipment") else None,
                  "label": eq.name if (eq and a.entity_type == "equipment") else None}
    return {
        "id": a.id, "code": a.code, "detector": a.detector, "domain": a.domain, "entity": entity,
        "equipment": {"type": "equipment", "id": eq.id, "code": eq.code, "label": eq.name} if eq else None,
        "process_stage_code": stage_code, "start_ts": a.start_ts, "end_ts": a.end_ts if ended else None, "peak_ts": peak_ts,
        "score": round(min(1.0, max(0.0, score)), 4), "severity": severity_for(score) if thr else a.severity,
        "status": status or a.status, "evidence": evidence, "contributing_factors": json.loads(a.contributing_json or "[]"),
        "recommended_investigation": ev.get("investigation", []), "contributing_sensors": ev.get("sensors", []),
        "scenario_code": a.scenario_code, "model_version": f"{_model_for_domain(a.domain)}@{MODEL_VERSION}",
    }


def _model_for_domain(domain: str) -> str:
    return {"production": "production_anomaly", "equipment": "equipment_anomaly", "energy": "energy_anomaly", "logistics": "logistics_anomaly"}[domain]


@data_guard
def list_anomalies(db: Session, ctx: DemoContext, domain: str, days: int, *, equipment_id: int | None = None, severity: str | None = None,
                   status: str | None = None, limit: int = 50) -> dict:
    start, end = ctx.period_bounds(days)
    q = select(AnomalyEvent).where(AnomalyEvent.domain == domain, AnomalyEvent.start_ts <= end,
                                   AnomalyEvent.code.like("ANM-%"))
    if equipment_id is not None:
        q = q.where(AnomalyEvent.equipment_id == equipment_id)
    rows = db.execute(q.order_by(AnomalyEvent.start_ts.desc())).scalars().all()
    vis = []
    for a in rows:
        ev = json.loads(a.evidence_json or "{}")
        if not _visible(ev, ctx.as_of):
            continue
        end_ts = a.end_ts
        if end_ts is not None and pd.Timestamp(end_ts) < pd.Timestamp(start):
            continue
        vis.append(a)
    st = _effective_status(db, ctx, [a.id for a in vis])
    eqs, stages = _lookups(db)
    items = []
    for a in vis:
        o = anomaly_out(a, ctx, eqs.get(a.equipment_id), stages.get(a.process_stage_id), st.get(a.id))
        if severity and o["severity"] != severity:
            continue
        if status and o["status"] != status:
            continue
        items.append(o)
    total = len(items)
    items = sorted(items, key=lambda o: (o["start_ts"]), reverse=True)[:limit]
    return {"items": items, "total": total, "score_series": None}


def _lookups(db: Session) -> tuple[dict[int, Equipment], dict[int, str]]:
    eqs = {e.id: e for e in db.execute(select(Equipment)).scalars()}
    stages = {s.id: s.code for s in db.execute(select(ProcessStage)).scalars()}
    return eqs, stages


@data_guard
def get_anomaly(db: Session, ctx: DemoContext, anomaly_id: int) -> dict:
    a = db.get(AnomalyEvent, anomaly_id)
    if a is None or not a.code.startswith("ANM-") or not _visible(json.loads(a.evidence_json or "{}"), ctx.as_of):
        not_found("anomaly", anomaly_id)
    eqs, stages = _lookups(db)
    st = _effective_status(db, ctx, [a.id])
    return anomaly_out(a, ctx, eqs.get(a.equipment_id), stages.get(a.process_stage_id), st.get(a.id))


@data_guard
def set_status(db: Session, ctx: DemoContext, anomaly_id: int, to_status: str, note: str | None) -> dict:
    from app.services.audit import write_audit  # noqa: PLC0415

    cur = get_anomaly(db, ctx, anomaly_id)
    ch = AnomalyStatusChange(anomaly_event_id=anomaly_id, session_id=ctx.session_id, from_status=cur["status"], to_status=to_status,
                             actor_role=ctx.role.value, note=note)
    db.add(ch)
    write_audit(db, ctx, "anomaly.status_change", "anomaly_event", anomaly_id, {"status": cur["status"]}, {"status": to_status, "note": note})
    db.commit()
    return get_anomaly(db, ctx, anomaly_id)


@data_guard
def failure_risk(db: Session, ctx: DemoContext, limit: int) -> dict:
    """Relative ranking by the strongest equipment anomaly score visible in the last 7 days (not a probability)."""
    data = list_anomalies(db, ctx, "equipment", 7, limit=500)
    best: dict[int, dict] = {}
    for o in data["items"]:
        if o["equipment"] is None:
            continue
        k = o["equipment"]["id"]
        if k not in best or o["score"] > best[k]["score"]:
            best[k] = o
    ranked = sorted(best.values(), key=lambda o: -o["score"])[:limit]
    items = [{"equipment": o["equipment"], "risk_score": round(100 * o["score"], 1), "rank": i + 1, "drivers": o["evidence"][:3], "horizon_days": None}
             for i, o in enumerate(ranked)]
    return {"items": items,
            "meaning": "Relative ranking (0-100) = strongest equipment anomaly score detected in the last 7 days up to as_of. "
                       "NOT a calibrated failure probability. The rule-based health/risk index is served by the maintenance endpoints.",
            "limitations": ["Synthetic sensor data with prescribed degradation curves", "No failure history to calibrate against",
                            "Equipment without an anomaly in the window is not listed (score 0)"],
            "model": model_info(db, "equipment_anomaly")}


# ---------------------------------------------------------------------------- energy
@data_guard
def energy_forecast(db: Session, ctx: DemoContext, horizon_h: int) -> dict:
    art = artifact("energy_forecast")
    last = _last_complete_hour(ctx.as_of)
    con = _raw(db)
    hist = pd.read_sql_query(
        "SELECT p.ts, p.ffb_processed_t, p.running_minutes, p.throughput_tph, e.electricity_kwh FROM process_hourly p "
        "JOIN energy_consumption e ON e.ts = p.ts AND e.process_stage_id IS NULL WHERE p.ts >= ? AND p.ts <= ? ORDER BY p.ts",
        con, params=(_ts(last - pd.Timedelta(days=7)), _ts(last)))
    hist["ts"] = pd.to_datetime(hist["ts"], utc=True, format="mixed")
    hist = hist.set_index("ts")
    if hist.empty:
        raise ApiError(409, "insufficient_data", "No energy history before as_of", None)
    loc_h = (hist.index + pd.Timedelta(hours=7)).hour
    prof = hist.groupby(loc_h)[["ffb_processed_t", "running_minutes", "throughput_tph"]].mean()
    rows = []
    for h in range(1, horizon_h + 1):
        t = last + pd.Timedelta(hours=h)
        loc = t + pd.Timedelta(hours=7)
        p = prof.loc[loc.hour] if loc.hour in prof.index else prof.mean()
        rows.append({"t": t, "ffb_processed_t": p["ffb_processed_t"], "running_minutes": p["running_minutes"],
                     "throughput_tph": p["throughput_tph"], "hour_local": loc.hour, "weekday_local": loc.weekday()})
    X = pd.DataFrame(rows)
    pred = art["model"].predict(X[art["features"]])
    sig = art["signature"].predict(X[["ffb_processed_t", "running_minutes"]])
    hw = art["half_width"]
    prov_f = provenance("forecast", "energy_forecast", ctx, mv("energy_forecast"))
    act = hist["electricity_kwh"].iloc[-48:]
    return {"target": "electricity_kwh",
            "forecast": {"key": "energy_forecast", "label": "Plant electricity forecast (assumes last-7-day hourly production profile)", "unit": "kWh",
                         "points": [{"t": r["t"].to_pydatetime(), "v": round(float(v), 2), "lower": round(max(0.0, float(v - hw)), 2),
                                     "upper": round(float(v + hw), 2)} for r, v in zip(rows, pred, strict=True)],
                         "interval": "P90 absolute training residual (in-sample, likely optimistic)", "provenance": prov_f},
            "actual": _series("electricity_actual", "Plant electricity (synthetic actual)", "kWh", [(t.to_pydatetime(), v) for t, v in act.items()],
                              provenance("synthetic_actual", "energy_consumption.electricity_kwh", ctx)),
            "baseline": _series("energy_signature", "Baseline: linear energy signature", "kWh",
                                [(r["t"].to_pydatetime(), float(v)) for r, v in zip(rows, sig, strict=True)],
                                provenance("forecast", "energy_signature_linear", ctx)),
            "model": model_info(db, "energy_forecast")}


# ---------------------------------------------------------------------------- logistics
@data_guard
def queue_prediction(db: Session, ctx: DemoContext) -> dict:
    art = artifact("queue_time")
    as_of = pd.Timestamp(ctx.as_of)
    con = _raw(db)
    t = pd.read_sql_query("SELECT id, truck_type, arrival_ts, weigh_in_ts, exit_ts FROM truck_trips WHERE arrival_ts >= ? AND arrival_ts <= ?",
                          con, params=(_ts(as_of - pd.Timedelta(hours=12)), _ts(as_of)))
    for c in ("arrival_ts", "weigh_in_ts", "exit_ts"):
        t[c] = pd.to_datetime(t[c], utc=True, format="mixed")
        t.loc[t[c] > as_of, c] = pd.NaT  # future events are unknown at as_of
    t = t.sort_values("arrival_ts").reset_index(drop=True)
    waiting = t[t["weigh_in_ts"].isna()]
    from app.ml.logistics import CLASSES  # noqa: PLC0415

    # remaining wait for each waiting truck = model prediction for the yard state NOW with (position - 1) trucks ahead
    hour = pd.Timedelta(hours=1)
    loc = as_of + pd.Timedelta(hours=7)
    in_yard = int((t["exit_ts"].isna()).sum())
    arr60 = int((t["arrival_ts"] >= as_of - hour).sum())
    win60 = int(((t["weigh_in_ts"] <= as_of) & (t["weigh_in_ts"] > as_of - hour)).sum())
    rows = [{"trucks_ahead": pos, "trucks_in_yard": in_yard, "arrivals_last_60m": arr60, "weigh_ins_last_60m": win60,
             "hour_local": loc.hour, "weekday_local": loc.weekday(), "truck_class": CLASSES.get(r.truck_type, 1)}
            for pos, r in enumerate(waiting.itertuples())]
    items = []
    if rows:
        X = pd.DataFrame(rows)[art["features"]]
        p, lo, hi = art["model"].predict(X), art["lo"].predict(X), art["hi"].predict(X)
        for i, r in enumerate(waiting.itertuples()):
            items.append({"truck_trip_id": int(r.id), "position": i + 1, "predicted_wait_min": round(max(0.0, float(p[i])), 1),
                          "lower_min": round(max(0.0, float(min(lo[i], p[i]))), 1), "upper_min": round(max(0.0, float(hi[i]), float(p[i])), 1)})
    return {"as_of": ctx.as_of, "trucks_waiting": len(items),
            "predicted_avg_wait_min": round(float(np.mean([i["predicted_wait_min"] for i in items])), 1) if items else None,
            "items": items, "model": model_info(db, "queue_time"), "provenance": provenance("forecast", "queue_time", ctx, mv("queue_time"))}


@data_guard
def arrival_forecast(db: Session, ctx: DemoContext, horizon_h: int) -> dict:
    art = artifact("arrival_forecast")
    last = _last_complete_hour(ctx.as_of)
    con = _raw(db)
    tr = pd.read_sql_query("SELECT arrival_ts FROM truck_trips WHERE arrival_ts >= ? AND arrival_ts < ?", con,
                           params=(_ts(last - pd.Timedelta(days=9)), _ts(last + pd.Timedelta(hours=1))))
    tr["arrival_ts"] = pd.to_datetime(tr["arrival_ts"], utc=True, format="mixed")
    idx = pd.date_range(last - pd.Timedelta(days=9) + pd.Timedelta(hours=1), last + pd.Timedelta(hours=horizon_h), freq="h")
    counts = tr.set_index("arrival_ts").assign(n=1)["n"].resample("h").sum().reindex(idx, fill_value=0).astype(float)
    counts[counts.index > last] = np.nan
    pts = []
    for t in idx[idx > last]:
        c = counts
        loc = t + pd.Timedelta(hours=7)
        lags = {"hour_local": loc.hour, "weekday_local": loc.weekday(), "lag_24h": c.get(t - pd.Timedelta(hours=24)),
                "lag_168h": c.get(t - pd.Timedelta(hours=168)),
                "mean_24h_lag24": c[(c.index > t - pd.Timedelta(hours=48)) & (c.index <= t - pd.Timedelta(hours=24))].mean(),
                "same_hour_mean_7d_lag24": np.mean([c.get(t - pd.Timedelta(hours=24 * k)) for k in range(1, 8)])}
        v = float(art["model"].predict(pd.DataFrame([lags])[art["features"]])[0])
        counts[t] = v  # recursive beyond 24 h
        pts.append({"t": t.to_pydatetime(), "v": round(v, 2), "lower": None, "upper": None})
    prof = art["profile"]
    bl = [(p["t"], prof.get(((pd.Timestamp(p["t"]) + pd.Timedelta(hours=7)).weekday(), (pd.Timestamp(p["t"]) + pd.Timedelta(hours=7)).hour)))
          for p in pts]
    act = counts[(counts.index <= last)].iloc[-48:]
    return {"target": "truck_arrivals_per_hour",
            "forecast": {"key": "arrival_forecast", "label": "Truck arrivals per hour (day-ahead model; recursive beyond 24 h)", "unit": "trucks/h",
                         "points": pts, "interval": None, "provenance": provenance("forecast", "arrival_forecast", ctx, mv("arrival_forecast"))},
            "actual": _series("arrivals_actual", "Truck arrivals (synthetic actual)", "trucks/h", [(t.to_pydatetime(), v) for t, v in act.items()],
                              provenance("synthetic_actual", "truck_trips.arrival_ts", ctx)),
            "baseline": _series("arrivals_profile", "Baseline: hour x weekday mean of the training period", "trucks/h", bl,
                                provenance("forecast", "hour_weekday_profile", ctx)),
            "model": model_info(db, "arrival_forecast")}


@data_guard
def run_model(db: Session, ctx: DemoContext, name: str) -> dict:
    if name not in MODEL_NAMES:
        not_found("model", name)
    if name == "oer_forecast":
        out = oer_forecast(db, ctx, 1)["forecast"]["points"][0]
    elif name == "energy_forecast":
        out = energy_forecast(db, ctx, 1)["forecast"]["points"][0]
    elif name == "queue_time":
        r = queue_prediction(db, ctx)
        out = {"trucks_waiting": r["trucks_waiting"], "predicted_avg_wait_min": r["predicted_avg_wait_min"]}
    elif name == "arrival_forecast":
        out = arrival_forecast(db, ctx, 1)["forecast"]["points"][0]
    else:
        dom = {"production_anomaly": "production", "equipment_anomaly": "equipment", "energy_anomaly": "energy", "logistics_anomaly": "logistics"}[name]
        r = list_anomalies(db, ctx, dom, 1, limit=200)
        out = {"anomalies_visible_last_24h": r["total"], "codes": [o["code"] for o in r["items"][:20]],
               "note": "Detections come from the causal batch pipeline (python -m app.ml.train); only events with detected_at <= as_of are shown."}
    return {"model": model_info(db, name), "ran_at": datetime.now().astimezone(), "outputs": json.loads(json.dumps(out, default=str)),
            "provenance": provenance("forecast", name, ctx, mv(name))}

