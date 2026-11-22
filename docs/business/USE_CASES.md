# Industrial Use Cases: Value, Feasibility and Priority

> Tasks DML-004 and DML-007. Owner: researcher. Independent concept demo for a fictional palm oil mill; no internal company data. Tone: opportunities to build on. Parameters and sources: `docs/business/DOMAIN_PARAMETERS.json`, `docs/business/ASSUMPTION_REGISTER.md`.

## 1. How the use cases were found and ranked

Each feature must answer at least one of: what cost it cuts, what efficiency it adds, what risk it lowers, what duplicate work it removes, what planning accuracy it adds, how it improves executive decisions, what evidence supports it, what a real plant would need (SPEC section 1). The use cases below come from the SPEC modules and the process map in `PALM_MILL_PROCESS.md`.

**Rubric (scores 1-5, assigned by the researcher; qualitative judgement, not measured):**

| Score | Value (V): size of the lever | Feasibility in the demo (F) | Real-plant data readiness (R) |
|---|---|---|---|
| 5 | Moves OER, throughput or a major cost line; decision-grade for executives | All data can be generated consistently; model/logic verifiable; low risk of fake accuracy | Data usually exists in plant systems and is clean |
| 4 | Clear measurable saving or risk reduction in one area | Feasible with moderate modelling; verification possible | Exists but needs integration/cleaning |
| 3 | Useful, secondary, or benefit is indirect | Feasible only in simplified form | Partly available or manual |
| 2 | Narrow or uncertain benefit | Mostly illustrative | Rarely available |
| 1 | Speculative | Needs data or assets we do not have | Does not exist yet |

**Rank score = V x F** (what is worth building *in this demo*). R is shown separately so that nobody mistakes demo feasibility for a production commitment: a high F with low R means "we can demonstrate the idea honestly, but a pilot needs new data collection".

**Priority** (P0/P1/P2) is fixed by `docs/SPEC.md` section 2; the ranking decides build order *within* a priority.

## 2. Value levers, with evidence (sourced where possible)

| Lever | Why it matters | Evidence | Confidence |
|---|---|---|---|
| OER | 0.5 pp of OER on 1,000 t FFB is 5 t CPO (SPEC example); on the demo's 936 t/day it is 4.7 t CPO/day, about 187,000 THB/day at an illustrative 40,000 THB/t (about 56 M THB/yr at 300 days). Illustrative only. | Arithmetic on parameters; national OER spread 15.85-18.21% over 2012-2021 (S14) | med |
| Oil loss | Residual oil losses are about 1.0% of FFB (0.6-1.6%); a vendor claims a 0.3 pp OER gain equals 3.6 t CPO/day at 60 t/h (not independent evidence) | S17 (peer reviewed, fibre 0.25-0.55%), S37 (vendor) | low-med |
| Unplanned downtime | A mill that stops loses throughput or defers FFB, which then waits and degrades; a Thai mill group reports rerouting FFB to sister mills during maintenance stops | S18 | low-med |
| FFB waiting time | Each hour beyond a free window adds FFA in the lab literature; long peak-season queues are a documented Thai issue | S14, S22 (weak) | low |
| Energy | Thai mills are self-sufficient on biomass; steam and power intensity are tunable; surplus biomass and biogas are options | S15, S26 | med |
| Seasonality | Supply swings (Feb trough vs Sep peak at a Surat Thani site) make planning and staffing a forecasting problem | S20, S21 | med |
| Thin spreads | At 2026 quotes oil revenue about equals FFB cost, so small efficiency gains matter relatively more | S13, S31 | med |

## 3. Use-case catalogue and ranking

`P` = SPEC priority. `Demo route` = SPEC section 6 route. `AI ref` = SPEC module AI-ids.

