# Architecture Decision Records

Owner: architect. Format: Status / Context / Decision / Consequences. ADR-001..010 come from the build plan (kept private) §2;
ADR-011+ were added during wave 0. Status values: `accepted`, `superseded`, `proposed`.

---

## ADR-001 — Modular monolith: pnpm workspace + one Python service
**Status:** accepted
**Context:** SPEC §7 asks for "modular monolith first", domain boundaries, API-first. A portfolio demo run by one person must be cheap to operate.
**Decision:** One repo, pnpm workspace (`apps/*`, `packages/*`) with a Next.js web app and a single FastAPI service (`apps/ai-api`). Domain boundaries are Python packages (`app/models/<domain>.py`, `app/services/<module>.py`, `app/api/v1/<module>.py`), not network services.
**Consequences:** One deploy unit per tier, simple local dev. Boundaries are enforced by ownership + review, not by process isolation. Splitting a module into a service later means extracting its router/service/models — the API contract stays the same.

## ADR-002 — All analytics, business rules and AI live in Python
**Status:** accepted
**Context:** KPI, OER, ROI and model numbers must be identical wherever they appear (dashboard, copilot, export).
**Decision:** `apps/ai-api` is the single source of truth for every number. Next.js renders and proxies only; no business formulas in TypeScript.
**Consequences:** Frontend agents cannot "fix" a number locally — they must request a backend change. Every number carries `provenance`, so the UI can badge it.

## ADR-003 — SQLite default, PostgreSQL-compatible schema
**Status:** accepted
**Context:** "clone → seed → run" with zero infrastructure; Docker is unavailable on the build machine.
**Decision:** SQLAlchemy 2.0 typed models, no SQLite-only SQL, deterministic constraint names (naming convention), `UTCDateTime` type, CHECK constraints instead of native enums, `BIGINT`/`INTEGER` variant for large-table PKs. `DATABASE_URL` switches to PostgreSQL. SQLite foreign keys are enabled with `PRAGMA foreign_keys=ON` on every connection.
**Consequences:** Verified: Alembic `0001` upgrade on fresh SQLite equals `create_all` (test), and offline PostgreSQL DDL renders (`alembic upgrade head --sql`). **Not verified:** running against a live PostgreSQL server (none available). PostgreSQL needs a driver (`psycopg[binary]`) added to the image.

## ADR-004 — REST + OpenAPI → generated TypeScript types
**Status:** accepted
**Context:** Several frontend agents work in parallel with backend agents.
**Decision:** FastAPI generates OpenAPI; `make contracts` exports `packages/contracts/openapi.json` and generates `packages/contracts/src/api-types.ts` with `openapi-typescript`. CI fails if the generated file is stale.
**Consequences:** Frontend code is type-checked against the real contract. Any schema change requires `make contracts`.

## ADR-005 — Scenario playback, not data mutation
**Status:** accepted
**Context:** A public demo with many concurrent visitors must be reproducible and cross-module consistent.
**Decision:** Scenarios are pre-generated deterministic episodes. The client chooses `as_of` (demo clock) and optionally `scenario_id`; the server is stateless about time. Services never read "actual" data with `ts > as_of`.
**Consequences:** No background clock; "Simulated Live" = client advancing `as_of` (`POST /demo/tick` helper). All modules agree because they read the same rows at the same `as_of`.

## ADR-006 — Mutable records are scoped by `X-Demo-Session`
**Status:** accepted
**Context:** Visitors must be able to create work orders / approve recommendations without corrupting each other's demo.
**Decision:** Mutable tables carry nullable `session_id` (NULL = seeded shared baseline). Reads return baseline ∪ own session (`services.demo_context.session_filter`). Writes require a session (`require_session` → 428). `POST /demo/session/reset` deletes the caller's business rows. See ADR-014 for changes to baseline rows.
**Consequences:** No auth needed for a safe public demo. Session data grows; an admin `reset-all` and a retention job (backend-b) bound it.

## ADR-007 — Simulated roles via `X-Demo-Role`, enforced server-side
**Status:** accepted
**Context:** SPEC §10: 8 roles, server-side authorization, cross-role tests; roles are *simulated viewpoints*.
**Decision:** `services/rbac.py` holds the role → permission matrix (single source of truth). Handlers depend on `require_permission(Permission.X)`. OpenAPI operations carry `x-permission` and derived `x-roles`; a test asserts the declared permission equals the enforced one. Copilot tools have per-role permissions (`copilot:tool:<name>`).
**Consequences:** Anyone can pick any role — this is a demo, not security. The UI must label roles as simulated. Production would replace the header with real identity (OIDC) while keeping the permission layer.

## ADR-008 — i18n via cookie locale, no `/th` route prefix
**Status:** accepted
**Context:** SPEC route list has no locale prefix; TH default with EN toggle.
**Decision:** Cookie-based locale + typed dictionaries in the web app. API returns bilingual labels where relevant (`name_en`/`name_th`, `Disclaimer.text_th`) and copilot accepts `lang`.
**Consequences:** Route list stays intact; SEO per-locale is not a goal.

