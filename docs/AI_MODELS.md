# AI Models — inventory and status

> Owner: ml. Classical ML (scikit-learn) + robust statistics on **Synthetic Demonstration Data** (ADR-009). Measured
> results: `docs/MODEL_EVALUATION.md`. Model cards (SPEC section 9 fields, generated with the measured numbers):
> `docs/ai/model-cards/<model>.md` and `GET /api/v1/ai/models`. AI is advisory only; it never controls equipment.

## Commands

```bash
cd apps/ai-api && source .venv/bin/activate
python -m app.ml.train      # make models: train + evaluate on the temporal split, save data/models/*, run the causal
                            # detection pipeline into DATABASE_URL (model_registry, ai_predictions, anomaly_events,
                            # ai_recommendations, ML alerts). --no-write = no DB writes; --db-url URL.
python -m app.ml.evaluate   # make eval: reproducibility check + re-score detections from the DB + regenerate
                            # data/models/EVALUATION.md and docs/ai/model-cards/*.md
```
Runtime on the build machine: train + pipeline ~42 s; evaluate ~1 s. Deterministic (seed 20261120, fixed sklearn seeds).

## Inventory

| Task | Model name | Approach | Baseline | Beats baseline (test) | Endpoint(s) | Status |
|---|---|---|---|---|---|---|
| AI-B01 OER forecast | `oer_forecast` | HGB on lagged OER level + driver changes + drivers (selected by CV among HGB/Ridge/RF variants), split-conformal 90 % interval, permutation importance + local occlusion explanation | persistence, seasonal-naive 24 h, 24 h rolling mean | **No** (0.268 vs 0.237 pp MAE) | `GET /ai/oer/forecast`, `/ai/oer/explanation` (incl. day-level nowcast residual), `/ai/oer/model` | implemented (forecast not useful at hour/shift/day; nowcast residual = diagnostic) |
| AI-B02 production anomaly | `production_anomaly` | expanding robust z on 9 process signals + walk-forward OER residual; >= 2 h persistence | IsolationForest, OER-residual-only rule | Yes vs IF (recall 4/7 vs 1/7, both 0 FP) | `GET /ai/anomalies/production`, `/ai/anomalies/{id}`, `POST /ai/anomalies/{id}/status` | implemented |
| AI-C02 equipment anomaly (+ C03 input) | `equipment_anomaly` | per-sensor expanding robust z on steady-running hours, 3 h mean, >= 3 h persistence; flatline / missing-data rules | rule threshold alarms, per-equipment IsolationForest | Yes (recall 4/6 vs 2/6; PRS-03 148 h before the critical alarm) | `GET /ai/anomalies/equipment`, `/ai/failure-risk` (relative anomaly ranking, not a probability) | implemented |
| AI-E01 energy forecast | `energy_forecast` | HGB conditional on processed FFB / running time | linear energy signature, seasonal-naive | **No** hourly (10.90 vs 9.67 kWh) | `GET /ai/energy/forecast` | implemented |
| AI-E02 energy anomaly | `energy_anomaly` | walk-forward expected kWh, robust z of residual, 6 h mean | daily 18.5 kWh/t rule | **No** (both miss the single test label) | `GET /ai/energy/anomalies` | implemented |
| AI-D01 queue time | `queue_time` | HGB on yard state at arrival + P10/P90 quantile models | queue-drain (gate + trucks ahead / weigh-in rate) | Yes, marginal (2.72 vs 2.78 min) | `GET /ai/logistics/queue-prediction` | implemented |
| AI-D02 arrival forecast | `arrival_forecast` | HGB Poisson, day-ahead lags | hour x weekday profile | **No** (2.109 vs 2.101) | `GET /ai/logistics/arrival-forecast` | implemented |
| AI-D04 logistics flags | `logistics_anomaly` | per-class weight envelope, wait > P99 | - | n/a | `GET /ai/logistics/anomalies` | implemented |
| P2 CV FFB grading | - | research prototype: safe upload + HSV colour statistics, no trained grader | - | no accuracy claimed | `POST /cv/ffb-assessment`, `GET /cv/protocol` | prototype |
| Model cards / runs | all | - | - | - | `GET /ai/models`, `/ai/models/{name}`, `POST /ai/models/{name}/run` (AI Analyst) | implemented |

## Code map (`apps/ai-api/app/ml/`)

| File | Role |
|---|---|
| `common.py` | split timestamp, seed, forbidden-feature audit, artifact/metrics container |
| `data.py` | read-only loaders; `load_labels` (injected_events) is evaluation-only |
| `events.py` | causal expanding robust baselines, walk-forward refits, event extraction, event-level evaluation, train-only threshold tuning |
| `oer.py`, `production.py`, `equipment.py`, `energy.py`, `logistics.py` | models / detectors + evaluation |
| `pipeline.py` | writes model_registry, ai_predictions, anomaly_events (`detected_at` + per-hour trajectory in evidence_json), advisory ai_recommendations, ML alerts; idempotent |
| `service.py` | API inference (artifacts loaded once), as_of-truncated anomaly rendering |
| `cards.py`, `evaluate.py`, `train.py`, `cv.py` | card content, evaluation CLI, training CLI, CV prototype |

## Data written by the pipeline (run on a seeded DB)

`models 8, anomaly_events 163, alerts 64, ai_predictions 18,610`; per-truck wait flags are anomaly_events without alerts (OER walk-forward nowcasts, energy expectations,
per-truck queue predictions, day-ahead arrival forecasts). Alerts use the frozen enum values `production_anomaly`,
`equipment_anomaly`, `energy_anomaly`, `logistics_anomaly` (the schema has no `ml_*` values) with
`evidence_json.rule_type = "ml_anomaly"` and `detector`. Anomaly codes `ANM-*`, alerts `MLA-*`, recommendations `REC-ML-*`
(`advisory = true`, `risk_score = NULL`: the risk index belongs to backend-b).

## as_of semantics

* Forecast features and actuals: hourly rows are used only when complete (`ts + 1 h <= as_of`).
* Anomalies: visible only if `evidence.detected_at <= as_of`; peak, score, severity, evidence and end are recomputed from
  the stored trajectory truncated at `as_of` (an event that continues after `as_of` is shown as ongoing, `end_ts = null`).
* Alerts table rows: `raised_at = detected_at`, `resolved_at = event end`; readers of `alerts` must hide rows with
  `raised_at > as_of` and treat `resolved_at > as_of` as unresolved.

## Limits

Synthetic, single fictional mill, 120 days; few labels per class; degradation curves prescribed by the generator;
multi-hour OER forecast = persistence of conditions; energy forecast conditional on planned production. See each card.
