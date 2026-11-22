# Project Vision: Digital Mill Lab

> **Independent portfolio and concept demo. Not an official system of any company.** It runs on **synthetic data** about a
> fictional mill ("Demo Palm Mill A"). It uses no internal company data, no company branding and no real system
> connection. Status of every capability is tracked in `docs/portfolio/CAPABILITY_MATRIX.md`; statements below that are
> not yet independently verified are stated as such in the text.

## 1. Vision in one paragraph

Palm oil manufacturing turns a perishable raw material into oil, kernel and by-products through a chain of connected
steps: weighbridge, reception, sterilisation, threshing, digestion, pressing, clarification, storage and dispatch.
Small gains at each step (a fraction of a percentage point of oil extraction, a few hours of avoided downtime, a shorter
truck queue, a lower energy figure per tonne) add up across a season. The vision is a **trustworthy decision layer
that sits beside the systems a plant already has**: it gathers the numbers people already care about into one
consistent view, points to what looks abnormal and why, proposes what to inspect first, and lets a person decide. It is
built so that every number can be traced to its source and every model result is reported as measured, including when a
simple baseline wins.

## 2. Why this domain, and why now

Public information gives dated, general context. It is context only, never a statement about any company's performance
(fact taxonomy: *Verified Public Fact* and *Historical Public Information*).

- Thailand produced a record 21.1 million tonnes of fresh fruit bunches (FFB) in 2025 with a national oil extraction
  rate (OER) of about 18.2 %, and industry capacity utilisation averaged about 48.7 % over 2023 to 2025 (Krungsri
  Research, May 2026).
