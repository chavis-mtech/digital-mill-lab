# Résumé project entry: Digital Mill Lab

> **DRAFT for the owner.** Built from the rows of `docs/portfolio/CAPABILITY_MATRIX.md` (round-2 status, 2026-11-22). Developer facts come only from the applicant's own public README (github.com/chavis-mtech, last updated March 2025). Nothing here invents a role, employer, duration, metric, certificate or outcome. Anything the README does not say is a **TODO** in section 4.

## 1. Entry (copy into the résumé)

**Project:** Digital Mill Lab: an independent AI and industrial-analytics concept demo for palm oil manufacturing (synthetic data; not an official system of any company)

**Role:** Author and technical lead of an independent portfolio project (AI-assisted development with a written specification, ownership rules and an independent verification log). *Owner to confirm this wording and the share of hands-on coding before use:* **TODO (owner).**

**Period:** **TODO (owner): start and end dates** (the repository notes are dated November 2026; no duration is claimed here).

**Stack:** Python 3.12 (FastAPI, SQLAlchemy 2, Alembic, scikit-learn), SQLite with a PostgreSQL-compatible schema (PostgreSQL not run live), TypeScript and Next.js (public site), pytest, Playwright, ruff.

**Description:** Designed, directed and verified (with AI coding agents) the data engine, typed APIs, ML evaluation and business-impact simulator of a concept platform that shows how operational data from a palm oil mill could be turned into consistent KPIs, equipment-health insight, human-confirmed maintenance workflows and a transparent business case. It runs on a deterministic synthetic dataset of a fictional mill, labels every number by provenance, keeps the AI advisory and read-only, and reports model results as measured, including where simple baselines win.

**Highlights (each backed by a verified capability-matrix row):**

- Built a **deterministic synthetic-data engine** for a fictional palm oil mill (120 days, about 1.57 million rows, six linked scenario episodes) with **58 automated consistency checks** covering mass balance, capacity limits and referential integrity; the same seed reproduces an identical content checksum. *(CM-01, CM-02)*
- **Evaluated eight scikit-learn models** on a temporal hold-out against naive baselines and published the results as measured, including the OER, energy and arrival forecasts that **did not beat** their baselines; a press-bearing anomaly detector flagged a prescribed synthetic degradation about **148 hours before** the rule-based critical alarm. *(CM-15 to CM-19)*
- Designed a **typed FastAPI service** with KPI endpoints that match direct SQL, equipment health from explicit criteria, and a **work-order workflow that needs human confirmation and writes a hash-chained audit trail**, protected by simulated-role permissions and rate limiting, with an automated suite of **1,139 passing Python tests** (2 skipped), **75 web unit tests** and **20 browser end-to-end scenario tests**. *(CM-04, CM-06, CM-10, CM-11, CM-35)*
- Built an **illustrative ROI simulator** (four cases, no double counting between OER uplift and recovered downtime), recomputed by hand against the API, and recalibrated unrealistic default assumptions after review so the headline stayed credible. *(CM-13)*
- Defined the architecture and delivery process: **17 architecture decision records**, a one-writer-per-path ownership model and an evidence rule under which key status claims were independently re-run (seed checksum, KPIs against SQL, model retraining, ROI by hand, full test suite, end-to-end scenarios) before they were reported. *(CM-38; `docs/DECISIONS.md`, the engineering log (kept private))*

*Shorter version for a one-line résumé slot:* Independent AI-for-manufacturing concept demo (palm oil): deterministic synthetic-data engine with 58 consistency checks, typed FastAPI service with human-confirmed work orders and audit trail, eight ML models evaluated honestly against baselines.

## 2. Round-2 status of candidate bullets (usable only where marked "use")

