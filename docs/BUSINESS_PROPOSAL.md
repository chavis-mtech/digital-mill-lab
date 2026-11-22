# Business Proposal: a 90-day pilot with the existing team

> **Independent proposal from a job applicant. Not an official company document, not a quotation.** It contains no
> budget, no return and no statement about any company's systems or results, because none of those are known to the
> author. Everything described in sections 3 to 11 is tagged *Proposed Future Capability*: a plan to be shaped together,
> not a finished product. Evidence about the demo is in `docs/portfolio/CAPABILITY_MATRIX.md`; items not yet
> independently verified are stated as such in the text.

## 1. The proposal in brief

Work alongside the target organisation's own production, maintenance, logistics and IT people for **90 days** to build and test one
small, read-only, measurable improvement in the palm oil value chain, starting with the mill. The pilot would:

1. learn how the work is done today and which data already exist (days 1 to 30);
2. build a focused dashboard and, where it earns its place, an AI model on authorised historical data (days 31 to 60);
3. trial it with real users, measure it against a baseline that everyone agreed in advance, and decide on evidence
   whether to scale, adjust or stop (days 61 to 90).

The aim is to add to what the team already does well, not to replace it. The AI is advisory. It does not control
equipment, and any change to a business record needs a person's confirmation.

## 2. Why the applicant is proposing this

The applicant, Chavis Keawrat, is a full-stack developer (public profile README, last updated March 2025) who has built
a payroll and HR system with complex overtime rules tested with PHPUnit, and a real-time point-of-sale system using
Socket.io, and who is applying for a **Technical Project Manager (Software & AI)** role. To show how he would work, he
built an independent concept demo on synthetic data. The demo exists so that every claim below can be checked
(commands, tests, model cards), not so that anyone has to take it on trust. *Project-management and AI experience
beyond this project are not stated in the applicant's public profile; the owner will supply them:* **TODO (owner).**

## 3. Value areas (palm mill first)

Value areas are ordered by how directly they connect to the mill's daily figures. Every benefit statement below is a
*hypothesis to measure*, never a result. "Evidence needed" is what the pilot must collect before any benefit is claimed.

| # | Value area | What it could add | Main KPI (definition in `docs/business/KPI_DEFINITIONS.md`) | Evidence needed |
|---|---|---|---|---|
| V1 | **Production visibility** | One consistent view of FFB received and processed, CPO, OER, KER, throughput, downtime and energy per tonne, with previous-period comparison and the team that should look first | Time to produce the weekly production report; number of figures that disagree between sources | Current reporting steps and time, agreed KPI definitions, laboratory and production data access |
| V2 | **Condition-based maintenance** | Ranking inspections by vibration, temperature and current trends on presses and rotating equipment; a traceable alert to work order loop | Unplanned downtime hours; alert precision (share judged worth inspecting by engineers); lead time against the existing alarm | Sensor or historian access (read-only), maintenance history including failures, equipment code mapping |
| V3 | **Truck flow and fruit freshness** | Waiting-time prediction and simulated slot scheduling in peak weeks | Wait-to-weigh and turnaround (median and 90th percentile); FFB wait-to-process time | Weighbridge exports with arrival and exit timestamps, privacy review for driver and supplier data |
| V4 | **Energy per tonne** | Spotting disproportionate electricity or steam use (idle running, leaks) normalised for load | Electricity and steam per tonne FFB at comparable load | Sub-metering, biomass fuel records |
| V5 | **Traceability readiness** | Mass-balance supplier-to-lot trace and report as groundwork for audits (never a certification claim) | Time to answer a trace query; share of CPO mass attributable to supplier lots | Supplier registry, ticket numbering, trace method agreed with auditors |
| V6 | **A grounded copilot** | Plain-language questions in Thai or English answered from allow-listed tools with sources, and a refusal when data is missing | Time to answer routine questions; answer accuracy on a user-written question set | Authorised documents and data, role permissions, an evaluation set from real users |

The group-wide data opportunities (shared master data and KPI definitions across businesses) are a Year 3 theme
(`docs/IMPLEMENTATION_ROADMAP.md`). They are not part of this pilot.

## 4. What exists today as evidence

The demo is the author's way of showing method before asking for anything. Status from the capability matrix:

