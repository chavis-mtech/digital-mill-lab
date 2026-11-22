# Product Requirements Document (PRD)

> Task DML-008. Owner: researcher. Derived from `docs/SPEC.md` (what) and the build plan (kept private) (how). If anything here conflicts with SPEC, SPEC wins; this PRD adds testable acceptance criteria and business context from `docs/business/**`. Status of every requirement at the time of writing: **planned** (nothing built yet when this was written; builders must update status chips as they work).

## 1. Purpose and positioning

**Digital Mill Lab - Intelligent Operations & AI Transformation** is an **independent portfolio and concept demo**, not an official system of any company. An applicant uses it to propose long-term software and AI work to a target organisation (Thailand) for the role **Technical Project Manager (Software & AI)** and related roles. It must be a working, testable, deployable application: no decorative buttons, charts or AI panels; every primary feature has a real data flow, implementation, validation and verifiable output.

**Primary focus:** a palm oil mill (workflow from plantation to dispatch, plus kernel recovery, boiler and steam, power, water, POME/biogas/biomass, maintenance, QC) using a **fictional** company and mill and **synthetic** data. Public information about the group is thin and partly dated (the public-facts research (kept private)), so the demo demonstrates capability and method rather than claiming knowledge of the company's operations.

## 2. Goals, outcomes and non-goals

### 2.1 Goals (mapped to the five outcomes in SPEC section 2)
| Outcome | Goal | Evidence the product must provide |
|---|---|---|
| A. Industrial process understanding | Show that the process logic is understood and respected (mass balance, steam/energy, losses) | Process map page; consistent synthetic data; `PALM_MILL_PROCESS.md`; validation report |
| B. Applied AI engineering | Real models with honest evaluation; grounded copilot | Model cards; temporal splits; naive baselines; scenario-based anomaly metrics; copilot evaluation |
| C. Enterprise architecture | Modular, typed, testable platform with future integration contracts | Architecture docs, ADRs, OpenAPI/contracts, CI |
| D. Business value | KPIs, cost, risk, productivity translated into decisions with transparent formulas | KPI definitions, scenario and ROI simulators, business-impact analysis |
| E. Technical leadership | Roadmap, backlog, risks, plan | Roadmap page, TASKS, KNOWN_LIMITATIONS, status reports |

### 2.2 Non-goals
Production deployment at a real plant; control of machines; any use of internal company data, systems, logos or branding; claims of certification, integration or accuracy on real plants; legal/financial advice.

## 3. Users

Seven audiences (detail in `docs/business/PERSONAS.md`): Executive/MD, Factory Manager, Production Manager, Maintenance Engineer, IT Manager, HR/Recruiter, Technical Interviewer. A non-technical executive must get the value in 3-5 minutes; engineers must be able to verify logic. Roles in the demo are **simulated viewpoints** (eight roles: Executive, Factory Manager, Production Engineer, Maintenance Engineer, Logistics Officer, AI Analyst, System Administrator, Public Demo Viewer), selectable with no signup; authorization is enforced server-side and tested.

## 4. Scope by priority

| Priority | Modules | Required state |
|---|---|---|
| **P0 flagship** (fully functional) | Executive Control Tower; Palm Mill Production Intelligence; AI Anomaly Detection / Predictive Maintenance; Industrial AI Copilot; Scenario Simulator; Traceable Business Impact Analysis | `implemented` with real data flow, tests and verifiable output |
| **P1 supporting** (working workflows) | Logistics & Weighbridge; Energy & Resource; FFB Supplier & Traceability; Maintenance Work Orders; AI Recommendations & Human Approval | `implemented` workflows; may be narrower than P0 |
| **P1-adjacent** (needed for acceptance) | Digital Twin Lite (scenario A consistency); Guided Executive Tour; Public landing and portfolio pages | `implemented` |
| **P2 concepts** | Computer Vision FFB grading; Smart Plantation / Yield forecast; Petroleum inventory; Port & terminal scheduling; Cross-company data platform | `prototype` or `planned`, labelled, never "production" |

If time is short: finish the P0 modules so they genuinely work, and record the rest transparently with status chips (`implemented | partial | prototype | planned`).