| Candidate bullet | Matrix row | Round-2 status |
|---|---|---|
| Built an interactive executive control tower with 12 KPIs, alerts and an AI insight summary | CM-24 | Use: verified by an end-to-end scenario test and an orchestrator browser check |
| Built a digital-twin-lite process view that stays consistent with sensor trends, KPIs, alerts and the maintenance view | CM-25 | Use: built; covered by the scenario-A end-to-end test |
| Built production, analytics, scenario simulator and business-impact screens | CM-26, CM-27 | Use: built and covered by the scenario-A end-to-end test |
| Built maintenance, equipment and work-order screens with a human-confirmed work-order loop in the browser | CM-28 | Use: covered by the scenario-B end-to-end test |
| Built a logistics page (queue, waiting time, prediction, slot simulation) | CM-29a | Use with the caveat that the slot-simulation baseline is not calibrated (CM-09) |
| Built energy and traceability views | CM-29b | Do not use yet: energy page partial; traceability is built and tested in the suite |
| Built an industrial operations **Copilot** with allow-listed tools, role checks, a grounding verifier, retrieval with citations, a deterministic mode and an evaluation harness | CM-30a, CM-30b | Use with caveats: evaluation re-run (grounded 45 of 45; unauthorised refused 23 of 23; injections refused 26 of 26); it answers about half of fresh paraphrases correctly; the LLM mode has been tested only with a fake provider |
| Built a **7-step guided executive tour** | CM-32 | Use: the tour is covered by end-to-end tests |
| Eight **model cards** and a documented **leakage audit** with causality tests | CM-21, CM-22 | Use: leakage tests are in the full suite run |
| Containerised with Docker (images built and smoke-tested in CI) and automated with GitHub Actions CI | CM-36 | Usable, with this precision: images were built and tested on GitHub Actions, not deployed |
| End-to-end acceptance tests (Playwright) for five scenarios | CM-35 | Use: 20 Playwright tests pass (scenarios A to E) |
| Deployed a public demo at a stable URL | CM-37 | Do not use: not deployed |
| Computer-vision FFB prototype with safe upload handling | CM-23 | Use only as "research prototype, no accuracy claimed" |

## 3. Facts the résumé may state from the applicant's README only

| Fact | Source |
|---|---|
| Full-Stack Developer, Bookengine.com, 2024 to present (as of the README's March 2025 update) | README |
| TITANSJET POS: real-time order management with Socket.io between order points and kitchen displays; a Task Tracker with multi-level assignment and Kanban workflow | README |
| Livepocket HRM and payroll: validation logic for complex overtime rules tested with PHPUnit; document management with multi-level approval and Pako compression; encrypted and decrypted salary adjustments; notifications through Firebase Cloud Messaging | README |
| Skills: Angular, Vue.js, SolidJS; .NET, Rust, Python, Laravel, CodeIgniter, NestJS; MariaDB, PostgreSQL, MongoDB; Ubuntu, Git, Docker, JetBrains IDEs | README |
| Education: Bachelor's Degree in Computer Science, Thaksin University (TSU) | README |
| Contact: GitHub github.com/chavis-mtech; email chavis.mtech@gmail.com. Whether to publish a phone number is an owner decision | README |

Do **not** add job titles beyond "Full-Stack Developer", team sizes, durations, metrics or outcomes for these roles unless the owner supplies and confirms them.

## 4. Checklist: what the applicant still needs to supply (TODO)

- [ ] **Thai name** (ชื่อ-นามสกุลภาษาไทย). The README gives the Latin spelling only.
- [ ] **LinkedIn URL** (not in the README).
- [ ] **Project-management and team-leadership experience.** The README lists none; the target role is Technical Project Manager (Software & AI), so this is the most important gap. Give only true, checkable facts (team size, scope, duration, outcome).
- [ ] **AI and data experience outside this project** (courses, work, other repositories), if any.
- [ ] **Certifications** (PM, cloud, data or security), if any. None are claimed.
- [ ] **Language proficiency** (Thai, English, others).
- [ ] **Availability**: start date and notice period, preferred work location (city, remote or hybrid).
- [ ] **Current employment status.** The README (updated March 2025) says Bookengine.com 2024 to present; confirm it is still accurate in November 2026 and add dates.
- [ ] **Education details** (graduation year, honours), if desired.
- [ ] **Résumé PDF** (single source of truth for dates and titles) and an optional **photo**.
- [ ] **Which contact details to publish** (email, phone, social links).
- [ ] **Public repository URL** and **demo URL** once published and deployed.
- [ ] **Confirm the "AI-assisted development" wording** and the description of your own hands-on contribution.
- [ ] **References**, if the process asks for them.
