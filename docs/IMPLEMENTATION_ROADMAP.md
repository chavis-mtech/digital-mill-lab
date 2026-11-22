# Implementation Roadmap: 30 / 60 / 90 days and Years 1 to 3

> **Independent proposal. Not an official company plan.** Every item is tagged *Proposed Future Capability*. There are
> **no budgets, returns or company facts** in this document; dates are relative to a start day chosen together with the
> company. It mirrors the public site's roadmap page (`/implementation-roadmap`, source
> `apps/web/content/public/roadmap.ts`); if the two ever differ, the site copy and this file must be reconciled before
> either is sent. Items not yet independently verified are stated as such in the text
> (`docs/portfolio/CAPABILITY_MATRIX.md`).

## 1. How to read this roadmap

- The framing is **opportunity to build on**. A working organisation already has systems, people and routines; the
  roadmap lists what could be added next to them, in an order where each step earns the right to the next one.
- Every phase has the same parts: goal, deliverables, roles, dependencies, risks with mitigations, and success criteria
  that are **measured against a baseline agreed in discovery**.
- Gates between phases are decisions taken on evidence. Stopping or adjusting at a gate is a legitimate outcome.

## 2. Overview

| Phase | Horizon | Theme | Gate at the end |
|---|---|---|---|
| Discovery | Days 1 to 30 | Understand systems, people, data and IT/OT limits; agree the baseline; choose one pilot | G1: sponsor approves one pilot and its baseline |
| Pilot development | Days 31 to 60 | Build the dashboard and models on authorised historical data; read-only integration plan | G2: key users confirm figures match the sources; model results reported against baselines |
| Pilot evaluation | Days 61 to 90 | Limited live trial; measure against the baseline; security and reliability review; scale-up plan | G3: go, adjust or stop, decided on evidence |
| Year 1 | Operational digitalisation | Scale what the pilot proved; shared data platform; standard KPI definitions | G4: core KPIs come from one verifiable source and are used in routine meetings |
| Year 2 | AI and industrial IoT | Condition monitoring where needed; models calibrated on real data; permission-controlled copilot | G5: models reported on real data against baselines; AI never controls machines |
| Year 3 | Group-wide intelligent operations | Reuse proven patterns across suitable business units under shared standards | G6: a pattern reused in a second business unit; an internal team can run the platform |

```mermaid
flowchart LR
  D[Days 1-30<br/>Discovery] -->|G1 baseline + pilot chosen| P[Days 31-60<br/>Pilot build]
  P -->|G2 figures validated| E[Days 61-90<br/>Evaluation]
  E -->|G3 go / adjust / stop| Y1[Year 1<br/>Operational<br/>digitalisation]
  Y1 -->|G4 one verifiable KPI source| Y2[Year 2<br/>AI + industrial IoT]
  Y2 -->|G5 models proven on real data| Y3[Year 3<br/>Group-wide<br/>operations]
  Y1 -.shared data platform.-> Y2
  Y2 -.model catalogue + MLOps.-> Y3
```

## 3. Days 1 to 30: Discovery

**Goal.** Understand existing systems, stakeholders, available data and IT/OT constraints, then choose one measurable pilot.

| Part | Content |
|---|---|
| Activities | Walk the process and data trail; interview stakeholders about improvement themes they already hold; inventory data sources and check a sample; agree KPI definitions in writing; measure baselines; score candidate pilots together |
| Deliverables | Map of current systems and data sources; stakeholder interview summary and improvement themes; agreed KPI baseline; pilot selection criteria and pilot proposal |
| Roles | Technical Project Manager; production and maintenance representatives; IT/OT; executive sponsor |
| Dependencies | Access to stakeholders and the site; a data confidentiality agreement |
| Risks and mitigations | Data quality or completeness lower than expected: assess data quality before choosing the pilot. Misaligned expectations: written scope and success criteria signed off jointly |
| Success criteria | Sponsor approves the pilot and the baseline; every pilot data source and owner identified |

## 4. Days 31 to 60: Pilot development

**Goal.** Build the dashboard and models on authorised historical data, with a read-only integration plan.