## 5. Cross-cutting requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-CC-01 | Provenance on every numeric payload: `{kind, source, as_of, model_version}` where kind is synthetic_actual, forecast or what_if; UI renders a badge from it | Contract/schema test rejects a numeric payload without provenance; visual check of badge on each KPI card |
| FR-CC-02 | "Synthetic Data" badge visible on every `/demo/*` page; "Simulated Live" mode explicitly says simulation | E2E assertion on each demo route |
| FR-CC-03 | Playback: Today, Last 7 Days, Last 30 Days, Scenario Date, Simulated Live; client sends `as_of` / `scenario_id`; server is stateless about the clock | Same request returns same result; switching scenario changes all dependent modules consistently |
| FR-CC-04 | Honest status: anything unfinished carries a status chip; no silent stubs | Static check that unfinished routes expose a chip; KNOWN_LIMITATIONS matches reality |
| FR-CC-05 | i18n: Thai default, English toggle (cookie-based, no route prefix), typed dictionaries | Toggle persists; missing-key test passes |
| FR-CC-06 | Loading, error and empty states everywhere | Component/e2e tests for each state on key pages |
| FR-CC-07 | Light and dark themes; responsive: tablet/desktop first, mobile gives an overview | Visual checks at 375, 768, 1280 px; contrast checks |
| FR-CC-08 | Disclaimers: ROI text (SPEC rule 5); "independent concept, not an official system of any company" on public pages and in the footer of reports | Text present and tested |
| FR-CC-09 | Mutable records (work orders, approvals, audit, copilot sessions) scoped per `X-Demo-Session`; seeded rows form a shared read-only baseline; `POST /demo/session/reset` | Two sessions cannot see each other's changes; reset restores baseline |

## 6. Functional requirements by module

### 6.1 Public site, tour and portfolio (P1-adjacent; epics E03, E13)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-PUB-01 | Landing (TH default, EN toggle) with headline "Intelligent Operations for a Smarter Industrial Future" and the SPEC subtitle; sections Project Overview, Business Challenges, AI Solutions, Explore Live Demo, Technical Architecture, Implementation Roadmap, About the Developer, Contact/Resume | All sections present; routes `/`, `/about-project`, `/business-opportunities`, `/technical-architecture`, `/implementation-roadmap`, `/developer`, `/contact` respond |
| FR-PUB-02 | "Business Challenges" framed as opportunities to build on; no claim that the company has problems or missing systems without evidence | Copy review against PUBLIC_FACTS rules |
| FR-PUB-03 | Developer page uses only facts from the applicant's own README; everything else is a clearly marked placeholder plus a TODO list | Review: no invented facts |
| FR-TOUR-01 | Guided Executive Tour ("ทดลองชมระบบใน 5 นาที") with seven skippable/backable steps: efficiency drop detected -> AI analyses related data -> abnormal equipment signal -> AI proposes inspection -> manager creates work order -> system simulates production impact -> executive dashboard shows status and potential benefit | E2E walks all steps; values identical across steps; skip/back works; ends in dashboard |
| FR-TOUR-02 | Tour data is consistent with the demo data of the selected scenario (same OER delta, same equipment, same work order) | Cross-step assertion test |

### 6.2 Executive Industrial Control Tower (P0; epic E05)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-EXEC-01 | KPI cards: FFB Received, FFB Processed, CPO Produced, OER, KER, Throughput, Equipment Availability, Plant Downtime, Energy/tonne, Estimated Production Cost, Active Maintenance Alerts, Logistics Queue Time, each defined exactly as in `docs/business/KPI_DEFINITIONS.md` | Recomputation test from raw records matches payload (OER within 0.01 pp) |
| FR-EXEC-02 | Filters: date range, period, unit; current vs previous period with absolute and relative change (pp for ratios) | Filter changes numerator and denominator consistently |
| FR-EXEC-03 | Trends and drill-down from KPI to the underlying records | Each card links to a detail view with the same total |
| FR-EXEC-04 | Alerts with risk level, ranked by business effect; bottleneck overview; cost and productivity analysis; scenario comparison | Ranking rule documented and unit-tested |
| FR-EXEC-05 | AI Insight Summary generated from computed evidence (no canned text); each statement links to its evidence | Summary changes when scenario changes; every claim has a source link |
| FR-EXEC-06 | Export report (PDF or printable view) with provenance and assumptions | Export contains KPIs, labels and disclaimers |
| FR-EXEC-07 | The page answers: what is abnormal today, how much it affects business, which team checks first, what to decide | Tour step 7 and acceptance scenario E |

