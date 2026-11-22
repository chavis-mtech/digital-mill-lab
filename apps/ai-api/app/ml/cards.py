"""Model-card content (SPEC section 9 fields) - single source for the API (/ai/models) and docs/ai/model-cards/*.md.

Measured numbers are NOT written here: they are read from data/models/<name>/<version>/metrics.json at render time.
"""

from __future__ import annotations

COMMON_ASSUMPTIONS = [
    "Synthetic Demonstration Data from a fictional mill ('Demo Palm Mill A'); 120 days, one line; no company data.",
    "We generated the data ourselves, so the generator's drivers are fully observable; real plants have unmeasured drivers, "
    "sensor drift and labelling gaps - expect worse results on real data.",
    "Temporal split: train < 2026-10-15 00:00 Asia/Bangkok, test >= it. injected_events (ground truth) are used only for evaluation "
    "and for tuning thresholds on the training period.",
]

CARDS: dict[str, dict] = {
    "oer_forecast": {
        "purpose": "AI-B01: expected hourly OER from FFB quality and process conditions, with a 90% interval and a naive baseline; "
                   "multi-hour forecasts hold the latest conditions constant.",
        "training_data": "process_hourly running hours (>= 30 min, FFB processed > 0) + 12 h delivery quality + press vibration/current "
                         "(hourly means); train 2026-07-24..10-14 local.",
        "assumptions": ["Hourly OER = deterministic loss model + hourly and daily noise in the generator (DATA_GENERATION.md section 4)."],
        "evaluation": "3 expanding-window folds inside the training period select the served candidate; every candidate is then scored once "
                      "on the test period vs persistence, seasonal-naive 24 h and 24 h rolling-mean baselines (MAE/RMSE). Split-conformal "
                      "90% interval (calibrated on the last 14 train days) with measured test coverage; permutation importance; driver-group "
                      "ablation; walk-forward per-scenario error.",
        "limitations": ["Does not beat the 24 h rolling-mean baseline on the test period (see metrics) - hourly OER is noise-dominated.",
                        "Shift (8 h) and day granularity were also evaluated: neither beats its best naive baseline (see granularity table). "
                        "The useful output is the day-level nowcast residual (actual - expected) as a flag, not the forecast.",
                        "Out-of-sample driver attribution of OER_DEGRADATION was unreliable (wrong signs for ripe %, clarifier temperature, "
                        "sterilizer cycle: these drivers barely varied before the episode); the in-sample view attributes it plausibly.",
                        "Trees cannot extrapolate to driver values never seen in training (e.g. the 66-min sterilizer cycle).",
                        "Multi-hour forecast = persistence of conditions; the interval does not widen with horizon.",
                        "day_of_year in the test period lies beyond the training range; trees treat it as the last seen value, and local "
                        "explanations can show a large seasonality contribution that is an extrapolation artefact."],
        "failure_modes": ["Large multi-day OER shifts are absorbed by the lagged-level feature with ~1 day delay.",
                          "Stopped / partially running hours are excluded; start-up hours are noisy."],
        "status": "implemented",
    },
    "production_anomaly": {
        "purpose": "AI-B02: flag hours where the plant process state is unusual (OER below expected, steam pressure, processing rate, "
                   "sterilizer cycle, temperatures, oil loss, kWh/t, unplanned downtime) with evidence and possible factors.",
        "training_data": "Hourly process signals; baselines are expanding median/MAD of each signal's own history (data older than 2 days).",
        "assumptions": ["The Sunday 05:00-13:00 planned stop is plant schedule knowledge and is not treated as downtime."],
        "evaluation": "Event-level precision (detections overlapping any injected label), recall over production/quality labels + the "
                      "STEAM driver, false positives per day, detection latency (detected_at - label start), per scenario; threshold tuned "
                      "on the training period only; IsolationForest and an OER-residual-only rule as comparators.",
        "limitations": ["Short (< 1 h) breakdowns are missed by the 2-consecutive-hour rule.",
                        "PRESS_VIBRATION_ANOMALY moves plant OER only ~0.3 pp - production signals do not see it; equipment detection does.",
                        "Small number of test labels (7): metrics have wide uncertainty."],
        "failure_modes": ["Signals with very stable history (MAD floor) can over-react to small genuine changes.",
                          "A long anomaly older than 2 days slowly enters the expanding baseline only if it lasts weeks."],
        "status": "implemented",
    },
    "equipment_anomaly": {
        "purpose": "AI-C02: time-series anomaly scores per equipment with contributing sensors (vibration, bearing temperature, current, "
                   "pressure, flow, load) + sensor-health checks; the score feeds the rule-based risk index (backend-b). Not a failure probability.",
        "training_data": "Hourly means of 80+ sensors on steady-running hours (current above 25% of normal max this hour and the previous one).",
        "assumptions": ["Degradation shapes in the generator are prescribed curves (power laws): lead times say nothing about real bearings."],
        "evaluation": "Event-level metrics vs injected equipment labels (same equipment, 12 h tolerance); PRS-03 lead time vs the seeded "
                      "warning and critical threshold alarms; rule alarms and a per-equipment IsolationForest as comparators.",
        "limitations": ["A stopped machine (breakdown) is not an anomaly in its sensors - breakdowns are visible from state/downtime, not here.",
                        "A 30-min sensor spike is smoothed away by the 3 h mean (missed in test).",
                        "Low current is ignored (unloaded/idle running is an energy question)."],
        "failure_modes": ["Process-driven changes (e.g. low steam) show up on several machines at once.",
                          "Very slow drifts over months would enter the expanding baseline."],
        "status": "implemented",
    },
    "energy_forecast": {
        "purpose": "AI-E01: hourly plant electricity forecast conditional on planned processed FFB and running time.",
        "training_data": "energy_consumption plant meter (process_stage_id NULL) joined with process_hourly.",
        "assumptions": ["In production the hourly production plan would be an input; the API uses the last 7 days' hour-of-day profile."],
        "evaluation": "Test MAE/RMSE (hourly and daily totals) vs a linear energy signature (kWh = a + b*FFB + c*running minutes) and "
                      "seasonal-naive 24 h.",
        "limitations": ["Does not beat the linear energy-signature baseline on the test period (see metrics).",
                        "Interval is the in-sample P90 residual (optimistic), not conformal."],
        "failure_modes": ["Idle running and leaks are not in the features by design (they are what the anomaly detector looks for)."],
        "status": "implemented",
    },
    "energy_anomaly": {
        "purpose": "AI-E02: energy use above the production-adjusted expectation (walk-forward model) with idle-running evidence.",
        "training_data": "Walk-forward expected kWh (weekly refits on past data) and robust z of the residual.",
        "assumptions": ["ENERGY_EFFICIENCY_DROP lies in the training period; the test period has one energy label (an idle-running night)."],
        "evaluation": "Event-level metrics vs injected energy labels; comparator = the plant's daily 18.5 kWh/t rule.",
        "limitations": ["Missed the only test-period energy label (idle-running night) - see metrics.",
                        "One event covered the whole energy episode in training; per-driver separation is not possible from one meter."],
        "failure_modes": ["Walk-forward refits that include an earlier inefficiency week raise the expectation slightly."],
        "status": "implemented",
    },
    "queue_time": {
        "purpose": "AI-D01: predicted arrival-to-weigh-in wait for trucks in the queue (with P10-P90 band).",
        "training_data": "truck_trips (yard state at arrival computed from earlier events only).",
        "assumptions": ["Queue model in the generator is interval booking, FIFO-ish, with known outages."],
        "evaluation": "Test MAE/RMSE vs a queue-drain baseline (gate time + trucks ahead / recent weigh-in rate) and vs the training median; "
                      "separate MAE in the congestion window; P10-P90 coverage.",
        "limitations": ["Gain over the drain-time baseline is marginal (see metrics).", "No appointment system or driver behaviour."],
        "failure_modes": ["Sudden outages are only seen through the falling weigh-in rate."],
        "status": "implemented",
    },
    "arrival_forecast": {
        "purpose": "AI-D02: day-ahead hourly truck-arrival forecast.",
        "training_data": "Hourly arrival counts; lags >= 24 h only.",
        "assumptions": ["Arrival profile in the generator: hourly profile x season x weekday x rain, convoys of 1-3 trucks."],
        "evaluation": "Test MAE/RMSE vs the hour x weekday profile of the training period and seasonal-naive 24 h.",
        "limitations": ["Does not beat the hour x weekday profile baseline (see metrics).", "No weather input (rain shifts arrivals)."],
        "failure_modes": ["Surges (e.g. after rain) are not anticipated."],
        "status": "implemented",
    },
    "logistics_anomaly": {
        "purpose": "AI-D04: 'unusual, needs review' flags for implausible net weights and excessive waits. Never an accusation.",
        "training_data": "Weighbridge tickets per truck class; arrival-to-weigh-in waits.",
        "assumptions": ["Injected weight outliers are 8-13% above the class maximum payload."],
        "evaluation": "Weight flags vs injected implausible-weight labels (all in the training period); wait flags vs the queue-episode labels.",
        "limitations": ["Test-period weight recall is undefined (no test labels); only false flags are measured.",
                        "Per-truck wait flags (> training P99) are review items only and raise no alerts; alerts come from the sustained "
                        "queue rule (>= k trucks past P99 within 3 h), whose k was set by a false-alarm budget because the training "
                        "period has no queue-episode label."],
        "failure_modes": ["A truck-class mistake on the ticket produces a weight flag (which is exactly what review should catch)."],
        "status": "implemented",
    },
}
