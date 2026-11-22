# Known limitations — Digital Mill Lab

> Independent portfolio / concept demo. Not an official system of any company. Status date 2026-11-22.
> Collected from the engineering logs (kept private), the engineering log (kept private), `docs/MODEL_EVALUATION.md`, `docs/ai/COPILOT_EVALUATION.md`
> and the QA runs. Numbers are as measured; where something was not run, it says so.

## 1. Data

* **Synthetic data only.** Every plant, supplier, truck, sensor, price and lab value is generated deterministically by
  `python -m app.seed` (120 days ending 2026-11-20). No internal company data, no real plant, no real market prices.
  Synthetic benchmarks are not factory measurements.
* **Designed episodes are not measured effects.** Six scenario episodes are embedded in one timeline. Some measured effects
  are smaller than designed (e.g. PRESS_VIBRATION_ANOMALY moves plant OER only ~0.2–0.3 pp, inside normal daily noise; the
  congestion day's next-day OER is not lower). The UI, insights and Copilot must quote the measured effects only.
* **The synthetic generator encodes the relationships the analytics then find.** Agreement between modules proves internal
  consistency (see `tests/integration/test_cross_module.py`), not that the methods would work on real plant data.
* Comparison days have no daily OER noise draw (data-engine note); queue outages and manual-ticketing slowdowns are not stored as
  events (the queue simulation has to infer them).

## 2. Machine-learning models (`docs/MODEL_EVALUATION.md`)

| Model | Result vs baseline (test period, out-of-sample) |
|---|---|
| OER forecast (hourly) | **Does not beat** the 24 h rolling mean: MAE 0.268 pp vs 0.237; it is no better than a constant |
| OER at shift / day granularity | **Does not beat** baselines either: shift 0.205 vs 0.146, day 0.219 vs 0.161 |
| OER driver attribution (ML) | **Unreliable**: wrong-signed out of sample. The UI/Copilot show observed driver deviations vs normal ranges instead and say they are associations, not causes |
| Energy forecast | **Does not beat** the energy-signature baseline: MAE 10.90 vs 9.67 kWh/h; energy anomaly test recall 0/1 |
| Truck arrival forecast | **Does not beat** baseline: 2.109 vs 2.101 |
| Queue-time model | Marginal win: 2.72 vs 2.78 min |
| Production anomaly detection | Precision 1.00, **recall 4/7 = 0.57**, 0 false positives/day, median latency 1.96 h |
| Equipment anomaly detection | Precision 1.00, **recall 4/6 = 0.67**; PRS-03 detected 56.5 h before the rule warning |
| Sustained-queue alert | Recall 3/3, precision 0.50, 0.054 false alarms/day |
| CV (FFB image) | Prototype only: upload safety + colour statistics; **no dataset, no accuracy claim** |

* Small test sets (6–7 labelled episodes): the recall figures have wide uncertainty.
* **Trained once (QA-09).** Artifacts were trained on data before 2026-10-15 local. At demo clocks before that date the model output
  is in-sample (the model has seen data later than the clock). Only `/ai/oer/explanation` states this; other ML endpoints only expose `train_window`.
* Risk scores are relative rankings, **not calibrated failure probabilities**. An anomaly is not a proven cause; a logistics flag is not an accusation.
* ML alerts: until 2026-11-22 `/alerts` showed the severity of the whole episode's peak at earlier clocks (QA-16, fixed in the alert API). Equipment-health
  risk sub-scores, recommendation priority, scenario-catalogue counts and the Copilot `open_alerts` tool still use the stored peak severity (open).

## 3. Logistics queue simulation

* The FIFO replay does **not** reproduce the observed congestion: on the congestion day it gives ~5.7–7.3 min wait-to-weigh vs
  ~29.6–37.4 min observed (turnaround ~37–75 vs 67–129 min, depending on window). The slot policy result is therefore a comparison
  between two simulated policies, not a prediction of real savings. Calibration of a per-window service-time multiplier is open
  (orchestrator item 4). The response states the gap.

## 4. Copilot (`docs/ai/COPILOT_EVALUATION.md`)

* Deterministic tool router (default, no LLM). On 46 fresh held-out paraphrases written before the last changes: **25 correct (54 %),
  16 clarifying questions (35 %), 5 wrong (11 %)** — 83 % correct when it answers. Intent accuracy on its own labelled set is inflated
  (70.8 % of those questions are router exemplars).
* Grounding/safety evaluation passed on its own sets (grounded 45/45, no-data refusals 12/12, unauthorized 23/23, injections 26/26,
  citations 9/10); these are self-written test sets, not an external benchmark.
* **LLM mode never run against a real provider** (fake provider + mocked HTTP only).
* No work-order drafting tool (deliberate: the Copilot never writes business records).
* Known bug reported by the web verifier: within one conversation a follow-up question can be answered with the previous intent's answer (context carry-over).
* The expected-OER band shown is the measured 28-day ±2 s.d. band, not the ML day-level band.

## 5. Language and content

* **API narrative text is English-only** (executive insights, alert titles/messages, anomaly text, Copilot data answers in some paths) even when the UI is Thai.
* **Thai UI copy has not been reviewed by a native speaker**; the Thai recruitment email assumes a pronoun the owner must confirm.
* Some API gaps for the UI: `AnomalyOut` has no provenance block; ML alerts in `/alerts` carry no evidence list; the alert priority method is documented in code, not in the response.
* `/maintenance/downtime.total_downtime_h` is the sum of maintenance-event durations (66.8 h over 30 days at the PRESS focus), not plant downtime
  (40.25 h, the Executive KPI); the field name does not say so (provenance and series label do) — QA-18.

## 6. Integrations, deployment, operations

* **No real integrations.** No SCADA/DCS/historian, ERP, weighbridge, LIMS or SSO connection. Integration contracts in
  `docs/architecture/INTEGRATION_CONTRACTS.md` are future designs.
* **Deployment is on free tiers; a rate-limit fix is not yet verified there.** The web app runs on Vercel and the API on Render's free plan (https://digital-mill-lab-web.vercel.app, deployed 2026-11-23).
  The free API has 0.1 CPU and sleeps when idle: single requests measured 0.4 s to 5.4 s and one page fires 6 to 13 of them, so pages load slowly, and the first request after idle can take a minute or more.
  After the first deployment the demo pages got HTTP 429: the old limiter defaults were too small for the one address that all visitors share behind the web proxy (measured cause: docs/DEPLOYMENT.md section 11).
  The defaults were raised and tests added; the running instance must be redeployed with the new image before the fix shows, and it has not been re-checked yet. The browser tests have not been run against the public URL.
  The Docker images were built and smoke-tested on GitHub Actions (2026-11-22); the docker-compose file itself was never run; PostgreSQL support is only checked as offline DDL.
* **Single-process performance.** Heavy analytics endpoints (overview, KPIs, twin, equipment list, recommendations) take 75–210 ms alone but
  drop to 0.4–0.7 requests/s at 10 concurrent requests in one process (p50 15–23 s), measured on a shared, heavily loaded machine (QA-22,
  numbers in `docs/DEPLOYMENT.md` §8). Until QA-19 (2026-11-22) more than 15 concurrent requests produced HTTP 500 after a 30 s pool wait.
  Not load-tested on a dedicated host.
* Rate limiting is in-memory (single process); session-based limits are easy to evade by rotating session ids; per-IP limits need the
  correct `TRUSTED_PROXY_HOPS` behind proxies.
* Roles are simulated viewpoints, not authentication (`docs/SECURITY.md` §2).
* A public read (`GET /maintenance/recommendations`) lazily writes rule-generated catalog rows to a shared table (bounded, idempotent).
* Audit chain: truncation of the newest rows or a full rewrite is not detectable; above 20,000 audit rows the endpoint verifies incrementally.

## 7. Process

* Built by AI agents under human direction (disclosed in the portfolio docs). All tests and evaluations were written by the same
  agent team; there was no independent human code review or penetration test at this date.
