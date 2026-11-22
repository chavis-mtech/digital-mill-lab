# Model Evaluation — measured results (synthetic benchmark)

> Owner: ml. Every number below was produced by `python -m app.ml.train` / `python -m app.ml.evaluate` on the seeded
> 120-day synthetic dataset (seed 20261120) and is stored in `data/models/<model>/1.0.0/metrics.json`
> (full JSON incl. CV folds, tuning grids and per-label tables: `data/models/EVALUATION.md`).
> **These are synthetic benchmarks of a fictional mill, not real-plant measurements.** We generated the data
> ourselves, so the drivers are fully observable; a real plant will be harder.

## 1. Protocol

| Item | Rule |
|---|---|
| Temporal split | train < 2026-10-15 00:00 Asia/Bangkok (2026-10-14 17:00 UTC), test >= it. Test period = 37 days |
| Model selection | inside the training period only (3 expanding-window folds of 14 days for OER; threshold grids for detectors) |
| Test period | used once per model for the reported numbers; no re-selection after seeing it |
| Forecast metrics | MAE, RMSE vs naive baselines; interval coverage measured on test |
| Anomaly metrics | event level. *Precision* = detections (by `detected_at` in period) overlapping any injected label (6-12 h tolerance) / detections. *Recall* = target labels with an overlapping detection / target labels. *FP/day* = unmatched detections / days. *Latency* = `detected_at` - label start |
| Ground truth | `injected_events` (54 labels), read only by evaluation code (`app/ml/data.load_labels`), never by features or the API |
| Causality | robust baselines are expanding medians/MADs from data older than 2 days; model-based expectations are walk-forward (weekly refits on past data only); `detected_at` = end of the hour the persistence rule fired |
| Re-check | `python -m app.ml.evaluate` reloads the OER artifact and re-scores the test set (`recomputed_test_mae 0.2679 = stored 0.2679`) and re-scores the anomaly rows *as written in the DB* (same numbers as below) |

## 2. Headline

| Model | Model (test) | Best baseline (test) | Beats baseline? |
|---|---|---|---|
| AI-B01 OER (served: `hgb_level_plus_drivers`) | MAE 0.268 pp, RMSE 0.335 | 24 h rolling mean of past OER: MAE 0.237, RMSE 0.295 | **No** |
| AI-B01 at 8 h shift / calendar day (CV-selected `hgb_drivers`) | shift MAE 0.205 pp; day MAE 0.219 pp | shift: previous block 0.146; day: train mean 0.161 | **No** at any granularity |
| AI-B01 day-level nowcast (expected OER given conditions) | residual band +/-0.49 pp, test coverage 0.946 | - | diagnostic only (see 3.1) |
| AI-B02 production anomaly | precision 1.00, recall 4/7, 0 FP/day, median latency 2.0 h | IsolationForest: precision 1.00, recall 1/7, latency 9 h | Yes (vs IF) |
| AI-C02 equipment anomaly | precision 1.00, recall 4/6, 0 FP/day, median latency 16.5 h | Rule threshold alarms: precision 0.67, recall 2/6, 0.05 FP/day, latency 115 h | Yes |
| PRS-03 bearing (PRESS_VIBRATION_ANOMALY) | first ML detection 2026-11-13 06:00 local | rule warning 11-15 14:30, critical 11-19 10:20 local | **56.5 h before the warning, 148.3 h before the critical alarm** (171 h after the injected onset) |
| AI-E01 energy forecast | MAE 10.90 kWh/h, RMSE 16.19 | linear energy signature: MAE 9.67, RMSE 14.16 | **No** |
| AI-E02 energy anomaly | recall 0/1, 0 FP/day | daily 18.5 kWh/t rule: recall 0/1 | **No** (both miss the only test label) |
| AI-D01 queue time | MAE 2.72 min, RMSE 8.45 | queue-drain baseline: MAE 2.78, RMSE 8.98 | Yes, marginally |
| AI-D02 arrival forecast | MAE 2.109 trucks/h | hour x weekday profile: MAE 2.101 | **No** |
| AI-D04 queue ALERTS (>= 3 trucks past P99 wait within 3 h) | recall 3/3, precision 0.50, 0.054 FP/day, median latency 4.0 h; NORMAL_DAY 0 alerts; congestion window 1 alert (11-14 10:00 local) | - | n/a |
| AI-D04 truck-level flags (no alerts) | weight: 0 false flags in test (no test labels); wait episodes: recall 2/3, precision 0.68, 0.24 FP/day | - | n/a |