### 6.3 Palm Mill Production Intelligence (P0; epics E06, E11)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-MILL-01 | Data views: FFB intake and quality, processing rate, sterilizer cycle, steam pressure, digester temperature, press performance, clarification performance, CPO and kernel output, quality measurements, loss indicators | Each view driven by the same stored data as the KPIs |
| FR-MILL-02 | Process map page (`/demo/palm-mill/process`) from Plantation to Dispatch with the SPEC stage list, clickable nodes showing status, KPI, sensors, alerts, trends, recommendations (Digital Twin Lite) | Values equal those in sensor trends, KPIs and alerts for the same moment |
| FR-MILL-03 | AI-B01 OER forecast: features (FFB quality, wait-to-process time, timing, temperature, steam pressure, equipment efficiency, seasonality); training, validation, inference endpoint, feature importance, uncertainty indication, naive-baseline comparison, model version; sklearn | Model card; temporal split; MAE and RMSE vs naive baselines reported as measured; honest if baseline wins |
| FR-MILL-04 | AI-B02 production anomaly detection: OER low vs expected, steam pressure deviation, processing-rate drop, energy rise, abnormal loss; statistical baseline or Isolation Forest | Each anomaly shows score, observed evidence, normal range, possible contributing factors (never "proven cause"), recommended investigation, human verification status; scenario-based precision/recall/FPR/latency |
| FR-MILL-05 | AI-B03 production scenario analysis: adjust FFB intake, OER, availability, processing hours, energy cost, loss, CPO price; recomputed for real with formulas shown | Calculation example "1,000 t FFB x +0.5 pp OER = +5 t CPO" is labelled as a calculation example; results match the formulas |
| FR-MILL-06 | OER calculation and validation per KPI_DEFINITIONS (stock-change treatment, variants labelled) | KPI tests in section 6 of KPI_DEFINITIONS |
| FR-MILL-07 | CPO quality (FFA, moisture, dirt) shown with FFB wait-to-process time as a contributing factor | Link visible in the UI and data |

### 6.4 Predictive Maintenance AI and Work Orders (P0 analytics, P1 workflow; epic E07)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-MNT-01 | Equipment registry: Boiler, Sterilizer, Conveyor, Digester, Screw Press, Pump, Motor, Generator, Centrifuge, other rotating; sensors temperature, vibration, current, pressure, RPM, running hours, load, state | Registry and sensor history consistent with fixtures |
| FR-MNT-02 | AI-C01 health states Normal / Warning / Critical / Maintenance Required from **explicit computed criteria** (ISO 10816-3 zones, trends, temperature, current) | Criteria displayed; a test derives the state from stored readings |
| FR-MNT-03 | AI-C02 equipment anomaly detection on time series with anomaly score and contributing sensors | Scenario PRESS_VIBRATION_ANOMALY detected before the critical stage; metrics reported |
| FR-MNT-04 | AI-C03 failure-risk score with stated meaning and limits; **not** a calibrated probability | UI and model card carry the limit statement |
| FR-MNT-05 | AI-C04 recommendations (bearing, lubrication, alignment, sensor check, "inspect before continued use"), advisory only | Each recommendation shows evidence and requires human action |
| FR-MNT-06 | AI-C05 work-order workflow: AI Alert -> Engineer Review -> Work Order -> Assigned Technician -> Maintenance Record -> Resolved, with audit trail; changes after repair show in later data | Acceptance scenario B end to end; audit entries exist |
| FR-MNT-07 | AI-C06 impact what-if: downtime hours, lost production opportunity, estimated cost, maintenance cost, recovery scenario with assumptions and required data; supply- vs capacity-constrained cases handled (KPI_DEFINITIONS 4.10) | Result consistent with scenario simulator; no double counting |
| FR-MNT-08 | Equipment history and downtime analysis (DML-057) | Downtime totals reconcile with KPI-09 |

