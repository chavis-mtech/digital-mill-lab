# Final delivery report — Digital Mill Lab

Independent concept demo (NOT an official system of any company). All data is synthetic. Written 2026-11-22 by the orchestrator.
Evidence rule: "verified" = the orchestrator ran the check himself (log: the engineering log (kept private)); "agent-reported" = only an agent's status file says so.

## 1. Status at a glance (114 tasks, `docs/TASKS.md`, generated 2026-11-22)

| Status | Tasks | Meaning |
|---|---:|---|
| done-verified | 78 | re-run by the orchestrator (tests, SQL, browser/e2e, own probes) |
| done-claimed | 23 | built and reported with evidence by an agent; not re-run by the orchestrator |
| partial | 11 | built with a stated gap (see §4) |
| blocked-owner | 2 | public deployment; publishing the repo so CI can run |
| not-started | 0 | |

## 2. Completed features (all verified unless marked)
- **Synthetic data engine**: deterministic 120-day timeline, 1,569,016 rows, 6 linked scenario episodes, 58 consistency checks; re-seed reproduces checksum `34fc4a37…`; cross-table totals reconcile (FFB 111,814 t → CPO 20,643 t).
- **Backend API (FastAPI)**: 97 operations, all implemented; KPIs equal direct SQL; `as_of` never leaks future data; role-based access, session-isolated sandbox, hash-chained audit trail; work-order workflow with human confirmation; ROI simulator (four cases, no double counting, recomputed by hand); traceability (mass-balance); scenario what-ifs.
- **ML layer**: 8 models + causal detection pipeline, reproducible (`python -m app.ml.train`, ~90 s), model cards, leakage tests (49 ML tests pass).
- **Copilot (deterministic, no paid API)**: 10 read-only tools over the real services, grounding verifier (every number traced), per-role tool allow-list, injection defences, refuses control/write/SQL/accusation/no-data questions; RAG over 6 sample documents with citations.
- **Web app (Next.js)**: public site (TH/EN), 7-step guided tour, Executive control tower, Digital Twin Lite, palm-mill analytics, AI insights, scenarios, ROI, maintenance + work orders, logistics, energy, traceability, Copilot page, 7 technical-docs pages, prototypes page (concept cards).
- **Quality/security**: 20 Playwright end-to-end specs for acceptance scenarios A–E; axe 0 serious/critical (agent-run, spot-confirmed); security suite (authorization matrix, session isolation, as_of sweep, abuse/rate-limit, uploads); defects found and fixed along the way are listed in the QA log (kept private) (QA-01…22) and `docs/review/AUDIT.md`.
- **Docs**: README (proven from a clean copy: setup 40 s, demo-data 141 s, tests 140 s), SECURITY, DEPLOYMENT, API_DOCUMENTATION, DEMO_GUIDE, KNOWN_LIMITATIONS, ADRs, data/AI/model docs, business research, proposal, roadmap, case study, recruitment emails TH/EN, résumé entry (drafts).

## 3. Test results (orchestrator-run, final build)
| Suite | Result |
|---|---|
| Backend `pytest -q` (all) | **1140 passed, 2 skipped** (opt-in full-seed test; empty-parameter test), 0 errors; `ruff` clean |
| Web (vitest) | 75 passed; typecheck + lint clean; production build 34/34 pages |
| End-to-end (Playwright, production build + API on a DB copy) | **20 passed** (1.2 min), twice on the final build |
| Copilot evaluation (`python -m app.copilot.evaluate`) | grounded answers 45/45; no-data refused 12/12; unauthorized tool attempts refused 23/23; injections blocked 26/26; multi-turn 9/9; citations 9/10; fresh paraphrases 25 correct / 16 clarified / 5 wrong (83 % correct when it answers) |

## 4. Model evaluation (synthetic benchmark — NOT plant measurements; held-out 2026-10-15 onward)
| Model | Result |
|---|---|
| OER forecast | **does not beat baseline** at any granularity: hourly MAE 0.268 vs 0.237 pp (a train-mean constant gets 0.264); shift 0.205 vs 0.146; day 0.219 vs 0.161. Model driver-attribution is unreliable out of sample (not shown as a cause anywhere) |
| Production anomaly | precision 1.00, recall 4/7, 0 false positives/day, median latency 2.0 h |
| Equipment anomaly | precision 1.00, recall 4/6; press PRS-03 detected **56.5 h before** the rule warning and **148.3 h before** the rule critical alarm (171 h after injected onset) |
| Energy forecast / anomaly | forecast loses (MAE 10.90 vs 9.67 kWh/h); anomaly detector misses the only held-out label |
| Queue time / arrival forecast | marginal win (2.72 vs 2.78 min) / loses (2.109 vs 2.101 trucks/h) |
| Sustained-queue alert | recall 3/3, precision 0.50, 0.054 false alarms/day |

## 5. Partial / not implemented (honest list)
- **Queue simulation (AI-D03)** is not calibrated: it does not reproduce the observed congestion (FIFO replay 7.3 vs 37.4 min observed); the UI shows both with a warning.
- **LLM mode** of the Copilot was only tested with a fake provider; no real LLM provider was ever called.
- **PostgreSQL**: DDL checked offline only. **Docker images/compose and GitHub Actions: configured, NEVER built or run** (no Docker daemon here; repository not published).
- **Performance**: single-process API queues ~20 parallel page requests; multi-worker Docker setup (`WEB_CONCURRENCY`, WAL) is configured but unmeasured (QA-22 open).
- **Not built**: server-side PDF export (HTML print + CSV only), computer-vision grading (research prototype only, no accuracy), P2 concepts (plantation, petroleum, port, group data platform = concept cards, no outputs).
- API narrative text (insights/alert titles) is English-only on the Thai UI; Thai copy not reviewed by a native speaker; ML artifacts trained once (in-sample before 2026-10-15).

## 6. Deployment status
**No public deployment exists; there is no demo URL.** Hosting, cost and domain are the owner's decision. `docs/DEPLOYMENT.md` has the steps and a pre-exposure checklist.

## 7. Known risks
1. Synthetic data only — nothing here is a measurement of any company; every ROI figure is illustrative.
2. Several models lose to naive baselines (reported as measured); the strongest value is anomaly detection with lead time.
3. Unverified infrastructure (Docker, CI, PostgreSQL, public exposure); rate limiter is per process behind proxies (`TRUSTED_PROXY_HOPS`, QA-20/21).
4. The build was AI-agent-assisted; the résumé/emails disclose it, the exact wording is the owner's to confirm.

## 8. Owner decisions and next steps
1. Decide hosting/cost/domain; deploy; replace `[DEMO_URL]` in the emails. 2. Start Docker Desktop (or a CI runner) to verify the images; publish the repo to run CI. 3. Confirm the role wording ("author and technical lead, AI-assisted"), the AI-disclosure lines, Thai pronouns (draft uses ผม/ครับ by assumption), and whether to publish a phone number (currently NOT published). 4. Supply facts the README lacks (Thai name, LinkedIn, project-management experience, certificates, dates, résumé PDF). 5. Native Thai review of UI copy. 6. If pursuing a real pilot: calibrate on real plant data, replace synthetic benchmarks, integrate through the contract interfaces (`docs/architecture/INTEGRATION_CONTRACTS.md`).