## 3. AI-B01 OER forecast

Test MAE / RMSE (617 running hours; target SD 0.31 pp):

| Candidate / baseline | CV mean MAE (train folds) | Test MAE | Test RMSE |
|---|---|---|---|
| hgb_drivers (same-hour conditions only) | 0.343 | 0.279 | 0.353 |
| ridge_drivers | 0.355 | 0.284 | 0.357 |
| random_forest_drivers | 0.341 | 0.258 | 0.326 |
| **hgb_level_plus_drivers (served, lowest CV MAE)** | **0.272** | **0.268** | **0.335** |
| ridge_level_plus_drivers | 0.340 | 0.239 | 0.298 |
| baseline persistence (previous running hour) | 0.314 | 0.289 | 0.360 |
| baseline seasonal-naive 24 h | 0.364 | 0.323 | 0.398 |
| **baseline 24 h rolling mean of past OER** | 0.266 | **0.237** | **0.295** |

* **The served model does not beat the best naive baseline**, neither in CV nor on test. Hourly OER in this generator
  carries hourly and daily noise that no same-hour driver explains; the rolling mean averages it away. The ridge
  level model nearly ties the baseline on test, but choosing it after seeing the test period would be test-set selection, so it is not served.
* Daily view (FFB-weighted daily OER, 37 test days, daily SD 0.193 pp): model 0.168 pp vs previous day 0.183 vs
  trailing 7-day mean 0.163 — again no meaningful gain.
* Intervals (nominal 90 %): split-conformal +/-0.634 pp → **test coverage 0.948** (conservative); quantile HGB P5-P95 → coverage 0.778 (under-covers). Conformal is served.
* Permutation importance (served model, test, MAE increase in pp): lagged OER level 0.0106, throughput change 0.0022,
  ripe-FFB change 0.0020, press current change 0.0019, ripe FFB 0.0018, sterilizer cycle 0.0009. Drivers move the
  prediction very little relative to noise.
* Ablation (drivers-only HGB, test MAE 0.279): removing any single driver group changes MAE by < 0.01 except
  calendar (0.296, i.e. day-of-year seasonality matters); every single group alone gives 0.277-0.290; the lagged level alone (= baseline) gives 0.237.
* Per scenario (walk-forward, weekly refits): OER_DEGRADATION 0.334 vs persistence 0.367 / rolling 0.362 (train side);
  test-side scenarios 0.218-0.268 vs rolling mean 0.212-0.243.

### 3.1 Granularity and the nowcast view (orchestrator follow-up)

Same split, leakage rules and CV-only selection; blocks = FFB-weighted means over running hours (shift = 8 h local blocks
with >= 150 t, day >= 400 t). Baselines use only earlier blocks; "train mean" = constant training-period mean.

| Granularity | Test blocks | CV-selected model | Model test MAE | Best baseline (test) | Baseline MAE | Target SD |
|---|---|---|---|---|---|---|
| hour | 617 | hgb_level_plus_drivers | 0.268 | 24 h rolling mean | 0.237 (train mean 0.264) | 0.312 |
| shift (8 h) | 95 | hgb_drivers | 0.205 | previous block | 0.146 | 0.211 |
| day | 37 | hgb_drivers | 0.219 | train mean | 0.161 (previous day 0.183, 7-day mean 0.163) | 0.193 |

Other candidates on test (reported, not selected): shift ridge_level_plus_drivers 0.181, day ridge_level_plus_drivers 0.190 —
still worse than the baselines. **Verdict: no granularity is useful for forecasting OER on this data.**