| ID | Use case | Opportunity (framed positively) | P | AI ref | Demo route | V | F | R | Rank score |
|---|---|---|---|---|---|---|---|---|---|
| UC-01 | Executive control tower: KPIs, current vs previous, trends, drill-down, alerts, AI insight summary, bottlenecks | One trusted view that answers what is abnormal, what it costs, who checks first, what to decide | P0 | - | `/demo/executive` | 5 | 5 | 4 | 25 |
| UC-07 | Scenario simulator: change FFB intake, OER, availability, hours, energy cost, loss, CPO price; formulas shown | Test decisions on adjustable assumptions before committing | P0 | AI-B03 | `/demo/scenarios` | 5 | 5 | 4 | 25 |
| UC-08 | Traceable business impact / ROI simulator (Baseline, Conservative, Expected, Optimistic; no double counting) | Turn operational improvement into a transparent value case | P0 | - | `/demo/business-impact` | 5 | 5 | 4 | 25 |
| UC-02 | OER forecast with explanation, uncertainty and naive baseline | Plan output and spot drift earlier | P0 | AI-B01 | `/demo/palm-mill/ai-insights` | 5 | 4 | 3 | 20 |
| UC-03 | Production anomaly detection (OER low vs expected, steam deviation, rate drop, energy rise, abnormal loss) with contributing factors | Shorten the time from deviation to investigation | P0 | AI-B02 | `/demo/palm-mill/ai-insights` | 5 | 4 | 3 | 20 |
| UC-04 | Predictive maintenance: health states, anomaly detection, failure-risk score (uncalibrated), recommendations | Inspect the right machine first, before a stop | P0 | AI-C01..C04 | `/demo/maintenance/equipment` | 5 | 4 | 2 | 20 |
| UC-06 | Industrial AI copilot: TH/EN questions, safe tools over data, RAG over sample docs, no-API mode, evidence cited | Faster answers and daily/exec briefs with sources | P0 | Module F | `/demo/ai-copilot` | 5 | 4 | 3 | 20 |
| UC-17 | AI recommendations with human approval queue | Keep experts in control while saving triage time | P1 | AI-C04, AI-C05 | `/demo/maintenance/work-orders` | 4 | 5 | 4 | 20 |
| UC-05 | Maintenance work-order workflow with audit trail (alert -> review -> work order -> technician -> record -> resolved) | One traceable maintenance loop; less duplicate paperwork | P1 (needed for tour step 5 and scenario B) | AI-C05 | `/demo/maintenance/work-orders` | 4 | 5 | 4 | 20 |
| UC-18 | Digital twin lite: clickable process flow driven by the same simulated state | Shared mental model of the process across roles | P1 (needed for scenario A consistency) | - | `/demo/palm-mill/process` | 4 | 4 | 2 | 16 |
| UC-19 | CPO quality (FFA) early warning from wait-to-process time and lab results | Protect oil quality at the source | P1 | within AI-B | `/demo/palm-mill` | 4 | 4 | 3 | 16 |
| UC-09 | Weighbridge/queue dashboard and queue-time prediction | Shorter truck waits, steadier feed | P1 | AI-D01 | `/demo/logistics` | 4 | 4 | 3 | 16 |
| UC-13 | Energy and resource intensity with forecast | Lower energy per tonne; plan fuel and power | P1 | AI-E01 | `/demo/energy` | 4 | 4 | 3 | 16 |
| UC-14 | Energy anomaly detection (high vs production volume) | Catch steam leaks and idle running early | P1 | AI-E02 | `/demo/energy` | 4 | 4 | 3 | 16 |
| UC-16 | FFB supplier and traceability: supplier -> delivery -> batch -> processing batch -> CPO lot; mass-balance vs lot-based stated | Better supplier feedback; audit-ready records | P1 | - | `/demo/traceability` | 4 | 4 | 3 | 16 |
| UC-11 | Queue optimisation: FIFO vs constraint-aware slots (simulated) | Smooth peak-season arrivals | P1 | AI-D03 | `/demo/logistics` | 4 | 3 | 2 | 12 |
| UC-10 | Arrival-pattern forecast | Plan staffing and unloading bays | P1 | AI-D02 | `/demo/logistics` | 3 | 4 | 3 | 12 |
| UC-12 | Logistics anomaly flags (implausible net weight, excessive dwell) - never accusations | Data-quality review of tickets and flows | P1 | AI-D04 | `/demo/logistics` | 3 | 4 | 3 | 12 |
| UC-15 | Energy what-if (efficiency, idle run, energy mix, by-product value, biogas/biomass) | Explore energy projects with stated limits | P1 | AI-E03 | `/demo/energy` | 3 | 3 | 2 | 9 |
| UC-20 | Sustainability data model and RSPO-style audit sketch | Make future audits easier; no certification claim | P1 (sketch) | - | `/demo/traceability` | 3 | 3 | 3 | 9 |
| UC-22 | Smart plantation yield forecast (weather and soil-moisture lags) | Plan supply months ahead; published precedent exists (S21) | P2 | - | concept page | 4 | 2 | 2 | 8 |
| UC-24 | Port and terminal scheduling | Berth/yard utilisation | P2 | - | concept page | 3 | 2 | 1 | 6 |
| UC-23 | Petroleum depot inventory concept | Inventory visibility (generic; no company data, no modelling of real depots) | P2 | - | concept page | 3 | 2 | 1 | 6 |
| UC-25 | Cross-company data platform | Shared master data and KPIs across divisions | P2 | - | roadmap page | 5 | 1 | 1 | 5 |
| UC-21 | Computer vision FFB grading (research prototype, human review) | Objective, consistent grading at reception | P2 | Module G | concept page | 4 | 1 | 1 | 4 |

**Reading the ranking.** The three simulator/cockpit use cases (UC-01, UC-07, UC-08) rank highest because they are fully computable from the synthetic data and carry no fake-accuracy risk. The AI use cases (UC-02..UC-04, UC-06) rank a notch lower because their honest evaluation needs care (temporal splits, baselines, uncertainty) and their real-plant readiness is lower. P2 concepts stay below the line by design.

