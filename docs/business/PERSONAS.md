# Stakeholder Personas

> Task DML-005. Owner: researcher. Independent concept demo. **These are generic role archetypes** written from common industrial practice and the SPEC audience list; they are not descriptions of any real person or employee of any company and carry no internal knowledge (category: Engineering Assumption, confidence low). Use them to decide what each audience must see, in what order, and in which words.

## 1. The seven audiences and what they share

Audiences (SPEC section 2): Executive/MD, Factory Manager, Production Manager, Maintenance Engineer, IT Manager, HR/Recruiter, Technical Interviewer. The first five judge business and operational value; the last two judge the applicant. All seven must be able to reach what they need from the public demo without signing up.

**Shared needs.** Plain statement of what the project is (independent concept, synthetic data, advisory only); the "Synthetic Data" badge on every demo page; a path that takes 3-5 minutes for the executive and deeper links for engineers; evidence for every claim; respectful framing ("opportunity to build on", never "your systems are bad").

**Mapping to the eight simulated roles** (SPEC section 10; roles are viewpoints, not authentication):

| Persona | Simulated role to preselect | Suggested permissions in the demo |
|---|---|---|
| Executive / MD | Executive | Read executive, business impact, scenarios, copilot (read-only tools) |
| Factory Manager | Factory Manager | Above plus approve AI recommendations, create/assign work orders |
| Production Manager | Production Engineer | Palm mill analytics, process, scenarios, copilot production tools; no work-order approval |
| Maintenance Engineer | Maintenance Engineer | Equipment, health, work orders (review, update records), copilot maintenance tools |
| IT Manager | System Administrator | Read docs/architecture/security, audit log, role matrix; reset own demo session |
| HR / Recruiter | Public Demo Viewer | Landing, tour, developer, contact, read-only demo |
| Technical Interviewer | AI Analyst (and Public Demo Viewer) | Model cards, evaluation, copilot with tool trace, API docs; no record changes |
| (also in the role list) | Logistics Officer | Logistics and weighbridge views and actions |

## 2. Personas

### P-1 Executive / Managing Director
- **Archetype:** senior leader of a diversified group deciding where digital and AI investment goes; time-poor; non-technical.
- **Goals:** understand in 3-5 minutes whether the idea has business value; decide whether to ask for a conversation or a pilot.
- **Questions:** What is abnormal today? How much does it cost? Who should look first? What do I decide? What would this need from us? What does it cost and what is the evidence?
- **Needs to see:** the guided tour ("ทดลองชมระบบใน 5 นาที") ending in the executive dashboard; one AI insight summary; a scenario with a clear value statement; the ROI disclaimer ("Illustrative business scenario based on adjustable assumptions, not verified financial results of any company."); a roadmap with phases and no invented budgets.
- **KPIs they own:** OER, CPO produced, estimated production cost, downtime, energy per tonne, active critical alerts (KPI-04, 03, 11, 09, 10, 12).
- **Concerns / objections:** "Is this real data?" (No, synthetic and labelled), "Will it replace our people?" (No, advisory), "What does it cost to start?" (a pilot proposal, not a quote), "Is it secure?".
- **Demo path:** `/` -> tour -> `/demo/executive` -> `/demo/business-impact` -> `/implementation-roadmap` -> `/contact`.
- **Success criteria:** can state the value and the next step in one sentence; asks for a meeting.
- **Copy notes:** short Thai-first sentences, no jargon, numbers with provenance badges, "opportunity" language.

### P-2 Factory Manager
- **Archetype:** accountable for plant output, cost, safety and people on site.
- **Goals:** see the whole plant status, know what needs a decision, protect throughput and quality.
- **Questions:** Why did OER drop today? Which machine needs attention first? What is the effect on today's output? Should I approve this work order?
- **Needs to see:** abnormal items ranked with business effect; the alert -> work order -> status loop; scenario of downtime impact; queue and supply situation.
- **KPIs they own:** throughput, availability, plant downtime, queue time, estimated cost, alerts.
- **Concerns:** alert noise, false positives, extra paperwork, accountability for AI suggestions.
- **Demo path:** `/demo/executive` -> `/demo/maintenance` -> `/demo/maintenance/work-orders` -> `/demo/logistics`.
- **Success criteria:** can create and track a work order from an AI alert and see its production impact.
- **Copy notes:** evidence first, recommendation second, human confirmation explicit.

### P-3 Production Manager / Production Engineer
- **Archetype:** runs the process line daily; knows sterilizer cycles, digesters, presses and clarification by feel.
- **Goals:** hold OER and quality, reduce oil loss, steady feed.
- **Questions:** What changed in steam, digester temperature or press load? Is the dip from unripe fruit, delay, or the press? What happens to OER if I extend the cycle?
- **Needs to see:** process flow with live sensor state, OER trend with expected band, contributing factors (never "proven cause"), loss breakdown, scenario analysis with formulas.
- **KPIs they own:** OER, KER, throughput, oil loss, FFA, steam per tonne.
- **Concerns:** physically wrong simulation, charts that look nice but break mass balance, black-box models.
- **Demo path:** `/demo/palm-mill` -> `/demo/palm-mill/process` -> `/demo/palm-mill/analytics` -> `/demo/palm-mill/ai-insights` -> `/demo/scenarios`.
- **Success criteria:** the numbers obey the process logic (steam, throughput, losses agree); can find the evidence behind an anomaly.
- **Copy notes:** use the right process words (sterilization, digestion, pressing, clarification), show units and normal ranges.