Day-level nowcast ("expected OER given current conditions", Ridge on the 12 observable drivers, no lagged OER):
walk-forward residual MAE 0.270 pp (train) / 0.200 pp (test); 90 % split-conformal residual band +/-0.49 pp, test coverage 0.946.
OER_DEGRADATION (2026-10-02, actual 17.71 %): out-of-sample (fitted before that week) expected 18.57 % → residual
**-0.86 pp, outside the band** (the flag works), but the attribution is wrong: unripe intake -0.46 pp is right, while ripe %
(+0.31), low clarifier temperature (+0.18) and the short sterilizer cycle (+0.13) get the wrong sign — those drivers barely
varied before the episode. In-sample (model fitted on the whole training period, which contains the episode): expected 17.67 %,
clarifier temperature -0.48 pp and unripe intake -0.28 pp — plausible, but that is hindsight, not prediction.
Served: `/ai/oer/explanation` returns this nowcast (business day to `as_of`) with residual, band and contributions, and both OER
endpoints carry a `granularity_note` saying which view is useful.

## 4. AI-B02 production anomaly (threshold z = 4.5, >= 2 consecutive hours)

| Detector | Period | Events | Precision | Recall | FP/day | Median latency |
|---|---|---|---|---|---|---|
| Robust z + OER residual (served) | test | 4 | 1.00 | 4/7 = 0.57 | 0.00 | 1.96 h |
| Robust z + OER residual (served) | train (in-sample tuning) | 17 | 1.00 | 14/21 = 0.67 | 0.00 | 2.19 h |
| IsolationForest (walk-forward) | test | 1 | 1.00 | 1/7 | 0.00 | 9.0 h |
| OER-residual-only rule | test | 0 | - | 0/7 | 0.00 | - |

Per label (test): STEAM_PRESSURE_DEVIATION feed-water pump cavitation detected (latency 9.0 h after the pump onset;
the steam-pressure drop itself starts later); breakdowns INJ-BD-002/014/012 detected (1.6-2.3 h); INJ-BD-027, -015, -020
(40-68 min stoppages) missed. PRESS_VIBRATION_ANOMALY is **not** a production target: it moves plant OER ~0.3 pp, so
the OER-residual signal does not see it (equipment detection does).

## 5. AI-C02 equipment anomaly (threshold z = 6.0 on a 3 h mean, >= 3 consecutive hours)

| Detector | Period | Events | Precision | Recall | FP/day | Median latency |
|---|---|---|---|---|---|---|
| Robust z + sensor-health rules (served) | test | 13 | 1.00 | 4/6 | 0.00 | 16.5 h |
| Robust z + sensor-health rules (served) | train (in-sample tuning) | 20 | 1.00 | 4/10 | 0.00 | 77.4 h |
| Per-equipment IsolationForest | test | 25 | 1.00 | 3/6 | 0.00 | 75 h |
| Rule threshold alarms (seeded) | test | 6 | 0.67 | 2/6 | 0.05 | 115 h |

Per label (test): FWP-01 cavitation 5.0 h; CTF-01 rotor imbalance (below alarm limits) 28 h; PRS-03 bearing wear 171 h
after the injected onset; CLR-01 sensor dropout 3.7 h; PRS-02 30-min sensor spike missed (smoothed away); CTF-02 breakdown
missed (a stopped machine has no running-hour data — breakdowns belong to state/downtime monitoring).
In training, all 6 equipment-domain breakdowns are missed for the same reason; PRS-01 bearing wear, DIG-02 lubrication
deficit and both sensor flatlines are detected.

**PRS-03 lead time (measured):** onset label 2026-11-06 03:00 local → first ML detection 2026-11-13 06:00 local →
rule HIGH 11-15 14:30 → rule HIGH-HIGH (critical) 11-19 10:20. Detected before the critical threshold: **yes**, 148.3 h earlier.
Caveat: the generator's degradation is a prescribed power-law curve, so this lead time says nothing about real bearings.

## 6. AI-E01 / AI-E02 energy

| Model | Test MAE (kWh/h) | RMSE | Daily-total MAE (kWh/day, mean 16,704) |
|---|---|---|---|
| HGB (conditional on processed FFB) | 10.90 | 16.19 | 205 |
| Linear energy signature (baseline) | **9.67** | **14.16** | 214 |
| Seasonal-naive 24 h | 159.8 | 316.0 | 2,036 |

Hourly the HGB **loses** to the linear signature; on daily totals it is slightly better (205 vs 214 kWh/day). P90
in-sample residual interval: test coverage 0.91.
Energy anomaly (z = 8.0, >= 4 h): training period (in-sample) — one event covering the ENERGY_EFFICIENCY_DROP week,
recall 4/4 drivers, 0 FP; **test period — 0 events, recall 0/1 (missed the idle-running night 10-16)**, 0 FP. The
daily 18.5 kWh/t rule also misses it. Threshold tie-breaking (highest threshold among equal training F1) explains the miss;
it was not changed after seeing the test result.