| Demonstrates | Status | Matrix row |
|---|---|---|
| A deterministic 120-day synthetic dataset of a fictional mill with mass balance checked and six linked scenario episodes | verified | CM-01, CM-02 |
| Typed Python APIs: executive KPIs equal to direct SQL; logistics queue; equipment health from explicit criteria; work-order workflow with audit trail; ROI arithmetic recomputed by hand | verified | CM-06, CM-08, CM-10, CM-11, CM-13 |
| Eight classical ML models evaluated on a later held-out period against naive baselines. **Several do not beat their baselines** and are reported that way | verified | CM-15 to CM-19 |
| A press-bearing detector that fired about 148 hours before the rule-based critical alarm on a prescribed synthetic degradation curve (says nothing about real bearings) | verified | CM-17 |
| Executive control-tower page; maintenance, equipment and work-order pages; logistics page | Built; covered by 20 end-to-end scenario tests and the full suite (1,139 passed); the executive page was also checked in a browser by the orchestrator | |
| Digital twin, palm-mill, scenario simulator and business-impact screens | Built and covered by end-to-end scenario tests. Energy screen is partial (agent browser checks only); traceability is built and tested in the full suite. **[PENDING VERIFICATION · CM-29b: energy screen only]** | |
| Grounded Copilot with citations and a no-API mode | Built. Evaluator re-run: grounded answers 45 of 45, unauthorised requests refused 23 of 23, prompt injections refused 26 of 26. On 46 fresh paraphrases: 25 correct, 16 clarified, 5 wrong, so it answers about half correctly and clarifies about a third. The LLM mode has been tested only with a fake provider | |
| Public demo URL | https://digital-mill-lab-web.vercel.app (CM-37; free tiers, see docs/DEPLOYMENT.md section 11) | |

The demo's ROI simulator shows illustrative scenarios built on adjustable assumptions. **None of its numbers are claims
about any company.**

## 5. Pilot design: 90 days

### 5.1 Before day 1 (agreements)

A short confidentiality agreement, a named executive sponsor, a named day-to-day contact in operations and a named
contact in IT/OT. The pilot starts with **read-only** access to the smallest useful extract of data, delivered as
files (for example weighbridge, laboratory, production and maintenance exports) before any live connection.

### 5.2 Days 1 to 30: Discovery

| Activity | Output |
|---|---|
| Walk the process and the data trail with production, maintenance, logistics and laboratory staff | Process and data map: systems, owners, update frequency, quality |
| Interview stakeholders about improvement themes they already have in mind (not a list of faults) | Theme summary ranked by the team |
| Inventory the data that already exist and check completeness on a sample | Data-readiness assessment |
| Agree KPI definitions in writing, especially OER and the treatment of stock changes | KPI dictionary signed by data owners |
| Measure the **baseline** for the candidate KPIs from historical data (section 5.6) | Baseline report with seasonality noted |
| Score candidate pilots with the team (section 5.3) and choose one | Pilot proposal, scope, success criteria, go or no-go for the build phase |

*Exit criteria:* sponsor approves one pilot and its baseline; every pilot data source and owner is identified.

### 5.3 Choosing the pilot

Candidates are scored together on the same criteria. No candidate is assumed to win; the table lists what would favour each.

| Candidate | Scope | Favoured when |
|---|---|---|
| A. Production visibility | KPI dictionary, one consolidated daily and weekly view, previous-period comparison, drill-down | The team would like one shared reference for meetings alongside the reports already in use |
| B. Condition monitoring on one equipment family (for example the screw presses) | Read-only trend view, explicit health criteria, advisory ranking, confirmed work-order loop | Vibration or temperature history already exists for those assets and maintenance history is recorded |
| C. Truck flow in peak weeks | Queue view, waiting-time estimate, slot scenario | Weighbridge exports carry reliable timestamps and the peak season is near |

*Criteria:* a measurable KPI with a usable baseline; data availability and quality; integration effort and security
risk; users who want it; a sponsor; small enough to finish in 60 days.

### 5.4 Days 31 to 60: Pilot development

| Activity | Output |
|---|---|
| Write a **read-only integration plan** and start with periodic exports before any automated connection | Integration plan; data pipeline |
| Build the pilot dashboard with the users, weekly demos, changes from feedback | Pilot dashboard |
| Train models on authorised historical data only if the use case needs one. Use a later held-out period and naive baselines, and commit in advance to the decision rule: *adopt a model only if it beats the baseline on the held-out period; otherwise use the simpler method or rule* | Models with model cards, or a documented decision to use rules |
| Check figures with key users against the source systems | Validation report |

*Exit criteria:* key users confirm the figures match the source systems; model results are reported against the
baseline on a held-out period, whatever they are.

### 5.5 Days 61 to 90: Pilot evaluation