## 4. Per-use-case notes for builders

### P0 flagship

**UC-01 Executive control tower.** Real-plant needs: reliable KPI definitions and data lineage (KPI_DEFINITIONS.md). Demo evidence: every number carries provenance; drill-down to the underlying records. Success: a non-technical executive gets value in 3-5 minutes (guided tour).

**UC-02 OER forecast.** Method: gradient boosting on FFB quality, wait-to-process, season, temperature, steam pressure, equipment efficiency; temporal split; compare with naive baselines (yesterday, 7-day mean); show MAE/RMSE, uncertainty band, feature importance. Honest limit: the data is synthetic and generated from known relations, so the model is expected to recover them; report as a synthetic benchmark. Real plant needs: clean tank dips, lab results, 12+ months of history.

**UC-03 Production anomaly detection.** Method: statistical baseline or Isolation Forest with explanation by contributing tags (never a proven cause). Evaluation: scenario-based precision/recall/false-positive rate and detection latency using the labelled scenario seeds. Real plant needs: event labels from operators to tune thresholds.

**UC-04 Predictive maintenance.** Health states from explicit criteria (ISO 10816-3 zones, trends, temperature, current); anomaly score with contributing sensors; failure-risk score documented as an ordering, not a probability. Real plant needs: sensor history and failure/work-order history to calibrate; many mills lack continuous vibration monitoring on all assets (unknown for P.C.).

**UC-06 Copilot.** Pipeline: question -> intent -> safe tool -> authorised data query -> analytics -> evidence retrieval -> answer with citations. Two runtime modes (LLM adapter; deterministic no-API mode). Safety: read-only, role-checked tools, prompt-injection protection, refuses unsupported questions. Real plant needs: governed data access, document inventory, human review.

**UC-07 Scenario simulator.** All inputs adjustable; formulas visible; calculation example "1,000 t FFB x +0.5 pp OER = +5 t CPO" is labelled as a calculation example; `what_if` provenance.

**UC-08 Business impact.** Inputs per SPEC; outputs include payback and sensitivity; OER uplift and downtime recovery computed on **separate FFB bases**; disclaimer text exactly as in SPEC rule 5. No invented company figures.

### P1 supporting

**UC-05/UC-17 Work orders and approvals.** Human confirmation before any record change; audit entry for every change; mutable data scoped to the demo session. Real plant needs: CMMS integration, technician master data.

**UC-09..UC-12 Logistics.** The weighbridge is rarely the true bottleneck: unloading and sterilizer feed are. Queue simulations must use the capacity relations in `DOMAIN_PARAMETERS.json` (REL-05, REL-14). Optimisation compares FIFO with a constraint-aware slot policy in simulation; state assumptions. Anomaly flags are for data review, not misconduct.

**UC-13..UC-15 Energy.** Normalise intensity for load before flagging; biomass balance (REL-10) limits how much steam intensity can rise before fuel runs short; biogas is a what-if project.

**UC-16/UC-20 Traceability.** Multi-supplier mixing means mass-balance tracking is the default; lot-based tracking applies only where lots are physically kept apart. Never claim certification.

**UC-18/UC-19 Digital twin and FFA warning.** The twin must show the *same* values as sensor trends, KPIs, alerts and copilot context in the "Press Performance Degradation" scenario.

### P2 concepts (label "prototype", never "production")

**UC-21 CV grading.** A real model only if a licensed, labelled dataset exists. Otherwise ship a research prototype: dataset requirements, camera position, lighting, labelling protocol, class definitions (unripe, ripe, overripe, rotten, with loose-fruit counts as in S40), evaluation plan, pilot validation. No accuracy claim.

**UC-22 Plantation forecasting.** Precedent: province-level monthly yield models with R2 0.33-0.73 and 3-20 month lead (S21); a demo would need the operator's own estate records.

**UC-23..UC-25.** Concepts only. UC-23 and UC-24 use no company data; UC-23 does not model real depot stock.

## 5. What a real plant would need before any use case moves beyond the demo

1. A data inventory: sensors, historian/SCADA, weighbridge, LIMS, CMMS, ERP, with ownership and quality.
2. 90 days to 12 months of historical data under agreement, including failure and maintenance history.
3. Agreed KPI definitions (especially OER and the stock-change treatment).
4. A pilot scope (one line or one workflow), baseline measurement, success criteria and a validation plan.
5. IT/OT security review; read-only access first; no control of machines.
6. User involvement from operations, maintenance, logistics and IT from day one.

## 6. Not planned (and why)

| Item | Reason |
|---|---|
| Autonomous control of machines or setpoints | Violates rule 4 (AI never controls machines) |
| Anything using real company data or branding | Violates rule 1 |
| Claims of certification, accuracy on real plants, or integration | Violates rules 3, 6, 11 |
| Modelling real petroleum depot stock or fuel logistics | No data available |
| Deep learning without justification | ADR-009; small tabular data, sklearn baselines suffice |