### 6.5 Logistics and Weighbridge Intelligence (P1; epic E08)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-LOG-01 | Flow Supplier -> Truck Arrival -> Queue -> Weighbridge -> FFB Inspection -> Unloading -> Processing Queue -> Exit with arrival records, queue dashboard, supplier records, weighbridge tickets (gross, tare, net), FFB grades, waiting time, unloading status, history | Tickets obey net = gross - tare; referential integrity |
| FR-LOG-02 | AI-D01 queue-time prediction; AI-D02 arrival-pattern forecast | Evaluation vs naive baseline, temporal split |
| FR-LOG-03 | AI-D03 queue optimisation: FIFO vs constraint-aware slots, simulated, assumptions shown | Scenario C compares waiting time; limits stated |
| FR-LOG-04 | AI-D04 logistics anomaly detection (implausible weight, excessive wait); wording never accuses anyone | Copy review; flags framed as data review |
| FR-LOG-05 | Show waiting time, turnaround, queue length, utilisation | Equal to KPI-13/14/19 definitions |

### 6.6 Energy and Sustainability (P1; epic E09)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-ENG-01 | Electricity, steam, fuel, water, energy per tonne FFB, energy cost per tonne, biomass/biogas scenario, trend, abnormal consumption | Values obey REL-08..REL-11 relations in `DOMAIN_PARAMETERS.json` |
| FR-ENG-02 | AI-E01 energy forecast; AI-E02 energy anomaly (high vs production volume, load-normalised) | Baseline comparison; scenario ENERGY_EFFICIENCY_DROP detected |
| FR-ENG-03 | AI-E03 what-if (efficiency, less idle run, energy mix, by-product value) with limits shown; no unsupported engineering or environmental conclusions | Limits text present; formulas visible |

### 6.7 Industrial Operations Copilot (P0; epic E10)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-COP-01 | TH/EN questions over demo data: why OER dropped today; which machine to inspect first; when downtime is highest; effect of cutting downtime; why energy per tonne rose; how many trucks are waiting; daily summary; prioritise plant issues; executive-meeting brief | Each example question returns an answer grounded in database values |
| FR-COP-02 | Pipeline: question -> intent -> safe tool selection -> authorised data query -> analytics -> evidence retrieval -> answer, using only structured tools: `get_production_summary`, `get_oer_trend`, `get_equipment_health`, `get_active_alerts`, `get_downtime_analysis`, `get_logistics_summary`, `get_energy_summary`, `run_business_scenario`, `search_demo_documents`; never free SQL | Tool-call trace visible; no SQL string reaches the database from the model |
| FR-COP-03 | RAG over newly authored sample documents (Palm Oil Process Overview, Equipment Inspection Procedure, Production Report, Maintenance Checklist, Demo Data Dictionary, KPI Guide), separated from real company documents; answers cite sources; source opens | Citation accuracy test; documents carry "sample" label |
| FR-COP-04 | Two runtime modes: LLM-enabled via provider adapter or local model; **no-API deterministic mode** with intent routing and templates grounded in the database; never canned replies presented as AI analysis | Both modes tested; no-API mode works with no network |
| FR-COP-05 | Safety: read-only; no control actions; confirmation before modifying records; per-role tool permission; prompt-injection protection; no unrestricted SQL; evidence and assumptions shown; explicit uncertainty when data is missing | Scenario D: non-existent data -> no fabrication; unauthorized tool -> refused; injection tests |
| FR-COP-06 | Evaluation: grounded-answer accuracy, tool-call success, unsupported-claim detection, citation accuracy, access-control eval | Results in MODEL_EVALUATION |

### 6.8 FFB Supplier and Traceability (P1; epic E11)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-TRC-01 | Supplier registration, plantation info, FFB delivery, batch tracking, weighbridge reference, quality inspection, production-batch link, output lot, report | Chain Supplier -> Delivery -> FFB Batch -> Processing Batch -> CPO Output Lot navigable |
| FR-TRC-02 | Multi-supplier mixing handled; the UI states whether tracking is **lot-based or mass-balance** | Statement visible; allocation math tested |
| FR-TRC-03 | Sustainability data model sketch for RSPO-style audits; **never claims certification** | Copy review |