## 7. AI-D01 / D02 / D04 logistics

| Model | Test MAE | RMSE | Notes |
|---|---|---|---|
| Queue time HGB | 2.72 min | 8.45 | mean wait 6.3 min; congestion window (419 trucks) 8.96 vs baseline 9.40; P10-P90 coverage 0.74 (nominal 0.80) |
| Queue-drain baseline | 2.78 | 8.98 | gate time + trucks ahead / weigh-in rate of the last hour |
| Training median | 2.77 | - | |
| Arrival forecast HGB (Poisson, day-ahead) | 2.109 trucks/h | 3.04 | mean 4.0 arrivals/h |
| Hour x weekday profile (baseline) | **2.101** | **2.98** | model does not beat it |
| Seasonal-naive 24 h | 2.741 | 4.07 | |

**Alerts vs review flags.** Per-truck wait flags (> training P99 = 13.8 min) stay `anomaly_events` ("unusual, needs review")
and raise **no alerts**. Alerts come only from the sustained-queue rule: >= k trucks pass the P99 wait (counted when they pass it,
causal) within 3 h. The training period has no queue-episode label, so k was set by a false-alarm budget on train
(<= 1 per 30 days → k = 3; train: 2 alerts, both unmatched = 0.024 FP/day). Test: 4 alerts, recall 3/3 (surge 10 h, WB-02 outage
4 h, bay outage 0 h latency), precision 0.50, 0.054 FP/day; NORMAL_DAY 0 alerts; TRUCK_QUEUE_CONGESTION first alert 11-14
10:00 local (the seeded rule "wait > 60 min" fires 11:23). ML alerts fell from 157 to 64.

Logistics flags: weight envelope = training P99.5 per class x 1.05 → train 3/3 injected outliers, 0 false flags; test 0 flags
(no test labels, so recall is undefined). Wait > training P99 (13.8 min), merged into episodes: test 28 episodes, recall 2/3
queue-episode labels, precision 0.68, 0.24 FP/day — useful for review, noisy.

## 8. Leakage audit

| Check | Result |
|---|---|
| Forbidden columns (`oer`, `ker`, `cpo_t`, `kernel_t`, `oil_loss`, `injected`, `scenario`, `label`) in any forecast feature list | none (asserted at import and in `tests/ml/test_leakage.py`); single allowed exception: `oer_level_lag24` = mean of the 24 observed OER values strictly before the hour |
| Oil-loss columns | used only as *anomaly signals* (AI-B02), never as OER features |
| Feature causality | `test_oer_features_do_not_change_when_future_rows_are_removed` (features up to t identical with and without data after t); delivery features use hours t-12..t-1 only; queue features count only events before the arrival |
| Labels | `injected_events` read only by `load_labels` (evaluation); test asserts no feature/service module calls it |
| Scenario windows | `scenario_runs` used only to slice errors and as a playback tag on anomaly rows, never as a detector input |
| Selection | served OER model chosen by CV inside train; thresholds tuned on train; one test evaluation |
| Known optimism | synthetic drivers are observable; comparison days have no daily noise draw (DATA_GENERATION section 9); energy interval is in-sample |

## 9. What is NOT claimed

* No real-plant accuracy, no generalisation to a target organisation mills — synthetic benchmark only.
* No calibrated failure probability: `/ai/failure-risk` is a relative ranking of anomaly scores; the health/risk index is rule-based (backend-b).
* Anomaly outputs list *possible contributing factors*, never proven causes; logistics flags are review requests, never accusations.
* The CV endpoint is a research prototype: no labelled dataset, no grader, no accuracy (section 10).
* Small label counts (7 production, 6 equipment, 1 energy, 3 logistics labels in the test period) → wide uncertainty on every rate.

## 10. CV prototype

No properly licensed labelled FFB image dataset was available; none was used. The endpoint returns deterministic colour
statistics (HSV region fractions, 12x12 dominant-region grid as visual explanation) labelled "not a ripeness grade",
`validated=false`, `requires_human_review=true`, plus the dataset / camera / lighting / labelling / evaluation / pilot protocol.