## ADR-009 — Classical ML with naive baselines and temporal splits
**Status:** accepted
**Context:** SPEC §9 forbids fake accuracy; tabular synthetic data.
**Decision:** scikit-learn models (HistGradientBoosting, RandomForest, IsolationForest, statistical baselines). Every model is compared to a naive baseline on a temporal hold-out; `model_registry.beats_baseline` records the truth. `injected_events` (ground truth) is used only by evaluation, never by features or the API.
**Consequences:** Some models may not beat the baseline — that is reported, not hidden.

## ADR-010 — Copilot: deterministic tool router + optional LLM adapter
**Status:** accepted
**Context:** Must work with no API key; must never let an LLM run free SQL.
**Decision:** Intent routing → allow-listed structured tools (permission-checked per role) → templated, cited answers. An optional provider adapter (`LLM_PROVIDER`) may phrase answers but only sees tool outputs and retrieved chunks.
**Consequences:** No-API mode is the default and fully testable; LLM mode is an enhancement.

## ADR-011 — One continuous timeline with embedded scenario episodes
**Status:** accepted
**Context:** ADR-005 needs a concrete data shape. Alternatives: (a) one dataset per scenario (branches) or (b) one 120-day timeline with episodes at known dates.
**Decision:** (b). The data engine generates a single deterministic 120-day timeline ending `DEMO_ANCHOR`; each scenario is a window in it (`scenario_runs.start_ts/end_ts/focus_ts/baseline_ts`). `scenario_id` without `as_of` resolves to `focus_ts`. NORMAL_DAY points at a representative normal day.
**Consequences:** Cross-module consistency is automatic (one set of facts). Scenarios cannot overlap in conflicting ways; the data engine schedules them on distinct dates. Facts tables need no `scenario_id` column; `alerts`, `anomaly_events`, `injected_events` carry `scenario_code` for filtering/eval.

## ADR-012 — In-process token-bucket rate limiter
**Status:** accepted
**Context:** Public demo needs rate limiting (SPEC rule 10) without extra infrastructure.
**Decision:** Own ASGI middleware (`app/security/ratelimit.py`) with token buckets per client IP and per `X-Demo-Session`; 429 with the error envelope and `Retry-After`; `/health`, `/ready`, `/docs` exempt. `X-Forwarded-For` only honoured when `TRUST_PROXY_HEADERS=true`.
**Consequences:** Limits are per process. Multi-replica deployment must swap in a shared store (Redis) behind the same `check()` interface.

## ADR-013 — Append-only audit log with a hash chain
**Status:** accepted
**Context:** Work-order workflow and human approvals need an audit trail (SPEC rule 10, scenario B).
**Decision:** `services/audit.write_audit()` appends rows in the same transaction as the business change; each row stores `sha256(prev_hash + canonical fields)`. Audit rows are never updated or deleted — session reset deletes business rows and appends a reset audit entry. `verify_chain()` detects tampering.
**Consequences:** Tamper-evident, not tamper-proof (a DB admin can rewrite the whole chain). On PostgreSQL with concurrent writers the chain tail must be locked (`SELECT … FOR UPDATE` / advisory lock) — SQLite serialises writes already.

## ADR-014 — Copy-on-write for changes to seeded rows
**Status:** accepted
**Context:** Visitors act on seeded alerts, anomalies, recommendations and work orders, but ADR-006 forbids mutating the baseline.
**Decision:** Status changes are separate session-scoped tables (`alert_status_changes`, `anomaly_status_changes`, `recommendation_decisions`, `work_order_status_history`); effective status = latest change in the caller's session, else the baseline value. A transition on a seeded work order creates a session copy (`work_orders.cloned_from_id`).
**Consequences:** Reads compute effective status (small join). Baseline stays pristine for every visitor.

## ADR-015 — Contract-first stubs with ownership metadata
**Status:** accepted
**Context:** All downstream agents start at once and need a complete, typed API on day one.
**Decision:** Every endpoint exists now with an explicit Pydantic response model; unimplemented handlers call `errors.not_implemented(owner=…)` → HTTP 501 envelope. Operations carry `x-owner`, `x-task`, `x-status`, `x-permission`, `x-roles`. `docs/architecture/API_CONTRACT.md` and `DATABASE_SCHEMA.md` are generated (`make docs`) so they cannot drift.
**Consequences:** Owners flip `status="implemented"` in `contract(...)` when done; the generated table then shows real progress. Schema changes must stay additive.

## ADR-016 — Time handling
**Status:** accepted
**Context:** Mill business day is Asia/Bangkok; storage must be unambiguous.
**Decision:** Store UTC everywhere (`UTCDateTime` normalises on write, tags UTC on read). `as_of`: ISO date → 18:00 mill time; naive datetime → mill-local; offset datetime as given. Must fall in `[window_start, window_end)` = 120 mill-local days ending `DEMO_ANCHOR`. Default `as_of` = anchor day 18:00 mill time.
**Consequences:** One parsing rule for all agents (`services/demo_context.parse_as_of`).

## ADR-017 — Mass-balance traceability by default
**Status:** accepted
**Context:** SPEC 4.H: multi-supplier mixing; must state lot-based vs mass-balance.
**Decision:** `batch_inputs` (FFB batch → processing batch, mass + share) and `lot_compositions` (processing batch → CPO lot, tonnes + share) carry `trace_method`, default `mass_balance`; `lot_based` reserved for segregated runs. Sustainability fields are a data-model sketch, never a certification claim.
**Consequences:** Backward trace yields supplier *shares*, not physical certainty; the UI must say so.