### 6.9 ROI and Value Simulator (P0; epic E12)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-ROI-01 | Inputs: daily FFB throughput, operating days, current OER, target OER, CPO price, downtime hours, processing capacity, energy cost, maintenance expense, expected efficiency improvement, implementation cost, recurring operating cost | All adjustable; defaults come from DOMAIN_PARAMETERS (dated, illustrative) |
| FR-ROI-02 | Outputs: potential additional output, gross value uplift, estimated cost avoidance, implementation cost, annual recurring cost, scenario net benefit, payback, sensitivity analysis; cases Baseline / Conservative / Expected / Optimistic | Every formula and assumption traceable in the UI |
| FR-ROI-03 | No double counting: OER uplift and downtime recovery use separate bases | Unit test with overlapping inputs |
| FR-ROI-04 | Disclaimer: "Illustrative business scenario based on adjustable assumptions, not verified financial results of any company." | Present on every ROI view and export |

### 6.10 Computer Vision Prototype (P2; epic E11/E06 extension)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-CV-01 | Upload FFB image -> preview -> quality-assessment **prototype** -> visual explanation -> human review; safe upload handling | Rejects bad types/oversize; no accuracy claim |
| FR-CV-02 | Research Prototype documentation: dataset requirements, camera position, lighting, labelling protocol, class definitions, evaluation, pilot plan; never a generic image model relabelled as a validated grader | Doc present; UI says "prototype" |

### 6.11 Synthetic data engine (supports all; epic E04)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-DATA-01 | Deterministic, seeded; at least 90 days (default 120 ending at the demo anchor); domains: companies, facilities, production lines, equipment, sensors, readings, shifts, FFB deliveries, suppliers, weighbridge tickets, production batches, CPO output, quality measurements, maintenance events, work orders, truck trips, queue events, energy consumption, AI predictions, anomaly events, recommendations, audit logs, business scenarios | Same seed -> byte-identical dataset |
| FR-DATA-02 | Referential integrity and cross-domain consistency; mass balance holds (CPO ~ FFB x OER; kernel ~ FFB x KER; EFB, fibre, shell and POME as fractions of FFB); no physically impossible values without explanation | Validation report (DML-033) checks CHK-01..CHK-10 of `DOMAIN_PARAMETERS.json` |
| FR-DATA-03 | Scenario seeds NORMAL_DAY, OER_DEGRADATION, PRESS_VIBRATION_ANOMALY, STEAM_PRESSURE_DEVIATION, TRUCK_QUEUE_CONGESTION, ENERGY_EFFICIENCY_DROP, cross-module linked as in `PALM_MILL_PROCESS.md` section 5 | A scenario's signature appears in process, sensors, KPIs, anomaly, maintenance, copilot, scenario impact |
| FR-DATA-04 | Parameters come from `docs/business/DOMAIN_PARAMETERS.json`; code comments cite the key; low-confidence rows are never presented as facts | Static check for key references |
| FR-DATA-05 | Includes normal and abnormal periods, supplier quality variation, congestion, energy variation, sensor faults; Aug-Oct peak and November decline visible in the window | Seasonality check CHK-10 |

### 6.12 Roles, security and platform (epics E02, E14)
| ID | Requirement | Acceptance |
|---|---|---|
| FR-SEC-01 | Simulated roles via `X-Demo-Role` enforced server-side; cross-role access tests | Test matrix passes |
| FR-SEC-02 | Public demo hardening: rate limiting, input validation, safe uploads, error handling `{"error":{"code","message","details"}}`, audit records, demo-vs-prod config, no secrets in repo | Security tests; secret scan |
| FR-SEC-03 | Integrations are future contracts only (ERP, MES, SCADA, PLC, OPC UA, MQTT, weighbridge, LIMS, GPS/fleet, accounting/HR); nothing is claimed as connected | Integration page labels every item "planned contract" |
| FR-PLAT-01 | Modular monolith; Python owns analytics, rules and AI; web app is UI plus thin proxy; REST + OpenAPI -> generated TS types | Contract generation in CI |
| FR-PLAT-02 | Commands: `make setup`, `make seed`, `make dev`, `make test`, `make lint`, `make contracts`, `make models`, `make eval`; Docker files present (status "configured, not verified" if the daemon is unavailable) | Clone -> install -> seed -> run -> consistent data in the browser |

## 7. Non-functional requirements