- At the April 2026 public price quotes the project's researcher used (research notes, kept private), the value of the oil
  extracted from a tonne of FFB is close to the price quoted for the fruit, so the margin depends heavily on extraction
  efficiency, conversion cost and by-product income. Small efficiency gains therefore matter relatively more (our
  arithmetic on dated public quotes; illustrative, not a statement about any company's margin).
- Supply is seasonal. A Surat Thani study found monthly FFB yield peaking in September and lowest in February (about
  2.5 times apart), which makes planning, staffing and truck flow forecasting problems.
- Whether and how any particular operator's palm operations run today is not public, and this project makes no assumption about it.

These facts make palm oil a domain where careful measurement, early warning and clear explanation can be useful. They
do not say anything about the current state of any particular mill or system.

## 3. Opportunities to build on

The framing is deliberate. A working plant already has people, routines and systems that produce results. The
opportunities below are places where a thin, read-only layer could make that existing work easier to see and share. Each
one lists what a real plant would need before any benefit could be claimed (`docs/business/USE_CASES.md`).

| Opportunity | What it could add | Evidence a real plant would need first |
|---|---|---|
| One view for daily decisions | Key KPIs (FFB, OER, KER, downtime, energy per tonne, truck queue) side by side, compared with the previous period, with the team that should look first | Agreed KPI definitions, authorised access to production and laboratory data, a measured baseline of current reporting effort |
| Condition-based maintenance | Trends in vibration, temperature and current on presses, digesters and pumps to rank inspections before an unplanned stop | Real failure and repair history to calibrate any risk score, sensor or historian access (read-only) |
| Truck flow in peak weeks | Waiting-time prediction and simulated slot scheduling against first-come-first-served | Real arrival and exit timestamps from the weighbridge system |
| Energy per tonne | Comparing electricity, steam and water against throughput to spot disproportionate use such as idle running | Reliable sub-metering and biomass fuel records |
| Traceability readiness | Supplier to delivery to batch to CPO lot using a stated mass-balance method, as groundwork for audits (never a certification claim) | Supplier registry data, ticket numbering, the trace method agreed with auditors |
| A copilot grounded in system data | Plain-language questions in Thai or English answered from allow-listed tools, with sources, and a refusal when the data is missing | Authorised documents, role-based permissions, a real question set to evaluate against |

## 4. Principles

1. **Honesty first.** Synthetic data is labelled on every demo page. "Simulated live" says simulation. ROI is an
   illustrative scenario on adjustable assumptions, never a forecast. If a model loses to a naive baseline, the result
   is published as it is.
2. **Evidence over assertion.** A capability is described as working only when a command, test or inspection has
   reproduced it. The capability matrix records which claims are independently verified and which are not.
3. **Human in the loop.** The AI is advisory and read-only. It never controls a machine or sets a process parameter.
   Any change to a business record (for example a work order) needs an explicit human confirmation and leaves an audit
   record.
4. **Baselines before models.** Every model is compared with a naive method on a held-out later period. A simpler
   method that is as good is the better choice.
5. **Explain, do not just score.** Health states come from stated criteria. Anomalies show observed values, normal
   ranges and *possible* contributing factors, never a "proven cause". A risk score is a ranking, not a calibrated
   probability, and says so.
6. **One source of truth.** Every number is computed once, in the Python service; numeric API payloads carry provenance (anomaly objects and ML alert evidence are known gaps, see `docs/KNOWN_LIMITATIONS.md` section 5)
   (`synthetic_actual`, `forecast` or `what_if`). Dashboards, exports and the Copilot show the same figure.
7. **Respect the process.** Mass balance, capacity and steam and energy relations must hold in the generated data. A
   chart must never look good by breaking the engineering.
8. **Secure by default, modest by design.** Read-only first, separated demo and production configuration, rate limiting,
   input validation, safe uploads, an append-only audit trail, no secrets in the repository.
9. **Work with the existing team.** The aim is to listen, learn the real process from the people who run it, and build
   with them. Nothing here assumes that anything is missing or wrong.

## 5. What the project is, and is not

| It is | It is not |
|---|---|
| An independent concept demo and technical portfolio, designed, directed and reviewed by one engineer with AI coding agents working under written ownership rules and an independent verification log (the build plan (kept private), the engineering log (kept private)) | An official system, a product of any company, or endorsed by any company |
| Built on a deterministic synthetic dataset of a fictional palm oil mill | Built on, or validated against, any real plant's data |
| A proposal to collaborate: a 90-day, measurable pilot designed with an existing team (`docs/BUSINESS_PROPOSAL.md`) | A claim that any company has a problem, or a quote with budgets and returns |
| A demonstration of method: leakage-aware evaluation, honest baselines, explainable alerts, human-confirmed workflows | A claim of real-plant accuracy or of a model that has been proven on real equipment |
| Read-only and advisory | Autonomous control of equipment |
| Open about limits (`docs/portfolio/CAPABILITY_MATRIX.md`, section 4) | A finished production platform |

## 6. Scope and maturity

Priority classes (`docs/SPEC.md` section 2): **P0 flagship** (executive control tower, palm-mill production
intelligence, anomaly detection and predictive maintenance, copilot, scenario simulator, business impact), **P1
supporting** (logistics and weighbridge, energy, traceability, maintenance work orders, recommendations with human
approval) and **P2 concepts** (computer-vision grading, plantation yield forecasting, cross-company data platform and
generic inventory or scheduling ideas), which are only ever labelled prototypes.

What exists today, from rows verified by the orchestrator (`CAPABILITY_MATRIX.md`):

- A deterministic synthetic data engine: 120 days, about 1.57 million rows, six linked scenario episodes, mass balance
  checked (CM-01, CM-02).
- A Python service with typed APIs, simulated-role permission checks, rate limiting and a hash-chained audit log
  (CM-03, CM-04); an executive KPI API that matches direct SQL (CM-06); logistics queue-now (CM-08); equipment health
  from explicit criteria (CM-10); a work-order workflow with audit trail (CM-11); an ROI simulator whose arithmetic was
  recomputed by hand (CM-13).
- Eight classical ML models with temporal evaluation against baselines. Several do not beat their baselines and are
  reported that way (CM-15 to CM-19). The press-bearing detector gave about 148 hours of lead time before the rule-based
  critical alarm **on a prescribed synthetic degradation curve** (CM-17).
- A bilingual public site foundation (landing and developer profile verified, CM-33, CM-34).

Verified at the final integration run (2026-11-22 night): the executive control-tower page, the maintenance, equipment and work-order pages, the logistics page, the digital twin, the palm-mill, scenario-simulator and business-impact pages, the Copilot core (tool router, grounding verifier, role checks, safety patterns, retrieval with citations) and the guided tour. They are covered by 20 end-to-end scenario tests (scenarios A to E) and by the full suite (1,139 passed, 2 skipped). Limits: the energy page is partial (agent browser checks only, CM-29b); the Copilot answers about half of fresh paraphrases correctly and asks for clarification in about a third, and its LLM mode has been tested only with a fake provider (CM-30b). **[PENDING VERIFICATION · CM-36: Docker and CI configured, never built or run]**. There is no public deployment (CM-37).

## 7. Who it is for

| Audience | What they should be able to do |
|---|---|
| Executive or managing director | Understand the value and the next step in three to five minutes (guided tour, then the executive view and the business-impact page) |
| Factory, production and maintenance leads | See what is abnormal, the evidence behind it, and walk an alert through to a confirmed work order |
| IT and OT leads | Read the architecture, the read-only integration contracts, the security posture and the known limits |
| Recruiters and technical interviewers | Verify claims: run `make setup`, `make seed`, `make test`, read the model cards and the capability matrix |

## 8. How we will know it is working

For the demo: a visitor can follow one consistent scenario (a screw-press bearing degrading: vibration, bearing
temperature, small oil-loss and OER effect, alert, inspection advice, work order, impact estimate) and every figure
agrees across views. For a real collaboration the success criteria come from a baseline agreed during discovery, and the
go, adjust or stop decision is taken on evidence (`docs/IMPLEMENTATION_ROADMAP.md`).

## 9. Related documents

`docs/BUSINESS_PROPOSAL.md` · `docs/IMPLEMENTATION_ROADMAP.md` · `docs/TECHNICAL_CASE_STUDY.md` ·
`docs/portfolio/CAPABILITY_MATRIX.md` · `docs/SPEC.md` · `docs/DECISIONS.md` · `docs/MODEL_EVALUATION.md` ·
`docs/DATA_GENERATION.md` · the public-facts research (kept private)
