# Capability Matrix: what is claimed, and what evidence backs it

> Owner: portfolio-writer. Written 2026-11-22 from the engineering log (kept private) and the agent status files **as they
> stood at writing time**. The frontend module pages and the Copilot were still being built; this file must be
> re-checked by the orchestrator in the last pass (R8) before any portfolio document is sent to anyone.
> Independent concept demo on **synthetic data**. Not an official system of any company.

## 1. Rules for reading this matrix

| Status | Meaning | May other documents state it as implemented? |
|---|---|---|
| `verified` | The orchestrator log records a check the orchestrator itself ran (command, test, SQL, live API call, browser inspection). | Yes |
| `claimed-by-agent` | Only the owning agent's own status file says it is done (or the work is configured but has never run). | No. Documents mark it **[PENDING VERIFICATION · CM-nn: ...]** |
| `not built` | No agent has reported it done; the status file says "in progress" or "not started". | No. Documents mark it **[PENDING VERIFICATION · CM-nn: in progress at writing time]** and never describe it as working |

The tag `CM-nn` in a document points to the row below with the same ID. When the orchestrator verifies a row, it changes
the status here and removes or rewrites every bracketed marker that carries that ID (`grep -rn "CM-nn" docs/`).

Where a row has two parts with different status, the status column says so. A part that is not named in the orchestrator
log stays `claimed-by-agent` even when it sits inside a test suite that the orchestrator re-ran, because a green suite
does not prove that a specific behaviour was looked at.

## 1a. Round-2 status (2026-11-22 night): supersedes the status column in section 2 for these rows

Basis: the engineering log (kept private), section "FINAL INTEGRATION RESULTS" (full pytest 1,139 passed, 2 skipped, 0 errors; typecheck, lint, vitest 75 passed; production build 34 of 34 pages; 20 Playwright e2e scenario tests passed, files `tests/e2e/specs/`). Where a row below is not listed, section 2 still applies.

| ID | Round-2 status | Basis and caveat |
|---|---|---|
| CM-05 | `verified` | `make docs` regenerated the contract: 95 paths, 0 stubs (OL) |
| CM-07 | `verified` (backend-a) | covered by the full suite; not separately SQL-checked for every endpoint |
| CM-10 | `verified` (health states); index components `claimed-by-agent` | health verified via API; the risk-index formula is in the suite but its numbers are not orchestrator-checked; a relative index, not a probability |
| CM-14 | `verified` (suite) | conservation tests in the full suite; mass balance, never a certification |
| CM-21 | `verified` | full suite includes the ML leakage tests |
| CM-24 | `verified` | e2e scenario E (executive) and orchestrator browser check of the executive page |
| CM-25 | `verified` | digital twin built; e2e scenario A |
| CM-26 | `verified` | palm-mill and AI-insights pages; e2e scenario A |
| CM-27 | `verified` | scenario simulator and business impact; e2e scenario A; ROI API verified by hand |
| CM-28 | `verified` | e2e scenario B (maintenance, equipment, work orders) |
| CM-29a | `verified` | e2e scenario C (logistics congestion); slot simulation still uncalibrated (CM-09) |
| CM-29b | `partial` (energy); traceability `verified` (suite) | energy page checked only by agent browser runs |
| CM-30a | `verified` | evaluator re-run; e2e scenario D |
| CM-30b | `verified` (evaluation); LLM mode `partial` | evaluation numbers in section 3; LLM mode tested only with a fake provider; no real model called |
| CM-32 | `verified` | tour e2e checks E1 and E2; the "5 minutes" is a design target |
| CM-35 | `verified` | 1,139 passed, 2 skipped; 20 e2e passed |
| CM-36 | `verified` (GitHub Actions run, 2026-11-22) | Docker images built and smoke-tested in CI; all CI jobs green |
| CM-37 | `not built` | no public deployment (owner decision) |

Owner decisions still open (not changed by this round): role and hands-on wording (TODO), Thai copy review and pronouns, phone publication, résumé PDF, LinkedIn, dates, hosting and domain.

## 2. The matrix

### A. Data engine