| Area | Requirement (targets, to be measured and reported as measured) |
|---|---|
| Performance | Dashboard API p95 under 500 ms on the demo database on a laptop; first meaningful paint under 3 s on a mid-range connection; copilot no-API mode answer under 2 s |
| Reliability | Health checks; structured logs; graceful error and empty states; reset endpoint |
| Security | Server-side authorization, rate limiting, input validation, safe uploads, audit trail, prompt-injection and unauthorized-tool tests, no secrets in repo |
| Accessibility | WCAG 2.2 AA intent: keyboard operation, contrast in both themes, labelled charts with data tables, colour never the only signal |
| Usability | 5-minute executive path; dense-but-readable enterprise layout; Thai typography |
| Maintainability | Typed contracts, ADRs for deviations, ruff/lint, unit + integration + e2e tests, reproducible seed |
| Portability | SQLite by default, PostgreSQL via `DATABASE_URL`; Docker compose written; no SQLite-only SQL |
| Observability | Request IDs in logs; model version in every prediction |
| Compliance | No third-party logos or images without rights; sources recorded with retrieval dates |

## 8. Success metrics

Metrics are measured at delivery and reported as measured. Targets are goals, not claims.

| Category | Metric | Target | How measured |
|---|---|---|---|
| Demo experience | Executive path (landing -> tour -> dashboard -> insight -> scenario) | <= 5 min, no signup | QA stopwatch run, acceptance scenario E |
| Demo experience | Tour step consistency | 100% of cross-step assertions pass | E2E test |
| Correctness | KPI recomputation from raw records | 100% match within tolerance | KPI tests |
| Correctness | Data validation checks | All CHK-01..CHK-10 pass | Validation report |
| Honesty | Hardcoded metric/prediction found by static scan | 0 | Review + scan |
| Honesty | Pages with Synthetic Data badge | 100% of `/demo/*` | E2E |
| AI (OER) | Temporal-split MAE/RMSE vs naive baselines | Reported; beating baseline is desired but a loss is reported truthfully | MODEL_EVALUATION |
| AI (anomaly) | Scenario-based precision, recall, false-positive rate, detection latency | Reported per scenario | MODEL_EVALUATION |
| AI (copilot) | Grounded-answer accuracy, tool-call success, unsupported-claim detection, citation accuracy, access-control pass rate | Reported; access-control tests 100% pass | Copilot eval suite |
| Engineering | Clone -> install -> seed -> run | Works on a clean machine following README | Fresh-clone check |
| Engineering | Tests | Unit, integration, e2e, AI evaluation and security tests pass; counts reported | CI/test logs |
| Accessibility | Automated accessibility score on main pages | >= 90 (goal) | Lighthouse/axe, reported as measured |
| Recruitment | Materials present and consistent with what is built | Email TH/EN, résumé project summary, one-pager, case study | Review against Final Report |

## 9. Out of scope

Real company data or systems; production authentication/identity; real-time plant connectivity; machine control; certified accuracy; ERP/accounting replacement; mobile native apps; claims about company finances; modelling real petroleum depot stock; deep learning without justification; any automatic change to business records without human confirmation.

## 10. Risks and mitigations

| ID | Risk | Impact | Mitigation |
|---|---|---|---|
| R-01 | Scope too large for the time available | Half-built flagship | Priorities P0 > P1 > P2; status chips; finish P0 end to end first |
| R-02 | Fake accuracy or hardcoded metrics | Loss of credibility | Measured metrics only; baselines; synthetic-benchmark labels; scans |
| R-03 | Synthetic data physically wrong or inconsistent across modules | Engineers reject the demo | Parameters with sources; validation checks CHK-01..10; scenario causal map |
| R-04 | Demo read as an official system | Misrepresentation | Independent-concept branding, badges, disclaimers, no logos |
| R-05 | Public company information thin and dated | Weak business grounding | Say so; frame as concept; gap list; discovery proposal |
| R-06 | Outreach tone and timing | A proposal could land at an inopportune moment | Owner decides timing and tone; see private owner notes (not published); do not model or reference non-product context |
| R-07 | Public demo abused (spam, uploads, prompt injection) | Outage, bad content | Rate limits, validation, safe uploads, injection tests, session scoping |
| R-08 | LLM cost, availability or key leakage | Copilot downtime | Deterministic no-API mode default; adapter optional; no keys in repo |
| R-09 | Docker/Postgres not verifiable locally | Unverified deployment claims | Docker images verified in CI (2026-11-22); label anything else "configured, not verified" until verified |
| R-10 | Invented personal or résumé facts | Credibility and legal risk | Facts only from the applicant's own README; placeholders plus TODO |
| R-11 | Misleading ROI | Overclaiming | Illustrative disclaimer, adjustable inputs, separate bases, sensitivity |
| R-12 | Thai language quality | Poor first impression | TH/EN dictionaries reviewed by a Thai speaker (owner action) |
| R-13 | Parameter uncertainty (119 of 169 parameters low confidence) | Wrong realism | Ranges, confidence labels, scenario effects marked synthetic; replace with real data in a pilot |