| Part | Content |
|---|---|
| Activities | Integration plan; periodic exports into a pipeline; dashboard built with users in weekly cycles; models only where the use case needs one, evaluated on a later held-out period against naive baselines; figures checked against sources |
| Deliverables | Integration plan (read-only towards OT); pilot dashboard; models on historical data with baseline comparison; validation report with users |
| Roles | Technical Project Manager; data and ML engineer; full-stack developer; key users from operations |
| Dependencies | Discovery outputs; access to historical data |
| Risks and mitigations | Models do not beat the baseline: report it truthfully and use the simpler baseline or rules. Integration takes longer than planned: start with periodic exports before automated connections |
| Success criteria | Key users confirm figures match the source systems; model results reported against the baseline on a held-out period |

## 5. Days 61 to 90: Pilot evaluation

**Goal.** Run a limited live trial, collect feedback, measure KPIs against the baseline and prepare a scale-up plan.

| Part | Content |
|---|---|
| Activities | Named users use the pilot in routine meetings; weekly feedback and changes; KPI measurement with the pre-agreed evaluation design; security and reliability review; return assessment using the company's own method |
| Deliverables | Trial report; KPI results against the baseline; security and reliability review; return assessment from real data; scale-up plan |
| Roles | Technical Project Manager; key users; IT security; finance (for the return assessment) |
| Dependencies | A validated pilot; user availability |
| Risks and mitigations | Results unclear over a short period: define leading indicators and extend the trial if needed. Low user adoption: weekly feedback-driven changes and co-design with users |
| Success criteria | A go, adjust or stop decision made on evidence; no open high-severity security findings |

The detailed 90-day pilot design (candidate pilots, KPI table, evaluation design, roles and commitments) is in
`docs/BUSINESS_PROPOSAL.md`, sections 5 to 12.

## 6. Year 1: Operational digitalisation

**Goal.** Scale what the pilot proved, build a shared data platform and standard KPI definitions.

| Part | Content |
|---|---|
| Deliverables | Shared production data platform; executive and floor dashboards; work-order flow connected to existing systems; data governance guidelines |
| Roles | Data platform team; application team; key users per department; a data steward for KPI definitions |
| Dependencies | Pilot evaluation; budget approval through the company's own process |
| Risks and mitigations | Scaling faster than data readiness: expand area by area against data-readiness criteria |
| Success criteria | Core KPIs come from one verifiable source; dashboards used in routine meetings |
| Entry criteria | G3 decision is "go" or "adjust"; owners named for each data source |

## 7. Year 2: AI and industrial IoT

**Goal.** Add needed condition monitoring, forecasting models calibrated on real data and a permission-controlled AI copilot.

| Part | Content |
|---|---|
| Deliverables | Read-only historian or OPC UA connection; models with model cards and performance monitoring; AI copilot with citations |
| Roles | ML engineer; OT engineer; cybersecurity team; a reliability engineer from maintenance |
| Dependencies | Year-1 data platform; IT/OT network segmentation |
| Risks and mitigations | Cyber risk from OT connectivity: read-only through a DMZ or historian replica; never expose controllers to the internet. Calibrating on too little failure history: report uncertainty, keep risk scores as rankings until calibrated |
| Success criteria | Models reported on real data against baselines; AI never controls machines and every record change is human-confirmed |
| Entry criteria | G4 passed; data governance in place; a real question set and permission model for the copilot |

## 8. Year 3: Group-wide intelligent operations

**Goal.** Reuse proven patterns across suitable business units with shared data standards and governance.

| Part | Content |
|---|---|
| Deliverables | Group-level data and API standards; model catalogue and MLOps process; internal centre of excellence |
| Roles | Data and digital leadership; central platform team; business-unit representatives |
| Dependencies | Proven results from years 1 and 2 |
| Risks and mitigations | Business units have different needs: shared core plus business-specific modules |
| Success criteria | At least one pattern reused in a second business unit; an internal team able to run the platform |
| Entry criteria | G5 passed; an internal owner for the platform |

## 9. Dependencies between phases

| Needs | From | Why it cannot be skipped |
|---|---|---|
| Agreed KPI definitions and baseline | Discovery | Without them no result can be measured later |
| Authorised historical data | Discovery, then pilot | Models and validation need it |
| Pilot evaluation evidence | Pilot evaluation | Year-1 investment is decided on it |
| One verifiable KPI source (data platform) | Year 1 | Year-2 models and the copilot read from it |
| IT/OT segmentation and read-only access pattern | Year 1 into Year 2 | Condition monitoring must not add risk to controllers |
| Model cards, monitoring, baselines | Pilot, formalised in Year 2 | Without them a model cannot be trusted or retired |
| Real failure and repair history | Year 2 | Needed to calibrate any risk score |
| Shared standards and an internal platform team | Year 2 into Year 3 | Reuse across units needs an owner |