| Activity | Output |
|---|---|
| Limited live trial with named users in routine meetings and shifts | Trial log and weekly feedback |
| Measure KPIs against the agreed baseline using the evaluation design below | KPI results |
| Security and reliability review with IT (access, logs, failure behaviour, data retention) | Review report |
| Return assessment from the pilot's own measured data and the company's finance rules | Return assessment (figures come from the company's data, not from this document) |
| Scale-up plan, or a documented decision to adjust or stop | Scale-up plan and go, adjust or stop recommendation |

*Exit criteria:* a go, adjust or stop decision made on evidence; no open high-severity security findings.

### 5.6 Measuring honestly

Palm mills are seasonal, so a before and after comparison on raw averages would mislead. The evaluation design:

- **Baseline:** the longest clean history available (aim for at least one full season), stated with its noise, for
  example the day-to-day spread of OER.
- **Comparison:** compare against the *expected value given conditions* (intake, fruit quality, season) rather than
  against last month; use matched periods where possible; report ranges, not single points.
- **Leading indicators:** where results are slow to appear (for example failures are rare), also track alert precision,
  lead time over the existing alarm and false alerts per week.
- **Ownership:** each KPI has a named data owner, and the figures are reproduced from source records by someone other
  than the builder.
- **Targets:** set **after** the baseline is measured and agreed. This proposal sets none.

| Pilot KPI | Definition | Baseline method | Notes |
|---|---|---|---|
| OER (process basis) | CPO produced / FFB processed, ratio of sums | Trailing history with seasonal expectation | Diagnostic, not an operator score. Day-to-day noise is normal (about 0.25 pp in the synthetic data) |
| Unplanned downtime | Hours of unplanned stops per week | Maintenance records | Starved hours are not downtime |
| Truck wait-to-weigh | Median and 90th percentile, completed trucks | Weighbridge timestamps | Censored trucks counted separately |
| Energy per tonne FFB | Electricity and steam divided by FFB processed, at comparable load | Meter readings | Normalise for load before calling a rise abnormal |
| Report effort | Hours per week spent compiling production figures | Staff estimate then timesheet sample | A cost avoided only if time is freed for other work |
| Alert precision | Share of alerts that engineers judge worth inspecting | Engineer review log | For condition monitoring |
| Model skill | MAE or recall against baseline on held-out period | Naive baseline | Reported whether or not the model wins |
| Adoption | Weekly users and use in routine meetings | Usage logs | Adoption is a result, not an assumption |

## 6. Roles

| Role | Who | Responsibility | Proposed time commitment (to be agreed) |
|---|---|---|---|
| Executive sponsor | Company | Approves scope, removes blockers, owns the go, adjust or stop decision | A short check-in every two weeks |
| Technical Project Manager | Applicant (if hired) | Scope, plan, risks, stakeholder cadence, evidence and reporting | Full time for the pilot |
| Data and ML engineer | Applicant or a teammate | Data pipeline, KPI computation, models, evaluation | As needed in days 31 to 60 |
| Full-stack developer | Applicant or a teammate | Dashboard, read-only APIs, tests | As needed in days 31 to 75 |
| Production and maintenance representatives | Company | Process knowledge, KPI definitions, validation of figures, work-order loop | A few hours per week as key users |
| Logistics and laboratory contacts | Company | Weighbridge and laboratory data, definitions | As the chosen pilot needs |
| IT and OT | Company | Access, environment, security review, integration plan | Review points in each phase |
| Finance | Company | Return assessment method | One session in days 61 to 90 |

The applicant could cover several of the technical roles in the early weeks. The roadmap lists the roles a larger
effort would need (`docs/IMPLEMENTATION_ROADMAP.md`).

## 7. Deliverables

| Phase | Deliverables |
|---|---|
| Discovery | Process and data map; stakeholder theme summary; data-readiness assessment; signed KPI dictionary; baseline report; pilot selection and proposal |
| Pilot development | Read-only integration plan; data pipeline; pilot dashboard; models with model cards or a documented rules decision; validation report with users |
| Evaluation | Trial report; KPI results against the baseline; security and reliability review; return assessment; scale-up plan and recommendation |
| Throughout | Weekly status note; risk register; decision log; the source code and documentation, so the company's team can run and extend the work |

## 8. Dependencies

1. A sponsor and named contacts in operations and in IT/OT.
2. Authorised, read-only access to historical data, delivered as exports first. The size of the extract is the
   company's choice.
3. A confidentiality agreement and a clear rule about where data may be processed (company environment preferred).
4. Time from key users, even if small, because the figures must be checked by the people who know the process.
5. A place to run the pilot (a company workstation or server, or an isolated company cloud account) agreed with IT.
6. KPI definitions agreed in writing before the baseline is measured.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Data quality or completeness lower than hoped | Assess a sample before choosing the pilot; choose the candidate whose data are good enough |
| Models do not beat a simple baseline (this happened for several models in the demo) | Decide the rule in advance; use the simpler method; report truthfully |
| Seasonal effects hide or fake a result | Compare against expected-given-conditions; use leading indicators; extend the trial if needed |
| Integration takes longer than planned | Start with periodic exports; keep the integration read-only; defer live connections to the next phase |
| Low adoption | Co-design with key users; weekly changes from feedback; measure use honestly |
| Alert fatigue from false positives | Track alert precision from day one; raise alerts only for sustained conditions |
| Over-reliance on an AI suggestion | Advisory only; show evidence and normal ranges; human confirmation and audit trail for every record change |
| OT cyber risk from new connections | Read-only; no write path to controllers; historian replica or DMZ if a live feed is ever needed; never expose controllers to the internet |
| Privacy of driver, supplier or staff data | Data minimisation; aggregate or pseudonymise; privacy review; follow the company's PDPA process |
| Expectations drift beyond scope | Written scope and success criteria signed by the sponsor in discovery |
| The demo is mistaken for a company system | The demo is labelled independent and synthetic on every page; the pilot would use the company's own environment and names |

## 10. Data, security and OT considerations

- **Read-only first.** The service reads data. It never writes to controllers, historians or business systems in the pilot.
  Integration contracts (ERP/CMMS, MES, historian, OPC UA, MQTT, weighbridge, LIMS, GPS, accounting) are defined as
  *future, read-only* contracts (`docs/architecture/INTEGRATION_CONTRACTS.md`); none exists as a live connection.
- **Human confirmation.** The demo shows the intended pattern: a recommendation never changes a record on its own; a
  person confirms, and an append-only hash-chained audit entry is written (CM-11, CM-04).
- **Least data.** Only the fields the chosen KPI needs; no personal data unless the pilot requires it and the company
  approves it.
- **Environment.** The company decides where data live. Configuration for demo and production is kept apart; secrets
  come from the environment, never from the repository.
- **Access control.** The demo's roles are *simulated viewpoints*, not authentication. A real deployment would use the
  company's identity provider and keep the permission layer (ADR-007).
- **Model governance.** Each model has a model card with limits; performance is monitored against its baseline; a model
  that stops beating the baseline is retired.
- **Known limits of the demo's own controls:** in-process rate limiting, tamper-evident (not tamper-proof) audit chain,
  no penetration test yet. See the matrix (CM-04).

## 11. What the pilot would need from the company

A checklist for the first conversation:

- [ ] A sponsor and a named operations contact and IT/OT contact.
- [ ] Agreement on confidentiality and where data may be processed.
- [ ] A small read-only extract: weighbridge, laboratory, production and maintenance records for a stated period.
- [ ] A description of existing reports and meetings the pilot should fit into.
- [ ] A few hours per week from key users during days 31 to 90.
- [ ] An IT/OT contact for the security review.
- [ ] The company's own method for assessing returns and approving any later budget.

## 12. Success criteria

The pilot is successful if, by day 90:

1. the sponsor and the users can see, in the company's own data, what changed against the agreed baseline;
2. figures in the pilot match the source systems when checked by someone other than the builder;
3. model results are reported against baselines on a held-out period and the decision to use or not use each model
   follows the pre-agreed rule;
4. there is no open high-severity security finding;
5. the team can make a go, adjust or stop decision from evidence, and the work is documented well enough for the
   company's own people to run it.

"Stop" is a valid outcome. A pilot that shows a use case is not worth scaling has done its job.

## 13. Cost and commercial terms

Not included. No budget, price or return is stated here because none can be responsibly estimated before discovery. After
discovery, effort would be expressed as role-months by phase, infrastructure needs from the integration plan, and any
return from the company's own measured data and finance rules. Any later investment would go through the company's own
approval process.

## 14. Next step

A conversation of 30 to 45 minutes to listen first: which of the value areas is closest to what the team is already
thinking about, what a first extract might look like, and who should be in the room. The author can walk through the
demo and its evidence in the same meeting.

*Contact and links:* GitHub `https://github.com/chavis-mtech` (applicant's public profile) · demo link
https://digital-mill-lab-web.vercel.app · résumé: attached separately.