| ID | Capability and claim | Status | Evidence pointer | Caveat |
|---|---|---|---|---|
| CM-01 | **Deterministic synthetic data engine.** One fictional mill ("Demo Palm Mill A"), 120 days ending 2026-11-20, 1,569,016 rows (1,355,288 sensor readings), six cross-module scenario episodes, same seed gives the same checksum | `verified` | Orchestrator re-ran `make seed`: content checksum `34fc4a37...` equals `data/synthetic/MANIFEST.json`. Orchestrator's own SQL: FFB 111,814 t reconciles to CPO 20,643 t; 1,110 batches mass-balance; net = gross - tare on 11,813 tickets. Method: `docs/DATA_GENERATION.md` | Synthetic is not real. Losses, OER and FFA are simple parametric functions plus noise, not process physics. Degradation curves are prescribed. Scenario effects are smaller than first designed in places (`DATA_GENERATION.md` section 8). Comparison days carry no daily noise draw. The TRUCK_QUEUE_CONGESTION focus time is still to be moved to the queue peak in the final rebuild (orchestrator R7), which changes the seed checksum |
| CM-02 | **Data-quality validator**, 58 checks (referential integrity, mass balance, capacity limits, steam and energy relations, determinism) | `verified` | `python -m app.seed.validate` reported 58/58 (orchestrator log, data-engine row) | Checks prove internal consistency, not realism |

### B. Platform and API foundation

| ID | Capability and claim | Status | Evidence pointer | Caveat |
|---|---|---|---|---|
| CM-03 | **Database schema (44 tables) and Alembic migration**, SQLite default | `verified` (SQLite) | Orchestrator accepted the architect after `pytest` (150 passed at that time; includes the migration-equals-`create_all` test) and `ruff` clean; `tests/test_migrations.py` | PostgreSQL DDL rendering offline is **claimed-by-agent**; no live PostgreSQL was ever run |
| CM-04 | **API core and demo-grade security controls**: request id and JSON logs, error envelope, `as_of` validation, simulated-role permission checks (server side), per-IP and per-session rate limit, upload validation, append-only hash-chained audit log | `verified` | Full `pytest`: 334 passed, 26 skipped, 0 failed (orchestrator re-run, 2026-11-22). Orchestrator live RBAC check: `public_viewer`, `executive`, `logistics_officer` get 403, `maintenance_engineer` gets 201; writes without a session get 428; another visitor's record gets 404. Tests: `tests/test_rbac.py`, `test_ratelimit.py`, `test_audit.py`, `test_uploads.py`, `test_context.py` | Roles are headers, not authentication. Rate limiter is in-process (one replica). Audit chain is tamper-evident, not tamper-proof. No penetration test and no end-to-end security run yet (QA is still to come, R6). A lazy write on a read path (recommendation catalog rows) is noted for SECURITY.md |
| CM-05 | **Typed API contract**: 94 operations, OpenAPI exported to TypeScript types | `claimed-by-agent` | `docs/status/architect.md` (`make contracts`; `tsc --strict` ok). Orchestrator open item 1: contracts and generated docs must be regenerated after all backends land | Operation counts will change at regeneration |

### C. Backend modules (API only; screens are in section E)