## 10. Estimated team roles by horizon

Indicative only. Replace after discovery. Roles describe skills, not people; one person may cover several early on.

| Horizon | Builder roles | Company-side roles | Indicative builder headcount (planning assumption) |
|---|---|---|---|
| Days 1 to 30 | Technical Project Manager | Production and maintenance representatives, IT/OT, executive sponsor | 1 |
| Days 31 to 60 | Technical Project Manager, data and ML engineer, full-stack developer | Key users from operations, IT/OT contact | 2 to 3 |
| Days 61 to 90 | Technical Project Manager, plus builders as needed | Key users, IT security, finance | 2 to 3 |
| Year 1 | Data platform team, application team | Key users per department, data steward, IT | 3 to 6 |
| Year 2 | ML engineer, OT engineer, security specialist, application developers | Reliability and maintenance engineers, cybersecurity, key users | 4 to 8 |
| Year 3 | Central platform team, data and digital leadership | Business-unit representatives | 5 to 10 (growing share from inside the company) |

The headcounts are a rough planning range, not a quote and not a statement about the company's current staffing.

## 11. Cross-cutting tracks

| Track | Practice throughout |
|---|---|
| Security and OT | Read-only first; no write path to controllers; role-based access; append-only audit; secrets from the environment; security review at each gate |
| Data governance | Named owners, KPI dictionary, quality checks, minimum personal data, privacy review under the company's PDPA process |
| Model governance | Model cards, baselines, held-out evaluation, monitoring, a rule for retiring a model that stops beating its baseline |
| Change management | Co-design with users, weekly demos, training before each rollout, honest reporting of results |
| Documentation | Architecture decisions recorded (ADRs), runnable commands, known limitations kept current |

## 12. Cross-phase risks

| Risk | Where it bites | Mitigation |
|---|---|---|
| Expectations exceed what data support | All phases | Evidence at every gate; label forecasts, what-ifs and synthetic data clearly |
| Dependence on one person | Pilot and Year 1 | Documentation, tests, pairing with the company's own engineers from the start |
| Funding or priority shifts | Year 1 onward | Each phase delivers something usable on its own; gates allow a clean stop |
| Over-automation | Year 2 | AI remains advisory; human confirmation; audit trail |
| Data drift, new equipment or process changes | Year 2 onward | Monitoring against baselines; scheduled model review |

## 13. Groundwork already in the demo

The independent demo gives the roadmap some reusable patterns to start from. These are examples of method, not
components of any company system.

| Pattern | Evidence | Status |
|---|---|---|
| Deterministic, validated synthetic dataset for rehearsing pipelines safely | 120 days, 58 validation checks, checksum reproducible | verified (CM-01, CM-02) |
| KPI service whose outputs equal direct SQL | Orchestrator cross-check on a 7-day window | verified (CM-06) |
| Explicit health criteria and a confirmed work-order loop with audit | Live API check | verified (CM-10, CM-11) |
| Temporal ML evaluation against baselines, including losses | Reproduced from a clean database | verified (CM-15 to CM-19) |
| Illustrative ROI with no double counting | Recomputed by hand | verified (CM-13) |
| Executive, maintenance and logistics screens; Copilot core | Built; covered by 20 end-to-end scenario tests and the full suite (1,139 passed) | Verified; the Copilot answers about half of fresh paraphrases correctly |
| Other screens, Copilot evaluation and page, guided tour | Digital twin, palm-mill, scenario and business-impact pages built; energy page partial; Copilot evaluation re-run; tour covered by the end-to-end tests | Energy page partial; Copilot LLM mode tested only with a fake provider |
| Container build and CI | Configured, never built or run | **[PENDING VERIFICATION · CM-36: Docker build and GitHub Actions run not yet performed]** |

## 14. What is not in this roadmap

No budget, price, internal rate of return, savings figure, staffing claim or date tied to a company calendar. No claim that
any company lacks a system or has a problem. No promise of accuracy on real data. These come from discovery and from the
company's own decision process.
