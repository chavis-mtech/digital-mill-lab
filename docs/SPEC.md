# SPEC — Digital Mill Lab (condensed master prompt)

> Source of truth for every agent. This is a faithful condensation of the owner's Master Prompt:
> every requirement is kept, prose is removed. Thai terms are kept where they are UI copy.
> If anything here conflicts with the build plan (kept private), the build plan wins for *how*, SPEC wins for *what*.

## 0. Mission and non-negotiables

Product: **Digital Mill Lab — Intelligent Operations & AI Transformation**.
An **independent portfolio / concept demo** (NOT an official system of any company) that a job applicant
uses to propose long-term software + AI work to a target organisation (Thailand). Position sought:
**Technical Project Manager (Software & AI)**; also Enterprise Software, AI System Architecture,
Industrial Digital Transformation, Data Integration, Process Automation.

Must be a **working, testable, deployable** application. No decorative buttons/charts/AI panels.
Every primary feature needs a real data flow, implementation, validation, verifiable output.
If time is short: finish the most important parts so they truly work, record the rest transparently.

Honesty rules (hard):
1. No internal company data. Never present the system as official. Independent-concept branding. No logos/images we lack rights to.
2. "Synthetic Data" badge visible on every demo page. "Simulated Live" must say simulation.
3. Never claim integration with real company systems. Integrations = *future contracts* only.
4. AI never controls machines. Read-only analytics by default. Advisory only. Human confirmation before changing business records.
5. ROI is illustrative: "Illustrative business scenario based on adjustable assumptions, not verified financial results of any company."
6. No fake accuracy. Report model metrics as measured; if a model does not beat the baseline, say so. Synthetic benchmarks are not factory measurements.
7. Risk scores are NOT calibrated failure probabilities unless calibrated on real failure data. Anomaly ≠ proven cause. Logistics anomaly ≠ accusation of fraud.
8. No hardcoded metrics standing in for computation. No faked predictions. No invented test results. A task is "done" only with evidence.
9. No invented résumé facts. Developer facts come only from the applicant's own README
   (the applicant's own public GitHub profile README); everything else is a clearly marked placeholder + a TODO list.
   **Never read any other file in `chavis-mtech/` (especially `profile.secrets.env`, `*.zip`).**
10. No secrets/API keys in the repo. Public demo needs rate limiting, input validation, safe uploads, error handling, audit records, demo-vs-prod config separation.
11. Roles in the demo are *simulated viewpoints*, not production authentication. Public Demo Viewer works with no signup.

Fact taxonomy for all business/domain content — tag every statement as one of:
`Verified Public Fact` · `Historical Public Information` · `Industry Practice` · `Engineering Assumption` ·
`Synthetic Demonstration Data` · `Proposed Future Capability`.

## 1. Business context

Target: a diversified Thai industrial group with palm oil, petroleum, port and logistics businesses (its public website is used only as dated context).
Public info suggests: oil palm plantation + seedling nursery, palm oil extraction, petroleum & depots,
port/warehouse/logistics, transport, other businesses. Some operational info may be dated/unverified.

Primary focus = **palm oil mill**. Workflow:
Plantation → Harvest → FFB transport → Weighbridge → FFB reception → Grading → Sterilization → Threshing →
Digestion → Pressing → Clarification → CPO storage → Dispatch. Related: kernel recovery, boiler & steam, electricity,
water, wastewater/POME, biogas/biomass, maintenance, QC, lab, planning, supplier mgmt, sustainability & traceability.
Respect correct relationships between raw material, products, by-products and waste. Never simulate engineering wrongly to make charts pretty.

Every feature must answer ≥1: what cost does it cut / efficiency it adds / risk it lowers / duplicate work it removes /
planning accuracy it adds / how it improves executive decisions / what evidence supports it / what a real plant would need.

## 2. Outcomes, audiences, scope

Five outcomes: (A) Industrial process understanding (B) Applied AI engineering (C) Enterprise architecture
(D) Business value (KPI/cost/risk/productivity) (E) Technical leadership (roadmap, backlog, risks, plan).
Audiences: Executive/MD, Factory Mgr, Production Mgr, Maintenance Eng, IT Mgr, HR/Recruiter, Technical Interviewer.
Non-technical executive must get the value in 3–5 min; engineers must be able to verify logic.

Priority:
- **P0 flagship (fully functional):** Executive Control Tower · Palm Mill Production Intelligence · AI Anomaly Detection / Predictive
  Maintenance · Industrial AI Copilot · Scenario Simulator · Traceable Business Impact Analysis.
- **P1 supporting (working workflows):** Logistics & Weighbridge · Energy & Resource · FFB Supplier & Traceability · Maintenance Work Orders · AI Recommendations & Human Approval.
- **P2 concepts (clearly labelled prototype, never "production"):** Computer Vision FFB grading · Smart Plantation/Yield forecast · Petroleum inventory · Port & terminal scheduling · Cross-company data platform.

## 3. Demo experience

Landing (TH default, EN toggle). Headline: **"Intelligent Operations for a Smarter Industrial Future"**.
Subtitle: "An independent AI-driven industrial transformation concept, exploring how manufacturing intelligence, predictive analytics, and connected operations could create measurable business value."
Sections: Project Overview · Business Challenges · AI Solutions · Explore Live Demo · Technical Architecture · Implementation Roadmap · About the Developer · Contact/Resume.

Guided Executive Tour — button "ทดลองชมระบบใน 5 นาที". Skippable/backable steps, data consistent across steps:
1 Production efficiency drop detected → 2 AI analyses related data → 3 Equipment abnormal signal found → 4 AI proposes inspection →
5 Manager creates Maintenance Work Order → 6 System simulates production impact → 7 Executive dashboard shows status & potential benefit.

## 4. Modules

### A. Executive Industrial Control Tower (P0)
KPIs: FFB Received, FFB Processed, CPO Produced, OER, KER, Throughput, Equipment Availability, Plant Downtime,
Energy/tonne, Estimated Production Cost, Active Maintenance Alerts, Logistics Queue Time.
Features: filters (date, period, unit); current vs previous period; trends; drill-down; alerts with risk level; AI Insight Summary;
bottleneck overview; cost & productivity analysis; scenario comparison; export report.
**Every number is labelled `synthetic_actual` | `forecast` | `what_if`.**
Answers: "What is abnormal today, how much does it affect business, which team checks first, what to decide."

### B. Palm Mill Production Intelligence (P0)
Data: FFB intake & quality, processing rate, sterilizer cycle, steam pressure, digester temp, press performance, clarification
performance, CPO & kernel output, quality measurements, loss indicators.
- AI-B01 OER Forecast: features = FFB quality, wait-to-process time, production timing/conditions, temperature, steam pressure, equipment efficiency, seasonality.
  Needs training, validation, inference endpoint, feature importance/explanation, uncertainty indication, naive-baseline comparison, model version. sklearn (HistGradientBoosting/RandomForest…); no deep learning without justification.
- AI-B02 Production Anomaly Detection: OER low vs expected, steam pressure deviation, processing-rate drop, energy rise, abnormal loss.
  Statistical baseline / Isolation Forest. Show: anomaly score, observed evidence, normal range, possible contributing factors (never "proven cause"), recommended investigation, human verification status.
- AI-B03 Production Scenario Analysis: user adjusts FFB intake, OER, availability, processing hours, energy cost, loss, CPO price → recomputed for real, formulas shown.
  Example (label as calculation example): 1,000 t FFB × +0.5 pp OER = +5 t CPO.

### C. Predictive Maintenance AI (P0)
Equipment: Boiler, Sterilizer, Conveyor, Digester, Screw Press, Pump, Motor, Generator, Centrifuge, other rotating.
Sensors: temperature, vibration, current, pressure, RPM, running hours, load, state.
- AI-C01 Health states Normal/Warning/Critical/Maintenance Required — explicit computed criteria, not random colours.
- AI-C02 Equipment anomaly detection: time-series, anomaly score, contributing sensors.
- AI-C03 Failure Risk score with stated meaning + limits (not a calibrated probability).
- AI-C04 Recommendations (bearing, lubrication, alignment, sensor check, "inspect before continued use") — advisory only.
- AI-C05 Work Order workflow: AI Alert → Engineer Review → Work Order → Assigned Technician → Maintenance Record → Resolved.
- AI-C06 Impact analysis what-if: downtime hours, lost production opportunity, est. cost, maintenance cost, recovery scenario; show assumptions & required data.

### D. Logistics & Weighbridge Intelligence (P1)
Flow: Supplier → Truck Arrival → Queue → Weighbridge → FFB Inspection → Unloading → Processing Queue → Exit.
Features: arrival records, queue dashboard, suppliers, weighbridge tickets (gross/tare/net), FFB grades, waiting time, unloading status, history.
AI-D01 queue-time prediction · AI-D02 arrival-pattern forecast · AI-D03 queue optimisation (FIFO vs constraint-aware slots, simulated) ·
AI-D04 logistics anomaly detection (implausible weight / excessive wait; never accuse anyone). Show waiting time, turnaround, queue length, utilisation.

### E. Energy & Sustainability (P1)
Electricity, steam, fuel, water, energy/tonne FFB, energy cost/tonne, biomass/biogas scenario, trend, abnormal consumption.
AI-E01 energy forecast · AI-E02 energy anomaly (high vs production volume) · AI-E03 what-if (efficiency, less idle run, energy mix, by-product value) — show limits, no unsupported engineering/environment conclusions.

### F. Industrial Operations Copilot (P0)
Natural-language questions over demo data (TH/EN), e.g. why OER dropped today · which machine to inspect first · when is downtime highest ·
effect of cutting downtime · why energy/t rose · how many trucks waiting · daily summary · prioritise plant issues · exec-meeting brief.
Pipeline: question → intent → safe tool selection → authorized data query → analytics → evidence retrieval → answer.
Tools (structured, never free SQL): get_production_summary, get_oer_trend, get_equipment_health, get_active_alerts, get_downtime_analysis,
get_logistics_summary, get_energy_summary, run_business_scenario, search_demo_documents.
RAG over *newly authored sample docs* (Palm Oil Process Overview, Equipment Inspection Procedure, Production Report, Maintenance Checklist, Demo Data Dictionary, KPI Guide), clearly separate from real company docs; answers cite sources and the source doc is openable.
Two runtime modes: (1) LLM-enabled via provider adapter / local model; (2) **no-API deterministic mode** with intent routing + templates grounded in DB. Never hardcoded canned replies presented as AI analysis.
Safety: read-only; no control actions; confirm before modifying records; tool permission validation per role; prompt-injection protection;
no unrestricted LLM SQL; show evidence & assumptions; explicit uncertainty when data is missing.

### G. Computer Vision Prototype (P2)
Upload FFB image → preview → quality-assessment *prototype* → visual explanation → human review. Safe upload handling.
Real model only if a properly licensed labelled dataset exists; otherwise a **Research Prototype** documenting dataset requirements, camera position,
lighting, labelling protocol, class definitions, evaluation, pilot validation plan. Never relabel a generic image model as a validated grader. **No fake accuracy.**

### H. FFB Supplier & Traceability (P1)
Supplier registration, plantation info, FFB delivery, batch tracking, weighbridge ref, quality inspection, production-batch link, output lot, report.
View: Supplier → Delivery → FFB Batch → Processing Batch → CPO Output Lot. Handle multi-supplier mixing; state whether tracking is **lot-based or mass-balance**.
Sustainability data model sketch for RSPO-style audits; never claim certification.

### ROI & Value Simulator
Inputs: daily FFB throughput, operating days, current OER, target OER, CPO price, downtime hours, processing capacity, energy cost, maintenance expense,
expected efficiency improvement, implementation cost, recurring operating cost.
Outputs: potential additional output, gross value uplift, estimated cost avoidance, implementation cost, annual recurring cost, scenario net benefit, payback, sensitivity analysis.
Cases: Baseline / Conservative / Expected / Optimistic. Every formula & assumption traceable. **No double counting** (OER uplift vs downtime recovery use separate bases).
Disclaimer text above (rule 5).

### Industrial Digital Twin Lite
2D interactive flow: FFB Reception → Sterilization → Threshing → Digestion → Pressing → Clarification → CPO Storage. Click a node → equipment status, process KPI,
sensor readings, alerts, trends, AI recommendations — driven by the same simulated state.
Scenario "Press Performance Degradation" must show **consistent** values in: process flow, sensor trend, production KPI, anomaly detection, maintenance alert, copilot context, scenario impact.

## 5. UX/UI
Modern enterprise industrial SaaS; not a basic admin template. Clean industrial, premium, dense-but-readable, modern type, responsive, strong hierarchy, subtle motion, professional charts, high accessibility.
Stack preference: Next.js, React, Tailwind, shadcn/ui, Radix, Lucide, TanStack Table/Query, ECharts/Recharts, a motion lib.
Theme: light + dark; neutral bg; deep navy / industrial charcoal; restrained emerald/teal accent; amber = warning; red = critical. Colour = meaning, not decoration.
Layouts: Public Landing · Executive App · Industrial Operations · AI Workspace · Technical Docs. Tablet/desktop first; mobile must give an overview. Loading/error/empty states everywhere.

## 6. Routes
Public: `/`, `/about-project`, `/business-opportunities`, `/technical-architecture`, `/implementation-roadmap`, `/developer`, `/contact`.
Demo: `/demo`, `/demo/executive`, `/demo/palm-mill`, `/demo/palm-mill/process`, `/demo/palm-mill/analytics`, `/demo/palm-mill/ai-insights`,
`/demo/maintenance`, `/demo/maintenance/equipment`, `/demo/maintenance/work-orders`, `/demo/logistics`, `/demo/energy`, `/demo/traceability`,
`/demo/ai-copilot`, `/demo/scenarios`, `/demo/business-impact`.
Docs: `/docs/overview`, `/docs/architecture`, `/docs/data-model`, `/docs/ai-methodology`, `/docs/integration`, `/docs/security`, `/docs/roadmap`.
Routes may change only with an architectural reason; all user journeys must remain covered.

## 7. Architecture principles
Modular monolith first; domain-driven module boundaries; API-first; strong typing; AI inference separated from business rules; reproducible data pipeline;
observability (structured logs, health checks); automated tests; secure defaults; Docker + compose; env-based config; GitHub Actions; ADRs for deviations.
Future integration *contracts only*: ERP, MES, SCADA, PLC, OPC UA, MQTT, weighbridge, LIMS, GPS/fleet, accounting/HR.

## 8. Synthetic data engine (critical)
Deterministic (seeded). Domains: companies, facilities, production lines, equipment, sensors, sensor readings, production shifts, FFB deliveries, suppliers,
weighbridge tickets, production batches, CPO output, quality measurements, maintenance events, work orders, truck trips, queue events, energy consumption,
AI predictions, anomaly events, AI recommendations, audit logs, business scenarios.
≥ 90 days. Normal + abnormal periods, maintenance-related events, production variation, supplier quality variation, logistics congestion, energy variation.
Referential integrity AND cross-domain consistency. No physically impossible values without explanation (mass balance, capacity, steam/energy relations).
Scenario seeds: NORMAL_DAY, OER_DEGRADATION, PRESS_VIBRATION_ANOMALY, STEAM_PRESSURE_DEVIATION, TRUCK_QUEUE_CONGESTION, ENERGY_EFFICIENCY_DROP — cross-module linked.
Playback: Today · Last 7 Days · Last 30 Days · Scenario Date · Simulated Live Mode (labelled simulation).

## 9. AI engineering quality
Every model has a Model Card: purpose, input features, training data, synthetic-data assumptions, algorithm, evaluation method, validation results, limitations, known failure modes, deployment status.
Forecasting: MAE, RMSE, naive-baseline comparison, **temporal** train/test split. Anomaly: precision, recall, false-positive rate, detection latency, scenario-based eval.
Copilot: grounded-answer accuracy, tool-call success, unsupported-claim detection, citation accuracy, access-control eval. Watch for data leakage (we generate the data ourselves).
Never present synthetic benchmarks as real-plant measurements. If a model loses to baseline, show it truthfully.

## 10. Roles (simulated)
Executive · Factory Manager · Production Engineer · Maintenance Engineer · Logistics Officer · AI Analyst · System Administrator · Public Demo Viewer.
Server-side authorization with cross-role access tests. Demo accounts hold no sensitive data.

## 11. Backlog epics (task IDs — see docs/TASKS.md for full table)
E01 Research & Product (DML-001–008) · E02 Architecture & Foundation (009–016) · E03 Design System & UX (017–024) · E04 Synthetic Data (025–034) ·
E05 Executive Intelligence (035–042) · E06 Palm Mill AI (043–050) · E07 Maintenance AI (051–058) · E08 Logistics (059–064) · E09 Energy (065–070) ·
E10 Copilot (071–078) · E11 Process & Traceability (079–084) · E12 ROI & Scenarios (085–090) · E13 Portfolio & Recruitment (091–098) ·
E14 Quality/Security/Deploy (099–106) · E15 Docs & Handover (107–114).
Tasks need: ID, epic, priority, objective, dependencies, steps, acceptance criteria, tests, status.

## 12. Implementation phases (acceptance)
P1 Foundation: clone → install → seed → run → browser shows consistent data. P2 Working AI: pick scenario → models process data → verifiable evidence.
P3 Connected workflows: workflow changes are reflected in related modules. P4 Copilot: answers from system data with sources, no-API fallback, evaluation.
P5 Recruitment-ready: public demo, guided tour, architecture page, case study, roadmap, proposal, profile, résumé summary, email draft, deployment verification.

## 13. Transformation roadmap page (for an industrial organisation)
30 days Discovery (existing systems, stakeholders, pain points, data availability, IT/OT limits, KPI baseline, pick pilot) ·
31–60 Pilot dev (integration plan, dashboard, authorised data, AI on historical data, validation, user evaluation) ·
61–90 Pilot evaluation (trial, feedback, model performance, business KPIs, security/reliability, ROI assessment, scale-up plan) ·
Year 1 Operational digitalisation · Year 2 AI & Industrial IoT · Year 3 Group-wide intelligent operations.
Show dependencies, team roles, risks, deliverables, success criteria. **No invented company budgets/returns.** Tone: "opportunity to build on", never "existing systems are bad".

## 14. Portfolio & recruitment
Portfolio sections: objective, business understanding, solution architecture, implemented AI capabilities, data engineering, SW engineering practices, security, challenges, business-impact method, future expansion.
Case study title: "Designing an AI-Driven Industrial Intelligence Platform for Palm Oil Manufacturing" (why it matters, context, design decisions, AI approach, data reliability, tradeoffs, testing, demo limitations, production adoption needs).
Files: `docs/portfolio/{application-email-template-th.md, application-email-template-en.md, resume-project-summary.md, executive-one-pager.md, technical-case-study.md}`.
Email: polite, professional, modest, long-term value, collaborate with the existing team; contains intro, relevant experience, why the target organisation, proposed opportunities, demo link, GitHub link, résumé mention, invitation to talk.
Never claim the company has problems/missing systems without evidence. Résumé project entry = only what is actually built and verified.

## 15. Acceptance scenarios
A Production degradation: load NORMAL_DAY → baseline KPI → switch to OER_DEGRADATION → production data changes correctly → anomaly detection → evidence → Copilot analyses → Scenario simulator consistent with data & formulas.
B Maintenance alert: pick machine → sensor history → PRESS_VIBRATION_ANOMALY → detection → explanation → create Work Order → assign technician → change status → audit trail.
C Logistics congestion: load many-waiting scenario → queue baseline → queue estimate → try new slots → compare waiting time → show assumption limits.
D Copilot: ask OER → verify vs DB → ask possible causes → evidence → ask for non-existent data → no fabrication → unauthorized tool request is refused.
E Executive demo: open public URL → guided tour → KPIs → AI insight → scenario → business impact → technical architecture → developer profile → résumé/contact — all without extra setup.

## 16. Required docs (must match what is really built; label unbuilt features with status)
README, PROJECT_VISION, BUSINESS_RESEARCH, PRODUCT_REQUIREMENTS, SYSTEM_ARCHITECTURE, DOMAIN_MODEL, DATABASE_SCHEMA, DATA_GENERATION, AI_MODELS, MODEL_EVALUATION,
API_DOCUMENTATION, SECURITY, DEPLOYMENT, DEMO_GUIDE, TECHNICAL_CASE_STUDY, BUSINESS_PROPOSAL, IMPLEMENTATION_ROADMAP, TASKS, DECISIONS, KNOWN_LIMITATIONS.

## 17. Definition of done / final report
DoD: frontend, backend, DB consistent, seed/reset, exec dashboard, production AI real, maintenance AI real, copilot grounded, scenario simulator real, business impact with formulas,
tour, responsive, tests pass, model evaluation report, docs complete, README works step-by-step, public demo reachable, case study, résumé summary, email draft, known limitations.
Final Report states: completed / partial / not implemented features, test results, model evaluation results, deployment status, known risks, next steps.
Do not report a task complete without evidence. Resolve non-blocking ambiguity with engineering judgement and log the assumption. Ask the owner first for anything touching
security, real spend, personal data, or production connections.