| ID | Capability and claim | Status | Evidence pointer | Caveat |
|---|---|---|---|---|
| CM-06 | **Executive KPI API** (`/executive/*`): KPIs with previous-period comparison, series, insights, bottlenecks, cost and productivity, scenario comparison | `verified` | Orchestrator: `pytest tests/backend_a` 68 passed; API values equal direct SQL for the 7-day window (FFB 5,735.205 t; CPO 1,059.951 t; OER 18.481 % vs previous 18.244 %; downtime 8.0 h); `as_of` does not leak future data | KPI definitions are ratio-of-sums; estimated production cost uses assumed conversion and maintenance costs (Engineering Assumptions) |
| CM-07 | **Production and process-state, alerts, energy and reports APIs** | `claimed-by-agent` | `docs/status/backend-a.md` (31 of 31 operations implemented; tests inside the 68-test suite) | Not individually inspected by the orchestrator. No dispatch or tank tables exist, so those KPIs are derived and documented |
| CM-08 | **Logistics API** (queue now, tickets, suppliers, KPIs, arrival pattern) | `verified` for queue-now; other endpoints `claimed-by-agent` | Orchestrator: queue-now shows 15 trucks and 57 min average wait at 2026-11-14T06:00Z against 0 trucks on NORMAL_DAY | Queue timestamps are right-censored at the window end |
| CM-09 | **Queue slot simulation** (FIFO against constraint-aware slots) | `claimed-by-agent` | `docs/status/backend-a.md`; orchestrator open item 4 | **Baseline not yet calibrated**: at the congestion peak (as_of 2026-11-14 13:00 local, auditor re-run, agent-reported) FIFO replay gives 7.3 min average wait against 37.4 min observed; the slot policy cuts turnaround slightly (37.1 to 35.0 min) but total delay rises (12.4 against 7.3 min). Must not be presented as an optimisation result until recalibrated |
| CM-10 | **Equipment health states** from explicit criteria, **failure-risk index (0 to 100)** and **advisory recommendations** | `verified` for health state; index components and rule-based recommendations `claimed-by-agent` | Orchestrator: PRS-03 is `critical` at 2026-11-20T08:00Z and `normal` on 2026-11-05. `docs/status/backend-b.md` for index formula (risk 91.2 at the focus time) | The index is a relative ranking, not a calibrated probability. Service intervals are Engineering Assumptions |
| CM-11 | **Maintenance work-order workflow** with human confirmation and audit trail | `verified` | Orchestrator live API on a DB copy: create, assign, in_progress, resolved works; resolve requires notes; invalid jump gives 409; no session gives 428; other visitor gets 404; session reset removes the record; audit `chain_verified` true | Session-scoped sandbox; no connection to any real maintenance system |
| CM-12 | **Scenario catalogue with measured effects**, production what-if calculator (formulas echoed), demo session reset and simulated tick | `claimed-by-agent` (session reset `verified`) | `docs/status/backend-b.md`; orchestrator checked session reset | Measured scenario effects can be inside normal noise (PRESS_VIBRATION_ANOMALY moves plant OER about 0.17 to 0.3 pp, within day-to-day variation); the API says so |
| CM-13 | **ROI and value simulator API**: Baseline, Conservative, Expected, Optimistic cases; OER uplift and recovered downtime on separate bases (no double counting); exports; exact disclaimer | `verified` | Orchestrator recomputed by hand (OER component 1,367.1 t + downtime 799 t = 2,166 t; cost avoidance 1,413,418 THB) and matched the API at the original defaults; defaults were then recalibrated by the orchestrator (see section 3) and `backend_b` tests passed (163+) | Illustrative only. Every default for OER uplift, downtime reduction, efficiency, implementation cost and recurring cost is an Engineering Assumption, not a company figure |
| CM-14 | **Traceability API**: supplier to delivery to FFB batch to processing batch to CPO lot, mass-balance method stated | `claimed-by-agent` | `docs/status/backend-b.md` (supplier shares sum to 100 %; attributed CPO equals lot quantity). The underlying data mass balance is `verified` under CM-01 | Mass balance gives supplier shares, not physical certainty. Never a certification claim |

### D. Machine learning (all on synthetic data, temporal split at 2026-10-15)

