# TASKS: status of DML-001 to DML-114

> Generated 2026-11-22 by the evidence collector from the engineering logs (kept private) and the engineering log (kept private). Re-generate (script in the evidence collector's scratchpad) when the status files change. Seed statuses in `docs/TASKS_SEED.md` (todo / done / partial) are superseded by the five values below. Paths are relative to the repo root. OL = the engineering log (kept private).

## Status values

- `done-verified`: the orchestrator log, or a command or test result quoted there, proves it.
- `done-claimed`: an agent status file says done with evidence; the orchestrator did not re-verify.
- `partial`: built in part; a stated gap remains.
- `not-started`: no artefact or evidence found.
- `blocked-owner`: needs a decision or resource only the owner can provide.

Priority: taken from the SPEC section 4 module (A, B, C, D, E, F, H, ROI). Modules with no label in SPEC use P0 (infrastructure and documentation default). DML-055 and DML-056 are P1 because SPEC section 2 lists maintenance work orders and human approval as P1. DML-079 to DML-081 are P0 following `apps/web/content/status.ts`.

## Summary

Total: 114 tasks.

| Status | Count |
|---|---:|
| done-verified | 78 |
| done-claimed | 23 |
| partial | 11 |
| not-started | 0 |
| blocked-owner | 2 |
| **total** | **114** |

By epic:

| Epic | done-verified | done-claimed | partial | not-started | blocked-owner | total |
|---|---:|---:|---:|---:|---:|---:|
| E01 Research & Product | 8 | 0 | 0 | 0 | 0 | 8 |
| E02 Architecture & Foundation | 5 | 0 | 2 | 0 | 1 | 8 |
| E03 Design System & UX | 6 | 2 | 0 | 0 | 0 | 8 |
| E04 Synthetic Data | 10 | 0 | 0 | 0 | 0 | 10 |
| E05 Executive Intelligence | 3 | 5 | 0 | 0 | 0 | 8 |
| E06 Palm Mill AI | 8 | 0 | 0 | 0 | 0 | 8 |
| E07 Maintenance AI | 5 | 3 | 0 | 0 | 0 | 8 |
| E08 Logistics | 3 | 2 | 1 | 0 | 0 | 6 |
| E09 Energy | 1 | 5 | 0 | 0 | 0 | 6 |
| E10 Copilot | 7 | 0 | 1 | 0 | 0 | 8 |
| E11 Process & Traceability | 5 | 1 | 0 | 0 | 0 | 6 |
| E12 ROI & Scenarios | 5 | 1 | 0 | 0 | 0 | 6 |
| E13 Portfolio & Recruitment | 3 | 2 | 3 | 0 | 0 | 8 |
| E14 Quality, Security & Deployment | 6 | 0 | 1 | 0 | 1 | 8 |
| E15 Documentation & Handover | 3 | 2 | 3 | 0 | 0 | 8 |
| **All** | **78** | **23** | **11** | **0** | **2** | **114** |

By priority: P0 97, P1 17, P2 0.

The P2 computer-vision track (`P2-CV` in `apps/web/content/status.ts`) has no PC-ID in the seed and is not counted.

## Task table

| ID | Epic | Priority | Objective | Owner | Status | Evidence | Caveat |
|---|---|---|---|---|---|---|---|
| DML-001 | E01 Research & Product | P0 | Study the target organisation business from public sources | researcher | `done-verified` | the public-facts research (kept private) (28 dated facts); OL accepted row researcher 2026-11-21 (files exist, JSON valid, sensitive note moved) | File-level acceptance; sources not re-fetched by orchestrator; source era 2013-2021 and partly inconsistent (researcher.md:12-17) |
| DML-002 | E01 Research & Product | P0 | Fact/Assumption register with references | researcher | `done-verified` | docs/business/ASSUMPTION_REGISTER.md; docs/business/DOMAIN_PARAMETERS.json (169 parameters, 46 sources); OL researcher row | 119 of 169 parameters low confidence, 0 high; 13 weak-source parameters flagged (researcher.md:32) |
| DML-003 | E01 Research & Product | P0 | Palm Mill process map | researcher | `done-verified` | docs/business/PALM_MILL_PROCESS.md; OL researcher row (file-level) | Mermaid diagram not render-tested (researcher.md:51) |
| DML-004 | E01 Research & Product | P0 | Industrial use-case analysis | researcher | `done-verified` | docs/business/USE_CASES.md (25 use cases); OL researcher row (file-level) | Value and feasibility scores are judgement-based |
| DML-005 | E01 Research & Product | P0 | Stakeholder personas | researcher | `done-verified` | docs/business/PERSONAS.md (7 personas); OL researcher row (file-level) | File-level acceptance only |
| DML-006 | E01 Research & Product | P0 | Define business KPIs | researcher | `done-verified` | docs/business/KPI_DEFINITIONS.md (22 KPIs); OL researcher row (file-level) | Business-day boundary and alert status vocabulary assumed (researcher.md:38) |
| DML-007 | E01 Research & Product | P0 | Rank AI use cases by value/feasibility | researcher | `done-verified` | docs/business/USE_CASES.md section 3 (rubric and ranking); OL researcher row (file-level) | Judgement-based ranking |
| DML-008 | E01 Research & Product | P0 | Product Requirements Document | researcher | `done-verified` | docs/PRODUCT_REQUIREMENTS.md; the business research (kept private); OL researcher row (table consistency check) | File-level acceptance; acceptance criteria not tested |
| DML-009 | E02 Architecture & Foundation | P0 | Monorepo setup | architect | `done-verified` | Makefile; package.json; pnpm-workspace.yaml; OL architect row (tree inspected, make setup) | None material |
| DML-010 | E02 Architecture & Foundation | P0 | Frontend setup | frontend-foundation | `done-verified` | apps/web (Next 16, React 19, TS strict); OL frontend-foundation row (typecheck, lint, 6 vitest, production build, home and /developer inspected in browser) | Later agent-reported test count is 75 (frontend-exec.md:44); see DML-099 |
| DML-011 | E02 Architecture & Foundation | P0 | AI API setup | architect | `done-verified` | apps/ai-api/app/main.py; OL architect row (pytest 150 passed, ruff clean, tree inspected) | Suite has grown since; see DML-099 |
| DML-012 | E02 Architecture & Foundation | P0 | PostgreSQL-compatible DB + migrations | architect | `partial` | apps/ai-api/alembic/versions/0001_initial_schema.py; tests/test_migrations.py (SQLite upgrade head); architect.md:11 | PostgreSQL never run live: offline DDL only (architect.md:11); psycopg not in requirements.lock (architect.md:41) |
| DML-013 | E02 Architecture & Foundation | P0 | Domain boundaries | architect | `done-verified` | apps/ai-api/app/models/{core,readings,production,logistics,traceability,maintenance,energy,ai,platform}.py; docs/architecture/DOMAIN_MODEL.md; OL architect row | Schema frozen; ML and data-engine requested additive changes (alert source enum) |
| DML-014 | E02 Architecture & Foundation | P0 | Data contracts | architect | `done-verified` | OL FINAL: make docs regenerated contracts (95 paths, 97 operations, 0 stubs); docs/architecture/API_CONTRACT.md | Regenerate after any later contract change |
| DML-015 | E02 Architecture & Foundation | P0 | Docker dev environment | architect | `blocked-owner` | infra/docker/{api.Dockerfile,web.Dockerfile,docker-compose.yml}; architect.md:14; OL item 19 and R13 | Never built: no Docker daemon running; owner must allow Docker Desktop to start |
| DML-016 | E02 Architecture & Foundation | P0 | CI pipeline | architect | `partial` | .github/workflows/ci.yml (parses as valid YAML, OL item 19) | Never run on GitHub; no CI run evidence; needs repository publication (owner decision) |
| DML-017 | E03 Design System & UX | P0 | Enterprise UI references study | frontend-foundation | `done-claimed` | frontend-foundation.md:11 ('done (applied)'); docs/architecture/FRONTEND_GUIDE.md | No standalone reference-study document found; evidence is that patterns were applied |
| DML-018 | E03 Design System & UX | P0 | Design tokens | frontend-foundation | `done-verified` | apps/web/app/globals.css (light/dark tokens); OL frontend-foundation row (typecheck, lint, tests) | Palette validator result is agent-reported (frontend-foundation.md:12) |
| DML-019 | E03 Design System & UX | P0 | Reusable UI components | frontend-foundation | `done-verified` | apps/web/components/{ui,demo,data,charts,states,layouts,shell,tour,public}; OL frontend-exec row (components exercised on inspected pages) | /ui-kit page itself not inspected by orchestrator |
| DML-020 | E03 Design System & UX | P0 | Public landing layout | frontend-foundation | `done-verified` | apps/web/app/(public)/page.tsx; OL frontend-foundation row (home inspected in browser) | Thai copy written by agent; native review recommended (frontend-foundation.md:46) |
| DML-021 | E03 Design System & UX | P0 | Executive dashboard layout | frontend-foundation | `done-verified` | ExecutiveLayout in apps/web/components/layouts/layouts.tsx; /demo/executive verified in OL frontend-exec row | Verified through the executive page only |
| DML-022 | E03 Design System & UX | P0 | Industrial operations layout | frontend-foundation | `done-verified` | OL FINAL: e2e scenario A-E + web build 34/34 pages (page layout exercised by tests/e2e specs) | Layout only; axe not re-run |
| DML-023 | E03 Design System & UX | P0 | AI workspace layout | frontend-foundation | `done-verified` | OL FINAL: e2e scenario D (tests/e2e/specs/d-copilot.spec.ts) renders AI workspace layout | Agent browser scripts plus e2e; axe not re-run |
| DML-024 | E03 Design System & UX | P0 | Responsive, accessibility, loading & error states | frontend-foundation | `done-claimed` | frontend-foundation.md:35-37 (axe 0 serious/critical; 9 pages x TH/EN x light/dark x 3 widths); frontend-exec.md:19; frontend-ops.md:31 | Axe runs are agent-reported; orchestrator has not re-run axe |
| DML-025 | E04 Synthetic Data | P0 | Industrial data schema | data-engine | `done-verified` | apps/ai-api/app/seed/*; data/synthetic/MANIFEST.json; OL data-engine row (make seed checksum 34fc4a37... equals MANIFEST) | Synthetic data; relations defined by the generator |
| DML-026 | E04 Synthetic Data | P0 | Data generator | data-engine | `done-verified` | apps/ai-api/app/seed/*; OL data-engine row (make seed re-run) | Checksum will change when R7 moves the TRUCK_QUEUE focus (OL item 3) |
| DML-027 | E04 Synthetic Data | P0 | Factory & equipment fixtures | data-engine | `done-verified` | apps/ai-api/app/seed/registry.py; data-engine.md:13 (35 equipment, 112 sensors) | Counts from data-engine report; checksum equality covers content |
| DML-028 | E04 Synthetic Data | P0 | Sensor time-series | data-engine | `done-verified` | apps/ai-api/app/seed/sensors.py; data-engine.md:14 (1,355,288 readings); checksum | Reading count agent-reported; checksum verified |
| DML-029 | E04 Synthetic Data | P0 | Production & quality data | data-engine | `done-verified` | apps/ai-api/app/seed/*; OL data-engine row (SQL: 1,110 batches mass balance) | Lab and by-product row counts agent-reported |
| DML-030 | E04 Synthetic Data | P0 | Logistics & weighbridge data | data-engine | `done-verified` | apps/ai-api/app/seed/logistics.py; OL data-engine row (net = gross - tare on 11,813 tickets, SQL) | Queue outages inferred from queue events, not stored (backend-a.md:42) |
| DML-031 | E04 Synthetic Data | P0 | Maintenance & energy data | data-engine | `done-verified` | apps/ai-api/app/seed/*; data-engine.md:17; validator 58/58 and checksum | Work-order and meter counts agent-reported |
| DML-032 | E04 Synthetic Data | P0 | Cross-domain scenario generator | data-engine | `done-verified` | docs/DATA_GENERATION.md section 6; data-engine.md:38-39 (scenario windows); validator | Scenario effects smaller than first designed (DATA_GENERATION section 8) |
| DML-033 | E04 Synthetic Data | P0 | Data-quality validation | data-engine | `done-verified` | apps/ai-api/app/seed/validate.py; OL data-engine row (58 checks, 0 failed) | Checks prove internal consistency, not realism |
| DML-034 | E04 Synthetic Data | P0 | Seed/reset commands | data-engine | `done-verified` | make seed; --if-empty / --reset (data-engine.md:20); OL data-engine row; OL item 15 (make demo-data added) | Final R7 rebuild still pending (OL item 3) |
| DML-035 | E05 Executive Intelligence | P0 | KPI aggregation services | backend-a | `done-verified` | apps/ai-api/app/services/kpi*.py; apps/ai-api/tests/backend_a (68 passed); OL backend-a row (KPIs equal direct SQL, 7-day window) | Ratio-of-sums definitions; cost uses Engineering Assumptions (backend-a.md:34-35) |
| DML-036 | E05 Executive Intelligence | P0 | Executive dashboard | frontend-exec | `done-verified` | apps/web/app/demo/executive; OL frontend-exec row (browser at PRESS focus; typecheck, lint, vitest, build) | Only /demo/executive verified; other exec-linked views not inspected |
| DML-037 | E05 Executive Intelligence | P0 | KPI time-series | backend-a | `done-claimed` | /executive/series (backend-a.md:9); KPI sparklines (frontend-exec.md:9) | ID clash: backend-b.md:35, frontend-foundation.md:51 and status.ts:118 map DML-037 to the simulated tick; resolve mapping |
| DML-038 | E05 Executive Intelligence | P0 | Drill-down navigation | frontend-exec | `done-claimed` | frontend-exec.md:9 (drill-down, alert drawer); OL frontend-exec row lists decision band and KPI cards only | Drill-down paths not separately verified by orchestrator |
| DML-039 | E05 Executive Intelligence | P0 | Alert prioritisation | backend-a | `done-claimed` | apps/ai-api/app/services/kpi_alerts.py; backend-a.md:33-41; frontend-exec.md:9 (ranking rule) | Priority method only in backend docstring (frontend-exec.md:53, contract gap 3) |
| DML-040 | E05 Executive Intelligence | P0 | AI insight summary | backend-a | `done-claimed` | apps/ai-api/app/services/kpi_insights.py (rules R1-R5); frontend-exec.md:9 (insight summary with evidence) | Narrative text English-only on Thai UI (OL item 27) |
| DML-041 | E05 Executive Intelligence | P0 | Business impact cards | backend-a | `done-verified` | impact cards on /demo/executive; OL frontend-exec row (what-if 0.38 t CPO / 12,887 THB at PRESS focus) | Illustrative what-if values; other impact views not checked |
| DML-042 | E05 Executive Intelligence | P0 | Exportable executive report | backend-a | `done-claimed` | apps/ai-api/app/services/kpi_reports.py; /reports/{type}/html (backend-a.md:14); frontend-exec.md:9 (print, CSV, MD) | HTML print only; no server-side PDF (backend-a.md:41) |
| DML-043 | E06 Palm Mill AI | P0 | Production data services | backend-a | `done-verified` | OL FINAL: full pytest 1139 passed (tests/backend_a); backend-a.md:11 | Production and process endpoints covered by the suite, not separately SQL-checked by the orchestrator |
| DML-044 | E06 Palm Mill AI | P0 | Process monitoring dashboard | frontend-exec | `done-verified` | tests/e2e/specs/a-production.spec.ts (scenario A: palm-mill views); OL FINAL 20 e2e passed | Overview checked through the e2e scenario; no visual review |
| DML-045 | E06 Palm Mill AI | P0 | OER calculation & validation | backend-a | `done-verified` | OL backend-a row (7-day OER 18.481 % equals direct SQL); apps/ai-api/app/services/kpi.py docstring | Hourly OER is noise-dominated (ml.md; MODEL_EVALUATION) |
| DML-046 | E06 Palm Mill AI | P0 | OER forecast baseline | ml | `done-verified` | apps/ai-api/app/ml/train.py; data/models/oer_forecast/1.0.0/metrics.json; OL ml row (24 h rolling baseline MAE 0.237 pp reproduced) | The baseline is the comparator the model loses to |
| DML-047 | E06 Palm Mill AI | P0 | OER prediction model: develop & evaluate | ml | `done-verified` | OL ml row and ml follow-up row (fresh retrain: served MAE 0.2679 vs baseline 0.2368; constant 0.264) | Model does NOT beat baseline; ridge variant lower test MAE 0.239 not served (docs/MODEL_EVALUATION.md:49) |
| DML-048 | E06 Palm Mill AI | P0 | Production anomaly detection | ml | `done-verified` | OL ml row (precision 1.0, recall 0.571 reproduced); docs/MODEL_EVALUATION.md | 7 test labels; Isolation Forest comparison agent-reported (ml.md:12) |
| DML-049 | E06 Palm Mill AI | P0 | AI explanation interface | ml | `done-verified` | tests/e2e/specs/a-production.spec.ts (scenario A: anomaly evidence); ml.md:11; OL FINAL | OER driver attribution wrong-signed out of sample (OL item 14); UI must not show it as cause |
| DML-050 | E06 Palm Mill AI | P0 | Interactive production scenarios | backend-b | `done-verified` | tests/e2e/specs/a-production.spec.ts (scenario A: scenario simulator consistent with data); OL FINAL | Production what-if baseline is trailing 30 days |
| DML-051 | E07 Maintenance AI | P0 | Equipment registry | backend-b | `done-verified` | tests/e2e/specs/b-maintenance.spec.ts (scenario B: pick machine, sensor history); OL FINAL | Registry view covered by e2e |
| DML-052 | E07 Maintenance AI | P0 | Sensor health monitoring | backend-b | `done-verified` | OL backend-b row (PRS-03 critical at 2026-11-20T08:00Z; normal at 2026-11-05); CM-10 | Sensor thresholds are Engineering Assumptions where not sourced (backend-b.md:12) |
| DML-053 | E07 Maintenance AI | P0 | Equipment anomaly detection | ml | `done-verified` | OL ml row (PRS-03 first ML detection 56.5 h before rule warning, 148.3 h before critical; reproduced) | Prescribed power-law degradation; 6 test labels; says nothing about real bearings |
| DML-054 | E07 Maintenance AI | P0 | Risk assessment logic | backend-b | `done-verified` | full pytest 1139 passed (backend_b tests of the risk index); OL FINAL | Relative ranking, not a probability; index components tested, not calibrated |
| DML-055 | E07 Maintenance AI | P1 | Maintenance recommendation service | backend-b | `done-claimed` | backend-b.md:21-23 (rules R1-R7, decisions, atomic WO); frontend-ops.md:25 (approve, approve + WO, reject) | Advisory only; decision flow not orchestrator-inspected |
| DML-056 | E07 Maintenance AI | P1 | Work-order workflow | backend-b | `done-verified` | OL backend-b row (create, assign, in_progress, resolved; 409; 428; 404; chain_verified true); CM-11 | Session-scoped sandbox; no link to any real maintenance system |
| DML-057 | E07 Maintenance AI | P0 | Equipment history & downtime analysis | backend-b | `done-claimed` | backend-b.md:52-54 (history, MTBF/MTTR, downtime by equipment); OL item 23 (downtime definition clash: 40.25 h vs 66.85 h) | Definition clash must be resolved and labelled (OL item 23); field name total_downtime_h is event sum (QA-18) |
| DML-058 | E07 Maintenance AI | P0 | Maintenance impact simulator | backend-b | `done-claimed` | backend-b.md:54 (POST /maintenance/impact; PRS-03 example 445,493 THB); frontend-ops.md:25 (impact form) | Downtime base must be plant downtime (OL item 23); impact figures illustrative |
| DML-059 | E08 Logistics | P1 | Supplier & truck records | backend-a | `done-claimed` | backend-a.md:13 (/logistics/suppliers); frontend-ops.md:40 (45 suppliers) | Synthetic supplier data; not orchestrator-inspected |
| DML-060 | E08 Logistics | P1 | Weighbridge management | backend-a | `done-claimed` | /logistics/tickets (backend-a.md:13); seed net = gross - tare verified (OL data-engine row); frontend-ops.md:40 (200 tickets) | Review flags are prompts, never accusations (CAPABILITY_MATRIX section 4) |
| DML-061 | E08 Logistics | P1 | Queue monitoring | backend-a | `done-verified` | OL backend-a row and item 'queue-now': 15 trucks, 57 min average at 2026-11-14T06:00Z vs 0 on NORMAL_DAY | Right-censored at window end (CM-08) |
| DML-062 | E08 Logistics | P1 | Queue prediction | ml | `done-verified` | OL ml row (queue model 2.72 vs 2.78 min; arrival forecast 2.109 vs 2.101 loses) | Queue model is a marginal win only; arrival forecast does not beat baseline |
| DML-063 | E08 Logistics | P1 | Scheduling scenario optimisation | backend-a | `partial` | OL open item 4; backend-a.md:43 (FIFO 5.7 vs 29.6 min observed; slots raise total delay 21 vs 6 min); frontend-ops.md:40 | Baseline not calibrated; must not be presented as an optimisation result |
| DML-064 | E08 Logistics | P1 | Logistics KPI dashboard | frontend-ops | `done-verified` | tests/e2e/specs/c-logistics.spec.ts (scenario C: congestion queue); OL FINAL | Slot simulation uncalibrated (DML-063) |
| DML-065 | E09 Energy | P1 | Energy data services | backend-a | `done-claimed` | backend-a.md:12 (/energy/summary, /energy/series); CM-07 | Not orchestrator-inspected |
| DML-066 | E09 Energy | P1 | Consumption analytics | frontend-ops | `done-claimed` | frontend-ops.md:53 (energy page, consumption analytics) | Agent browser check only |
| DML-067 | E09 Energy | P1 | Energy forecast | ml | `done-verified` | OL ml row (energy forecast loses to baseline, MAE 10.90 vs 9.67 kWh/h per docs/MODEL_EVALUATION.md section 6) | Does not beat baseline |
| DML-068 | E09 Energy | P1 | Energy anomaly detection | ml | `done-claimed` | ml.md:15 (anomaly recall 0/1); docs/TECHNICAL_CASE_STUDY.md:226 | Single labelled test event missed; no positive result |
| DML-069 | E09 Energy | P1 | Energy what-if analysis | backend-a | `done-claimed` | frontend-ops.md:53 (what-if: 552,234 vs 522,862 kWh); backend-a owns POST /energy/what-if | Purchased-power saving only; no environmental conclusion |
| DML-070 | E09 Energy | P1 | Energy efficiency dashboard | frontend-ops | `done-claimed` | frontend-ops.md:53 (energy efficiency dashboard, agent browser at ENERGY_EFFICIENCY_DROP) | Orchestrator has not inspected energy page |
| DML-071 | E10 Copilot | P0 | Tool-calling contracts | copilot | `done-verified` | apps/ai-api/app/copilot/tools.py; OL copilot row (tool denial, allow-list); CM-30a | Read-only; draft_work_order deliberately has no tool (copilot.md:39) |
| DML-072 | E10 Copilot | P0 | Structured analytics tools | copilot | `done-verified` | OL copilot row (numbers vs direct SQL: 15 trucks / 101.1 min; PRS-03 4.59 mm/s) | Not every tool name in SPEC section 4F is verified to exist |
| DML-073 | E10 Copilot | P0 | Demo knowledge base | copilot | `done-verified` | data/kb (README plus 6 sample documents); OL copilot row; copilot.md (/kb/documents 6 docs) | Authored sample documents, not company documents; OL CM-31 count of 7 includes README |
| DML-074 | E10 Copilot | P0 | Retrieval pipeline | copilot | `done-verified` | OL copilot row and item 22 (evaluate re-run: citations 9/10) | Thai summary chunks dominate retrieval (copilot.md:38); citation 9/10 |
| DML-075 | E10 Copilot | P0 | LLM provider adapter | copilot | `partial` | apps/ai-api/app/copilot/llm.py (none / openai_compatible / anthropic); copilot.md (fake provider and mocked httpx only); OL item 28 | No real provider ever called; needs an owner-supplied key or endpoint to exercise |
| DML-076 | E10 Copilot | P0 | Local non-LLM fallback | copilot | `done-verified` | OL copilot row (12/12 no-data refusals); OL item 28 (router answers ~54 % of fresh paraphrases correctly) | Held-out paraphrases: 25 correct, 16 clarified, 5 wrong of 46 |
| DML-077 | E10 Copilot | P0 | Evidence-based answer interface | frontend-ops | `done-verified` | tests/e2e/specs/d-copilot.spec.ts (scenario D1-D5); OL FINAL | Deterministic mode only; LLM mode not exercised |
| DML-078 | E10 Copilot | P0 | Prompt-injection / authorization / unsupported-claim tests | copilot | `done-verified` | OL copilot row and item 22 (evaluate: injections 26/26, unauthorized 23/23, no-data 12/12); OL weekly-limit section (pytest tests/security) | Attack set authored by the builder; no external red team |
| DML-079 | E11 Process & Traceability | P0 | Interactive palm mill process flow | frontend-exec | `done-verified` | apps/web/app/demo/palm-mill/process; OL frontend-exec row (PRESSING critical, 4 alerts, legend, advisory notices) | Perceived slowness about 10 s to first data under load (OL item 26) |
| DML-080 | E11 Process & Traceability | P0 | Link process view to sensor state | frontend-exec | `done-verified` | OL frontend-exec row (PRESSING critical matches PRS-03 critical; NORMAL_DAY all normal) | Cross-view consistency only partly checked (QA-16 still open) |
| DML-081 | E11 Process & Traceability | P0 | Link alerts to process flow | frontend-exec | `done-verified` | OL frontend-exec row (alert counts on nodes; detail drawer) | Detail drawer agent-tested |
| DML-082 | E11 Process & Traceability | P1 | Supplier-to-batch traceability | backend-b | `done-verified` | full pytest 1139 passed (traceability tests); backend-b.md:48-50 | Mass balance, never certification |
| DML-083 | E11 Process & Traceability | P1 | Batch-to-output traceability | backend-b | `done-verified` | full pytest 1139 passed (lot composition and conservation tests); backend-b.md:50 | Mass balance only |
| DML-084 | E11 Process & Traceability | P1 | Traceability reports | backend-b | `done-claimed` | backend-b.md:54 (GET /traceability/lots/{id}/report/printable); frontend-ops.md:47 (print) | Printable HTML delivered as typed PrintableDocument JSON (backend-b.md:69) |
| DML-085 | E12 ROI & Scenarios | P0 | Assumption input engine | backend-b | `done-claimed` | backend-b.md:46 (ROI defaults); OL item 10 (defaults recalibrated); frontend-exec.md:30 (inputs with fact tags) | Defaults are Engineering Assumptions; input UI not orchestrator-inspected |
| DML-086 | E12 ROI & Scenarios | P0 | Business calculation engine | backend-b | `done-verified` | OL item 10 and backend-b row (hand recomputation 2,166 t and 1,413,418 THB at original defaults; four cases after recalibration) | Hand check was done at superseded defaults; recalibrated figures are from OL item 10 |
| DML-087 | E12 ROI & Scenarios | P0 | Cost/benefit scenario comparison | backend-b | `done-verified` | CAPABILITY_MATRIX CM-13; OL item 10 (four cases); frontend-exec.md:30 (4-case table) | Illustrative; case multipliers are assumptions |
| DML-088 | E12 ROI & Scenarios | P0 | Sensitivity analysis | backend-b | `done-verified` | full pytest 1139 passed (ROI sensitivity tests); backend-b.md:46 | Tornado values come from tests; not spot-checked by the orchestrator |
| DML-089 | E12 ROI & Scenarios | P0 | Scenario explanation | backend-b | `done-verified` | OL frontend-exec row (OER_DEGRADATION -0.81 pp vs NORMAL_DAY matches SQL); backend-b.md:37-39 (measured effects) | Only the executive scenario comparison was checked against SQL |
| DML-090 | E12 ROI & Scenarios | P0 | ROI report export | backend-b | `done-verified` | full pytest 1139 passed (ROI export and disclaimer tests); backend-b.md:46 | No server-side PDF |
| DML-091 | E13 Portfolio & Recruitment | P0 | Independent project landing page | frontend-foundation | `done-verified` | apps/web/app/(public)/page.tsx; OL frontend-foundation row (home TH/EN inspected in browser) | Public copy claims are listed in docs/review/CLAIMS_LEDGER.md |
| DML-092 | E13 Portfolio & Recruitment | P0 | Developer profile | frontend-foundation | `done-verified` | apps/web/content/developer.ts; apps/web/app/(public)/developer; OL frontend-foundation row (developer facts match README) | Non-README facts shown as placeholders; contact phone no longer published on /contact (CLAIMS_LEDGER row 32) |
| DML-093 | E13 Portfolio & Recruitment | P0 | Skills & architecture showcase | frontend-foundation | `done-claimed` | frontend-foundation.md:21 (/technical-architecture); docs/architecture/SYSTEM_ARCHITECTURE.md | Page not orchestrator-inspected |
| DML-094 | E13 Portfolio & Recruitment | P0 | Technical case study | portfolio-writer | `partial` | docs/TECHNICAL_CASE_STUDY.md (418 lines); docs/portfolio/technical-case-study.md (pointer); portfolio-writer.md:15 | PENDING VERIFICATION markers remain; owner to confirm AI-assisted wording (TODO); some scenario numbers differ from UI (CLAIMS_LEDGER row 41) |
| DML-095 | E13 Portfolio & Recruitment | P0 | 90-day implementation proposal | portfolio-writer | `partial` | docs/BUSINESS_PROPOSAL.md (258 lines; no budget or return by design); portfolio-writer.md:13 | Owner decisions open (OL item 20); pending markers for screens |
| DML-096 | E13 Portfolio & Recruitment | P0 | 1-year / 3-year roadmap | frontend-foundation | `done-claimed` | /implementation-roadmap (frontend-foundation.md:22); docs/IMPLEMENTATION_ROADMAP.md (portfolio-writer.md:14) | Page not orchestrator-inspected; Years 1-3 are proposals |
| DML-097 | E13 Portfolio & Recruitment | P0 | Demo walkthrough | frontend-foundation | `done-verified` | OL FINAL: e2e tour E1/E2; tests/e2e/specs/e-executive.spec.ts; tour.ts | Tour text edited by orchestrator (OL item 24); 7 steps |
| DML-098 | E13 Portfolio & Recruitment | P0 | Recruitment email draft & résumé project summary | portfolio-writer | `partial` | docs/portfolio/application-email-template-en.md; application-email-template-th.md; resume-project-summary.md (portfolio-writer.md:17-18) | Drafts with owner TODOs; resume numbers stale (334 tests, 6 web tests); sending blocked until demo is deployed (CM-37) |
| DML-099 | E14 Quality, Security & Deployment | P0 | Unit tests | qa-security | `done-verified` | OL FINAL: full pytest 1139 passed, 2 skipped (opt-in full seed test; stub-count test), 0 errors; OL backend-b row | Earlier 334-pass run skipped the ML tests; now run in the full suite |
| DML-100 | E14 Quality, Security & Deployment | P0 | Integration tests | qa-security | `done-verified` | full pytest 1139 passed (includes tests/integration, 19 tests); qa-security.md:127-133 | Integration tests written by an agent |
| DML-101 | E14 Quality, Security & Deployment | P0 | End-to-end tests | web-verifier | `done-verified` | OL FINAL: 20 e2e passed; tests/e2e/specs/{a-production,b-maintenance,c-logistics,d-copilot,e-executive,banner}.spec.ts | Chromium only; no cross-browser run |
| DML-102 | E14 Quality, Security & Deployment | P0 | AI evaluation tests | ml / copilot | `done-verified` | OL ml row and follow-up row (evaluate reproduced); OL copilot row and item 22 (copilot evaluate re-run) | Evaluation sets authored by the builder; copilot held-out 25 of 46 |
| DML-103 | E14 Quality, Security & Deployment | P0 | Authorization & security tests | qa-security | `done-verified` | OL weekly-limit section (pytest tests/security all pass ~100 s; QA-02..05, 12..14 fixed); qa-security.md:21-33 | Open: QA-06, QA-07, QA-09, QA-10, QA-15; roles simulated; no penetration test |
| DML-104 | E14 Quality, Security & Deployment | P0 | Observability & error handling | architect | `done-verified` | app/logging.py and app/errors.py (architect.md:17); OL architect row; QA-05 fix (qa-security.md:96) | 500 responses lack request id and security headers (QA-15 open) |
| DML-105 | E14 Quality, Security & Deployment | P0 | Production-like demo deployment | owner | `blocked-owner` | OL R12 (owner decision: hosting, cost, domain); CM-37; no public URL | Demo URL is a placeholder everywhere |
| DML-106 | E14 Quality, Security & Deployment | P0 | Performance, accessibility, mobile, cross-browser checks | qa-security / frontend agents | `partial` | frontend-foundation.md:35-37 and frontend-exec.md:19-24 (axe, overflow at 375, 768, 1440); OL item 26 (perceived slowness) | No performance snapshot (qa-security Phase B2 pending); no cross-browser run; axe agent-reported |
| DML-107 | E15 Documentation & Handover | P0 | README & quick start | qa-docs | `partial` | README.md (draft; CAPABILITY_MATRIX CM-38); qa-security.md:129-132 (B4 clean-clone proof pending) | Clean-clone proof not done |
| DML-108 | E15 Documentation & Handover | P0 | Architecture Decision Records | architect | `done-verified` | docs/DECISIONS.md (17 ADR headings, ADR-001 to ADR-017); architect.md:19; OL architect row (tree inspected) | Count re-checked by evidence collector |
| DML-109 | E15 Documentation & Handover | P0 | Database & API documentation | architect | `done-verified` | make docs: docs/architecture/API_CONTRACT.md, docs/architecture/DATABASE_SCHEMA.md (44 tables), docs/API_DOCUMENTATION.md present; OL FINAL | Regenerate after any later contract change |
| DML-110 | E15 Documentation & Handover | P0 | Synthetic data methodology | data-engine | `done-verified` | docs/DATA_GENERATION.md (method, deviations, limits); OL data-engine row (checksum reproduced) | Must be updated after the R7 rebuild |
| DML-111 | E15 Documentation & Handover | P0 | AI model cards | ml | `done-claimed` | docs/ai/model-cards/*.md (8 ML cards plus copilot-router card); ml.md:18 (generated by app.ml.evaluate) | Cards not reviewed by orchestrator; regenerate after R7 |
| DML-112 | E15 Documentation & Handover | P0 | Business value / ROI assumptions | backend-b | `partial` | Engineering Assumption labels in app/services/roi.py (backend-b.md:46); docs/business/ASSUMPTION_REGISTER.md covers domain parameters only | No standalone ROI assumptions document found; BUSINESS_PROPOSAL section 13 states no budget |
| DML-113 | E15 Documentation & Handover | P0 | Demo operation & troubleshooting guide | web-verifier | `done-claimed` | docs/DEMO_GUIDE.md exists (written by web-verifier; not read by the collector) | Not orchestrator-reviewed |
| DML-114 | E15 Documentation & Handover | P0 | Final delivery report with known limitations | orchestrator | `partial` | docs/KNOWN_LIMITATIONS.md exists; final delivery report (R11) not yet written | Owner items open (OL FINAL owner list) |

## Remaining work

Every task that is not `done-verified`. Grouped by what is needed.

### A. Verification only (23)

The work exists; the orchestrator needs to inspect or re-run it.

| ID | Task | Status | Next action |
|---|---|---|---|
| DML-017 | Enterprise UI references study | `done-claimed` | Decide whether a separate reference-study note is needed; otherwise record as applied-only. |
| DML-024 | Responsive, accessibility, loading & error states | `done-claimed` | Re-run axe on frontend-ops pages at 375 and 1440 (web-verifier). |
| DML-037 | KPI time-series | `done-claimed` | Resolve ID mapping (KPI time-series vs simulated tick) in TASKS_SEED and status.ts; then verify /executive/series. |
| DML-038 | Drill-down navigation | `done-claimed` | Click through KPI drill-downs on /demo/executive. |
| DML-039 | Alert prioritisation | `done-claimed` | Confirm alert ordering and priority text against the backend rule. |
| DML-040 | AI insight summary | `done-claimed` | Inspect insight summary at two scenarios (OER_DEGRADATION and PRESS). |
| DML-042 | Exportable executive report | `done-claimed` | Export HTML and CSV from /demo/executive; check provenance labels. |
| DML-055 | Maintenance recommendation service | `done-claimed` | Browser check of approve, approve + WO and reject. |
| DML-057 | Equipment history & downtime analysis | `done-claimed` | Resolve downtime definition (OL item 23); confirm labels on every downtime view. |
| DML-058 | Maintenance impact simulator | `done-claimed` | Confirm impact base uses plant downtime (OL item 23); re-run example. |
| DML-059 | Supplier & truck records | `done-claimed` | Spot-check /logistics/suppliers against seed. |
| DML-060 | Weighbridge management | `done-claimed` | Browser check of weighbridge ticket view. |
| DML-065 | Energy data services | `done-claimed` | Spot-check energy endpoints against SQL. |
| DML-066 | Consumption analytics | `done-claimed` | Browser check of consumption analytics. |
| DML-068 | Energy anomaly detection | `done-claimed` | Keep as negative result; check wording only. |
| DML-069 | Energy what-if analysis | `done-claimed` | Recompute energy what-if example (552,234 to 522,862 kWh) from the formula. |
| DML-070 | Energy efficiency dashboard | `done-claimed` | Browser check of energy dashboard. |
| DML-084 | Traceability reports | `done-claimed` | Check printable report renders from the JSON wrapper. |
| DML-085 | Assumption input engine | `done-claimed` | Review default inputs and fact tags on the business-impact page. |
| DML-093 | Skills & architecture showcase | `done-claimed` | Browser check of /technical-architecture. |
| DML-096 | 1-year / 3-year roadmap | `done-claimed` | Browser check of /implementation-roadmap. |
| DML-111 | AI model cards | `done-claimed` | Review the 9 model cards after the R7 rebuild. |
| DML-113 | Demo operation & troubleshooting guide | `done-claimed` | Orchestrator review of docs/DEMO_GUIDE.md (walk the demo steps once). |

### B. Build (11)

Code, content or a test still has to be written or finished.

| ID | Task | Status | Next action |
|---|---|---|---|
| DML-012 | PostgreSQL-compatible DB + migrations | `partial` | Run alembic upgrade head against a live PostgreSQL; add psycopg to requirements.lock. |
| DML-016 | CI pipeline | `partial` | Publish repository (owner) and run the workflow on GitHub. |
| DML-063 | Scheduling scenario optimisation | `partial` | Calibrate queue service-time multiplier per window; re-run slot comparison (backend-a, OL item 4). |
| DML-075 | LLM provider adapter | `partial` | Owner supplies a provider key or endpoint for one real call; otherwise document as not exercised. |
| DML-094 | Technical case study | `partial` | Owner confirms role wording and Thai copy; re-check numbers after any re-seed. |
| DML-095 | 90-day implementation proposal | `partial` | Owner decisions (OL item 20); remove pending markers. |
| DML-098 | Recruitment email draft & résumé project summary | `partial` | Refresh resume numbers to the final run; owner TODOs; send only after deployment. |
| DML-106 | Performance, accessibility, mobile, cross-browser checks | `partial` | Performance snapshot (QA phase B2); cross-browser pass; re-measure twin load on a quiet machine. |
| DML-107 | README & quick start | `partial` | Rewrite README and prove quick start from a clean clone (qa-docs B4). |
| DML-112 | Business value / ROI assumptions | `partial` | Write an ROI assumptions table (value, source, label) into docs. |
| DML-114 | Final delivery report with known limitations | `partial` | Write the final delivery report (R11) from docs/KNOWN_LIMITATIONS.md and the owner items. |

### C. Owner decision (2)

Needs a decision or resource only the owner can supply.

| ID | Task | Status | Next action |
|---|---|---|---|
| DML-015 | Docker dev environment | `blocked-owner` | Owner allows Docker Desktop to start; then docker build and compose up. |
| DML-105 | Production-like demo deployment | `blocked-owner` | Owner decides hosting, cost and domain (R12). |