### P-4 Maintenance Engineer
- **Archetype:** responsible for reliability of presses, boilers, fans, pumps, centrifuges; practical about sensors and failure modes.
- **Goals:** inspect before failure, plan work, keep a clean maintenance record.
- **Questions:** Which sensor triggered? Is this vibration level in a bad ISO zone? How long was the trend? What is the risk score really? What should I inspect?
- **Needs to see:** equipment list with computed health state and criteria, sensor history with thresholds, contributing sensors, recommendation (bearing, lubrication, alignment, sensor check), work-order trail, limits of the risk score.
- **KPIs they own:** availability, MTBF, MTTR, PM compliance, work-order backlog.
- **Concerns:** alerts without explanation, uncalibrated scores presented as probabilities, ignoring sensor faults.
- **Demo path:** `/demo/maintenance` -> `/demo/maintenance/equipment` -> scenario PRESS_VIBRATION_ANOMALY -> `/demo/maintenance/work-orders`.
- **Success criteria:** can reproduce why a state was assigned from the data and thresholds shown.
- **Copy notes:** "advisory", "inspect before continued use", "not a calibrated probability".

### P-5 IT Manager
- **Archetype:** owns systems, networks, integration and security for the group; cautious about new tools touching production.
- **Goals:** judge integration effort, security posture, maintainability and vendor risk.
- **Questions:** What does it connect to? How is data secured? Is it read-only? Where does it run? What are the APIs? What is missing for production?
- **Needs to see:** architecture page, integration contracts (ERP, MES, SCADA, PLC, OPC UA, MQTT, weighbridge, LIMS, GPS - all labelled *future contracts*), security page (rate limiting, input validation, safe uploads, audit, env-based secrets, demo-vs-prod separation), API docs, deployment notes, known limitations.
- **Concerns:** shadow IT, OT security, data residency, support burden, vendor lock-in.
- **Demo path:** `/technical-architecture` -> `/docs/architecture` -> `/docs/security` -> `/docs/integration` -> `/docs/data-model`.
- **Success criteria:** sees a credible, honest integration path with phased, read-only first steps.
- **Copy notes:** precise, status chips (implemented / partial / prototype / planned), no overclaiming.

### P-6 HR / Recruiter
- **Archetype:** screens for fit and credibility for a Technical Project Manager (Software & AI) role; non-specialist in palm oil.
- **Goals:** understand who the applicant is, what was built, whether claims are credible, how to contact.
- **Questions:** What is this? Did the person build it? What are the skills and leadership evidence? Is it honest about what is real?
- **Needs to see:** landing page with clear "independent concept" statement; developer page with only facts from the applicant's own README; the one-page executive summary; contact/resume links; the project's honesty features (badges, known limitations).
- **Concerns:** exaggerated claims, invented credentials, unclear independence from the company.
- **Demo path:** `/` -> `/about-project` -> `/developer` -> `/contact`.
- **Success criteria:** can summarise the applicant and the project in two sentences and knows how to follow up.
- **Copy notes:** modest tone, placeholders for anything not in the applicant's own README (never invented).

### P-7 Technical Interviewer
- **Archetype:** senior engineer or technical leader who will probe architecture, data engineering and AI quality.
- **Goals:** verify that the system really works, the AI is evaluated honestly, and the engineering practice is sound.
- **Questions:** How is the data generated and kept consistent? Is the model leakage-free and compared with a baseline? How does the copilot avoid hallucination and injection? Which tests pass? What are the trade-offs and known limits?
- **Needs to see:** model cards, temporal evaluation with naive baselines, scenario-based anomaly metrics, copilot evaluation (grounding, tool-call success, unsupported claims, citation accuracy, access control), tests and CI evidence, ADRs, reproducible seed/run commands, honest known limitations.
- **Concerns:** fake accuracy, hardcoded numbers, decorative AI, untested claims.
- **Demo path:** `/docs/ai-methodology` -> `/demo/palm-mill/ai-insights` -> `/demo/ai-copilot` (tool trace) -> `/docs/architecture` -> repository.
- **Success criteria:** can run `make setup`, `make seed`, `make dev`, `make test` and reproduce numbers; sees a model losing to a baseline reported truthfully if that happens.
- **Copy notes:** precise and verifiable; link every claim to a test, a file, or a result.

## 3. Consolidated needs matrix

| Need | P-1 Exec | P-2 FM | P-3 PM | P-4 ME | P-5 IT | P-6 HR | P-7 TI |
|---|---|---|---|---|---|---|---|
| Guided 5-minute tour | must | should | could | could | could | should | could |
| Provenance badges on numbers | must | must | must | must | must | should | must |
| Computed explanations (evidence) | should | must | must | must | should | could | must |
| Work-order loop with approval | could | must | could | must | could | could | should |
| Scenario / ROI with visible formulas | must | should | must | could | could | could | should |
| Architecture, security, integration contracts | could | could | could | could | must | should | must |
| Model cards and evaluation | could | could | should | should | should | could | must |
| Developer profile and contact | should | could | could | could | could | must | should |
| Honest limits and status chips | must | must | must | must | must | must | must |

## 4. Language and tone rules

- Thai is the default UI language (cookie-based toggle to English); keep Thai terms for UI copy (for example "ทดลองชมระบบใน 5 นาที") and technical terms in English where plant staff use them.
- Never write that the company's systems are poor, missing, or inefficient. Prefer: "opportunities to build on existing practice".
- Do not name or imply any real individual at the company. No internal terminology that was not found in public sources.
- Where a persona would be unsure, show provenance and a link to the definition rather than a long explanation.