| ID | Capability and claim | Status | Evidence pointer | Caveat |
|---|---|---|---|---|
| CM-15 | **AI-B01 OER forecast.** Result: **does not beat the best naive baseline** (served model MAE 0.268 pp against 24 h rolling mean 0.237 pp; a train-mean constant gives 0.264). **No granularity wins either** (hour 0.268 against 0.237; shift 0.205 against 0.146; day 0.219 against 0.161). A day-level "expected OER" band of about +/-0.49 pp flagged the OER_DEGRADATION episode (-0.86 pp). **ML driver attribution for OER is wrong-signed out of sample** | `verified` | Orchestrator re-ran `python -m app.ml.train` on a clean DB copy twice (first run and the follow-up) and reproduced the numbers; own SQL gave 24 h rolling MAE 0.231 and constant 0.264. Orchestrator log items 14 and 16. `docs/MODEL_EVALUATION.md` section 3 | Hourly OER is noise-dominated in the generator. The honest result is kept visible. **Constraint recorded by the orchestrator:** the UI, Copilot and insights must not present the model's driver attribution as the explanation; they use observed driver deviations against normal ranges. The band and attribution test numbers beyond the log are agent-reported |
| CM-16 | **AI-B02 production anomaly detection**: test precision 1.00, recall 4/7 | `verified` | Orchestrator fresh-train reproduction (P 1.0 / R 0.571). Isolation Forest comparison (recall 1/7) and latency are `claimed-by-agent` | 7 test labels; wide uncertainty. Anomaly is not a proven cause |
| CM-17 | **AI-C02 equipment anomaly detection and PRS-03 lead time**: first ML detection 56.5 h before the rule warning and 148.3 h before the rule critical alarm | `verified` | Orchestrator fresh-train reproduction; `docs/MODEL_EVALUATION.md` section 5. Per-label recall 4/6 and 0 false positives per day are `claimed-by-agent` | The degradation curve is prescribed by the generator (power law), so the lead time says nothing about real bearings. 6 test labels |
| CM-18 | **AI-E01 energy forecast and AI-E02 energy anomaly**: neither beats its baseline | forecast result `verified`; anomaly result (recall 0/1) `claimed-by-agent` | Orchestrator log: energy forecast loses to the baseline; `docs/MODEL_EVALUATION.md` section 6 (10.90 against 9.67 kWh/h MAE) | A single test label |
| CM-19 | **AI-D01 queue-time model** (marginal win: 2.72 against 2.78 min) and **AI-D02 arrival forecast** (does not beat the hour-by-weekday profile: 2.109 against 2.101) | `verified` | Orchestrator log: queue model marginal win, arrival forecast loses | Logistics flags (AI-D04) are `claimed-by-agent` (review prompts, never accusations) |
| CM-20 | **Detection pipeline** writes the models, anomaly events, alerts and predictions into the demo database. After the alert-noise fix: **64 ML alerts** (157 before; 19 rule alerts, 83 in total); a per-truck wait outlier is an anomaly event only; a sustained-queue alert is raised on TRUCK_QUEUE_CONGESTION (critical, 2026-11-14 10:00 local) and none in the NORMAL_DAY window; ML alerts are hidden before their detection time (`/api/v1/alerts?as_of=2026-11-10` shows 0 PRS-03 ML alerts; 8 are visible at 2026-11-20) | `verified` | Orchestrator log item 16 (fresh retrain on a clean copy, 112 s, every metric reproduced) and items 13 and 17 | Sustained-queue alert test: recall 3/3, precision 0.50, 0.054 false alerts per day (agent-reported). Event and prediction totals (163 anomaly events, 18,610 predictions) are agent-reported |
| CM-21 | **Leakage audit and ML tests**: forbidden-column audit, causality test, label isolation, determinism, as_of, upload security (46 tests in `tests/ml`) | `claimed-by-agent` | `docs/status/ml.md` (full suite 359 passed, 1 skipped); orchestrator log item 16 repeats the ML agent's later total of 362 passed, 1 skipped as a report, not a re-run. Orchestrator open item 5 flagged a failing leakage test while the ML agent was mid-work and asked for confirmation at hand-back (still listed open) | Treat as unconfirmed until the orchestrator's final full-suite run |
| CM-22 | **Eight model cards** and `GET /ai/models` | `claimed-by-agent` | `docs/ai/model-cards/*.md` (8 files present), generated by `python -m app.ml.evaluate` | Cards state limits and "no real-plant accuracy" |
| CM-23 | **Computer-vision FFB prototype**: safe upload, HSV colour statistics, validation protocol. No trained grader | `claimed-by-agent` (prototype) | `docs/status/ml.md`; `docs/MODEL_EVALUATION.md` section 10 | No licensed labelled dataset, so no accuracy is claimed. Colour statistics are PNG-only (no Pillow) |

### E. Screens, tour and public site