## 11. Assumptions, dependencies and open questions

- **Dependencies:** `docs/business/DOMAIN_PARAMETERS.json` for the data engine; `KPI_DEFINITIONS.md` for services; `PALM_MILL_PROCESS.md` for scenario causality; architect's schema and contracts for everything else.
- **Assumption:** 120 days of data ending 2026-11-20; business day Asia/Bangkok; fictional entities only.
- **Open questions for the owner:** (1) timing and tone of outreach (see private owner notes, not published); (2) which developer facts and placeholders to publish; (3) deployment target and domain; (4) whether to enable an LLM provider adapter at all; (5) native Thai review of UI copy; (6) whether to include any a Thai palm oil operator public RSPO facts on the public pages (recommended: only as dated context, never as performance).

## 12. Traceability

| SPEC section | Requirements | Backlog tasks |
|---|---|---|
| 0 Mission and non-negotiables | FR-CC-01..04, FR-CC-08, FR-SEC-02, section 7 | DML-099..DML-106, DML-114 |
| 1 Business context | `docs/business/**`, FR-DATA-02 | DML-001..DML-008 |
| 3 Demo experience | FR-PUB-01..03, FR-TOUR-01..02 | DML-091, DML-097 |
| 4A Executive | FR-EXEC-01..07 | DML-035..DML-042 |
| 4B Palm mill | FR-MILL-01..07 | DML-043..DML-050, DML-079..DML-081 |
| 4C Maintenance | FR-MNT-01..08 | DML-051..DML-058 |
| 4D Logistics | FR-LOG-01..05 | DML-059..DML-064 |
| 4E Energy | FR-ENG-01..03 | DML-065..DML-070 |
| 4F Copilot | FR-COP-01..06 | DML-071..DML-078 |
| 4G CV | FR-CV-01..02 | P2 backlog |
| 4H Traceability | FR-TRC-01..03 | DML-082..DML-084 |
| ROI and Digital Twin | FR-ROI-01..04, FR-MILL-02 | DML-085..DML-090, DML-079..DML-081 |
| 5 UX | FR-CC-05..07, section 7 | DML-017..DML-024 |
| 6 Routes | FR-PUB-01, FR-MILL-02 | DML-010, DML-020..DML-023 |
| 7 Architecture | FR-PLAT-01..02, FR-SEC-03 | DML-009..DML-016 |
| 8 Synthetic data | FR-DATA-01..05 | DML-025..DML-034 |
| 9 AI quality | FR-MILL-03/04, FR-MNT-03/04, FR-COP-06, section 8 | DML-047, DML-048, DML-053, DML-102, DML-111 |
| 10 Roles | FR-SEC-01 | DML-103 |
| 13-14 Roadmap and portfolio | FR-PUB-01..03 | DML-092..DML-098 |
| 15 Acceptance scenarios | Scenario A: FR-MILL-03..05, FR-DATA-03; B: FR-MNT-02..06; C: FR-LOG-03; D: FR-COP-05; E: FR-TOUR-01, FR-EXEC-07, FR-ROI | DML-100, DML-101 |

## 13. Definition of done (from SPEC section 17)

Frontend, backend and DB consistent; seed/reset works; executive dashboard live; production AI real; maintenance AI real; copilot grounded; scenario simulator real; business impact with formulas; tour; responsive; tests pass; model evaluation report; docs complete; README works step by step; public demo reachable (or recorded as not deployed); case study; résumé summary; email draft; known limitations. The Final Report lists completed, partial and not-implemented features with evidence. A task is done only with evidence.