| ID | Capability and claim | Status | Evidence pointer | Caveat |
|---|---|---|---|---|
| CM-24 | **Executive Control Tower page** (`/demo/executive`): decision band, 12 KPI cards with sparkline, delta and provenance, filters, insight summary with evidence, prioritised alerts, impact cards with formulas, bottlenecks, scenario comparison, cost and productivity, export | `claimed-by-agent` | `docs/status/frontend-exec.md` (marked done by the agent): typecheck and lint exit 0; 26 vitest tests; Playwright plus axe on two scenarios x TH/EN x light/dark x three widths gave 0 serious or critical violations; agent browser check NORMAL_DAY OER 18.45 % against OER_DEGRADATION 17.64 % | Not inspected by the orchestrator. The API behind it is `verified` (CM-06). Impact figures on the page are `what_if` and illustrative |
| CM-25 | **Digital Twin Lite** (process flow, click a stage) | `not built` | `docs/status/frontend-exec.md`: not started | Process-state API is `claimed-by-agent` (CM-07) |
| CM-26 | **Palm-mill production, analytics and AI-insights pages** | `not built` | `docs/status/frontend-exec.md`: not started | Underlying API and ML results are in CM-07, CM-15 to CM-17 |
| CM-27 | **Scenario simulator page and Business Impact (ROI) page** | `not built` | `docs/status/frontend-exec.md`: not started | ROI API is `verified` (CM-13) |
| CM-28 | **Maintenance, equipment and work-order pages**: health counts and attention list with criteria, advisory recommendations with confirm dialogs, failure-risk ranking with its "not a probability" text, sensor trends with threshold lines, impact what-if with formulas, work-order create, assign, transition and audit trail with hash-chain badge | `claimed-by-agent` | `docs/status/frontend-ops.md` item 1 (marked done and verified in browser by the agent): PRS-03 walked end to end in a browser (alert 18, WO-202611-0118, assign, in progress, resolved, `chain_verified` badge); helper unit tests; axe found a dark-mode contrast issue in a shared component (worked around locally, request filed) | Not inspected by the orchestrator. Final axe and build verification still pending in the agent's own plan. The work-order API is `verified` (CM-11) |
| CM-29a | **Logistics page** (`/demo/logistics`): queue, tickets, waiting time, queue prediction, slot simulation (scenario C) | `claimed-by-agent` | `docs/status/frontend-ops.md` item 2 (marked done and verified in browser by the agent) | Not inspected by the orchestrator. Shows the slot simulation, whose baseline is not yet calibrated (CM-09): the page must show the limits |
| CM-29b | **Energy and traceability pages** | `not built` | `docs/status/frontend-ops.md`: items 3 and 4 not started | APIs: CM-07 (energy, agent-reported), CM-14 (traceability, agent-reported) |
| CM-30a | **Copilot core (stages 1 to 3)**: deterministic tool router and composer, grounding verifier (numbers checked against tool output, causal-claim flags), role allow-list, safety patterns and injection refusals (including Thai), retrieval over the sample knowledge base with citations, `/copilot/chat` and `/kb` endpoints | `claimed-by-agent` | `docs/status/copilot.md`: `tests/copilot` 54 passed (answers compared with direct SQL for OER, PRS-03 sensor value and trucks waiting; no-data refusals; `tool_denied` with an audit row; control and write requests refused with business-table counts unchanged; injection refusals; session isolation; rate limit; a test-only knowledge base with a planted injection document); full suite excluding copilot 355 passed, 2 skipped; ruff clean. All agent-reported | Not re-run by the orchestrator. **No evaluation numbers exist** (grounded-answer accuracy, tool-call success, unsupported-claim and citation accuracy, access-control evaluation), so none may be quoted |
| CM-30b | **Copilot evaluation harness, optional LLM adapter with fake-provider tests, Copilot model card, and the Copilot page** | `not built` | `docs/status/copilot.md`: evaluation harness is the next stage; `docs/status/frontend-ops.md` item 5 (Copilot page) not started | No Copilot accuracy claim may be made. Design is fixed in ADR-010 |
| CM-31 | **Sample knowledge-base documents** (7 files under `data/kb`) for the Copilot to cite | `verified` | Orchestrator: 7 files, front matter and limits sections present, no forbidden terms | Newly authored samples, not company documents |
| CM-32 | **Guided tour** "ทดลองชมระบบใน 5 นาที" (7 steps, back and forward, Esc) | `claimed-by-agent` (partial) | `docs/status/foundation.md` (ran 1 to 7 in a browser); `apps/web/content/tour.ts`. Target elements reported wired: steps 1 and 7 (executive page, `docs/status/frontend-exec.md`), steps 3, 4 and 5 (maintenance pages, `docs/status/frontend-ops.md`) | Targets for step 2 (AI insights page) and step 6 (scenario simulator page) do not exist yet, so those steps show narration with a "not built yet" chip. Not walked end to end by the orchestrator |
| CM-33 | **Public project site**: landing (TH/EN), developer profile | `verified` for `/` and `/developer` | Orchestrator: production build served; home and `/developer` inspected in a browser; developer facts match the applicant's README | Other public pages (about, opportunities, architecture, roadmap, contact) and the a11y scan (axe, 0 serious or critical) are `claimed-by-agent`. Thai copy was written by an agent; native-speaker review recommended |
| CM-34 | **Design system and i18n (TH default, EN)** | `verified` | Orchestrator: `typecheck`, `lint`, 6 vitest tests (TH/EN key parity) pass | The wider module pages are not built (CM-24 to CM-29) |

### F. Quality, delivery and documentation

| ID | Capability and claim | Status | Evidence pointer | Caveat |
|---|---|---|---|---|
| CM-35 | **Automated tests** | `verified` | Python: 334 passed, 26 skipped (ML tests waiting for trained models), 0 failed (orchestrator re-run 2026-11-22). Web: 6 vitest tests. `ruff` clean (at architect acceptance) | Agent-reported later totals (359, then 362 passed with 1 skipped, ML agent) are `claimed-by-agent`. Playwright end-to-end tests for acceptance scenarios A to E are `not built` (QA, R6). ML tests skip on a clean checkout until `make models` has run |
| CM-36 | **Docker images and GitHub Actions CI** | `verified` | GitHub Actions run on commit 23b77ad: jobs `api`, `contracts-and-web`, `docker` all `success` | The docker-compose file itself was not run; nothing is deployed; do not claim 'deployed' |
| CM-37 | **Public deployment** | `not built` | Orchestrator R12: owner decision on hosting, cost and domain | No live demo URL exists. Every document uses the placeholder `[DEMO_URL - not deployed yet]` |
| CM-38 | **Technical documentation set** (SPEC section 16 list) | mixed | Present and checked: SPEC, the build plan, DECISIONS (17 ADRs), architecture/*, DATA_GENERATION, AI_MODELS, MODEL_EVALUATION, business/*, BUSINESS_RESEARCH, PRODUCT_REQUIREMENTS (researcher, data-engine and ML docs accepted or reproduced by the orchestrator). Present but unreviewed: the portfolio set written by this agent. **Not built yet:** final README (draft only), SECURITY, DEPLOYMENT, DEMO_GUIDE, KNOWN_LIMITATIONS, API_DOCUMENTATION, TASKS | Generated docs (`API_CONTRACT.md`, `DATABASE_SCHEMA.md`) need regeneration (orchestrator open item 1) |

## 3. Verified numbers that other documents may quote

Quote these only with the words "synthetic" or "illustrative" beside them. Source column is the orchestrator log unless stated.

| Topic | Number | Note |
|---|---|---|
| Dataset | 120 days, 1,569,016 rows, 35 equipment, 112 sensors, 11,813 truck trips | Rows and counts from the seed command and data-engine report; checksum equality verified |
| Cross-table totals (synthetic) | FFB 111,814 t to CPO 20,643 t; 1,110 production batches mass-balance | Orchestrator SQL |
| Tests | Python 334 passed, 26 skipped, 0 failed; web 6 vitest passed | Orchestrator re-runs |
| OER forecast | MAE 0.2679 pp (model) against 0.2368 pp (24 h rolling mean); constant 0.264 pp | Model does **not** beat baseline |
| Production anomaly | precision 1.0, recall 0.571 (4 of 7 labels), test period | Few labels |
| PRS-03 press bearing | ML detection 56.5 h before the rule warning, 148.3 h before the rule critical alarm | Prescribed degradation curve |
| Energy forecast, arrival forecast | Both lose to their baselines | Reported as measured |
| Queue-time model | 2.72 against 2.78 min MAE | Marginal win |
| OER at other granularities | Shift 0.205 against 0.146 pp; day 0.219 against 0.161 pp (model against baseline); no granularity beats its baseline | Driver attribution is wrong-signed out of sample (do not present as the explanation) |
| Pipeline output | 8 models; 64 ML alerts after the noise fix (157 before; 83 including 19 rule alerts); sustained-queue alert on the congestion scenario, none on NORMAL_DAY | Event and prediction totals are agent-reported |
| ROI (illustrative) | Conservative: year-1 net -7.9 M THB, payback 28 months. Expected: +3.4 M THB, 9.3 months. Optimistic: +8.8 M THB, 6.8 months. Defaults: +0.10 pp OER, 5 % downtime cut, 3 % efficiency, 12 M THB implementation, 3.6 M THB/yr recurring | Engineering Assumptions; not company figures; **never** quote as a promise |
| KPI cross-check (synthetic) | 7-day FFB 5,735.205 t, CPO 1,059.951 t, OER 18.481 % (previous 18.244 %), downtime 8.0 h | API equals direct SQL |

## 4. What is NOT claimed

1. All data is **synthetic**. It describes a fictional mill. Nothing is a measurement of any company's facility, and no internal company data was used or seen.
2. **No connection to any real system.** ERP, MES, SCADA, PLC, OPC UA, MQTT, weighbridge, LIMS and fleet connections exist only as written contracts for the future.
3. **Several ML models do not beat their baselines** (OER forecast, energy forecast, energy anomaly, arrival forecast; queue time only marginally). They are reported that way. Good results on the prescribed press-bearing episode do not transfer to real bearings.
4. **No production deployment evidence.** There is no public URL, no load test, no uptime record and no operations history.
5. **Docker images and CI passed on GitHub Actions (2026-11-22); nothing is deployed and the compose file was not run.** PostgreSQL has been checked only as offline DDL.
6. **ROI is illustrative.** It is an adjustable scenario on stated assumptions, not a forecast and not a result for any company.
7. **Risk scores are not calibrated probabilities.** The failure-risk index is a ranking. Anomalies list possible contributing factors, not proven causes. Logistics flags are review prompts, never accusations.
8. **The AI is advisory and read-only.** It does not control any machine or change business records without human confirmation.
9. **No certification claim** of any kind (traceability is a mass-balance data model, RSPO-style audit sketch only).
10. **Roles are simulated viewpoints**, not authentication.
11. The Copilot evaluation, several module screens and the end-to-end tests were not complete at writing time (rows CM-25 to CM-27, CM-29b, CM-30b, CM-35); other screens and the Copilot core are agent-reported only (CM-24, CM-28, CM-29a, CM-30a).

## 5. Where pending markers appear (for the orchestrator's last pass)

Documents carry **[PENDING VERIFICATION · CM-nn: ...]** markers for every row above that is not `verified`. Typical markers:

| Marker | Where it appears | Flip when |
|---|---|---|
| CM-24 to CM-29b (screens) | PROJECT_VISION section 6, BUSINESS_PROPOSAL section 4, IMPLEMENTATION_ROADMAP section 13, TECHNICAL_CASE_STUDY sections 1 and 5, executive one-pager, résumé "add after verification" table, both emails | Each page is inspected in a browser at the public or local URL. CM-24, CM-28 and CM-29a are agent-reported done; CM-25 to CM-27 and CM-29b are not built |
| CM-30a, CM-30b (Copilot) | Same set | `tests/copilot` is re-run by the orchestrator (CM-30a); the evaluation harness exists and its numbers are reproduced (CM-30b) |
| CM-32 (tour) | PROJECT_VISION, TECHNICAL_CASE_STUDY, executive one-pager, emails | All seven steps land on built views |
| CM-36 (Docker and CI) | PROJECT_VISION, IMPLEMENTATION_ROADMAP, TECHNICAL_CASE_STUDY, résumé table | A Docker build and a GitHub Actions run have actually happened |
| CM-37 (deployment) | Emails, one-pager, BUSINESS_PROPOSAL contact line | The demo URL replaces `[DEMO_URL - not deployed yet]` |
| CM-04 (IP hashing in logs), CM-05, CM-07, CM-10 (risk index), CM-12, CM-14, CM-21, CM-22, CM-23 | TECHNICAL_CASE_STUDY, résumé "add after verification" table | The orchestrator re-runs the specific check |

Command to find every open marker: `grep -rn "PENDING VERIFICATION" docs/PROJECT_VISION.md docs/BUSINESS_PROPOSAL.md
docs/IMPLEMENTATION_ROADMAP.md docs/TECHNICAL_CASE_STUDY.md docs/portfolio/`.

The emails must not be sent until CM-37 is closed and the owner has reviewed every bracketed marker.
