# Security — Digital Mill Lab (public demo)

> Independent portfolio / concept demo on **synthetic data**. Not an official system of any company. This document describes the
> controls that exist in the code **today**, the test that proves each one, and what is deliberately or honestly **not** done.
> Status date: 2026-11-22. No human penetration test has been performed. No public deployment exists yet.

## 1. Threat model (public demo)

What is being protected is small on purpose: there is no real company data, no personal data beyond the visitor's own
throw-away sandbox, no credentials and no payment. The realistic risks for a public portfolio demo are:

| Asset / risk | Why it matters here | Main controls |
|---|---|---|
| Availability (one small API process) | A single visitor or scanner can make the demo look broken for everyone | Rate limits, body-size cap, bounded list/simulation inputs, upload decompression limits (§3.4–3.6) |
| Demo integrity between visitors | Visitor A must not change what visitor B sees | Session-scoped writes + copy-on-write on seeded rows (§3.2) |
| Honesty of the numbers | Showing future data at an earlier demo clock, or leaking the synthetic "answer key", would make the AI look better than it is | `as_of` wall, ground-truth secrecy (§3.3) |
| Audit evidence | Work-order changes should be tamper-evident in the demo | SHA-256 hash chain (§3.7) |
| Browser-side attacks via API output | Stored text (work-order titles, Copilot answers) rendered in the UI | JSON-only API, CSP on HTML print views, no HTML in API strings (§3.5) |
| LLM key (optional) | Only if an owner enables an LLM provider | env-only configuration, deterministic default (§4) |

Out of scope: real authentication, multi-tenant data separation, protection of real plant systems (there are none — the demo is
read-only analytics with **no machine control**).

## 2. Roles are simulated, not authentication

`X-Demo-Role` selects one of 8 **simulated viewpoints** (SPEC §10, ADR-007). Anybody can send any role. Server-side permission
checks are real and tested, but they demonstrate *how* authorization would be enforced — they do **not** protect anything,
because there is no identity behind the header. A production system needs SSO/OIDC, per-user identities and the same
permission table bound to real users.

## 3. Implemented controls and the tests that prove them

All test paths are under `apps/ai-api/tests/`. Counts are collected test items (2026-11-22).

### 3.1 Authorization (simulated roles)

| Control | Test |
|---|---|
| Every operation without `x-permission` is on an explicit public allow-list (`/health`, `/ready`, `/api/v1/meta`, `/api/v1/demo/roles`) | `security/test_authz_matrix.py` (316 items) |
| Declared `x-roles` = RBAC table; 97 operations x 8 roles: forbidden roles get 403 `forbidden`, permitted roles never get 401/403/5xx | same |
| Writes without `X-Demo-Session` -> 428 `session_required`; invalid role/session headers -> 422; role cannot be smuggled via query/cookie/body | same; `test_rbac.py`, `backend_b/test_workorders.py` |

### 3.2 Visitor isolation (session sandbox, ADR-006 / ADR-014)

| Control | Test |
|---|---|
| Session-scoped rows are invisible to other sessions and anonymous viewers; foreign ids behave exactly like missing ids (no existence oracle) | `security/test_session_isolation.py` (25) |
| Seeded baseline is byte-identical after two visitors act and after reset (row fingerprint of every shared table) | same |
| Work order in session A changes PRS-03 `maintenance_status` and the linked alert status for A only | `integration/test_cross_module.py::test_work_order_changes_prs03_and_alert_for_that_session_only` |
| Session reset deletes only the caller's rows; reset-all is admin-only | `security/test_session_isolation.py` |

### 3.3 Data honesty: `as_of` wall and ground-truth secrecy

| Control | Test |
|---|---|
| No timestamp later than `as_of` in non-forecast data, 10 clocks x every GET operation | `security/test_asof_leak.py` (31) |
| ML alerts show the severity/title known at the demo clock, not the episode peak (QA-16, fixed 2026-11-22) | `integration/test_cross_module.py::test_ml_alert_severity_and_title_never_come_from_the_future` |
| Runtime code never reads `injected_events` / designed effects; ~190 secret strings absent from every response, KB doc and adversarial Copilot answer | `security/test_ground_truth.py` (11) |

### 3.4 Abuse and resource controls

| Control | Test |
|---|---|
| Token-bucket rate limit per client IP (240/min, burst 40) and per `X-Demo-Session` (120/min); 429 envelope + `Retry-After`; spoofed `X-Forwarded-For` ignored unless `TRUST_PROXY_HEADERS=true` | `security/test_abuse_ratelimit.py` (11) |
| Behind proxies: client IP = `TRUSTED_PROXY_HOPS`-th `X-Forwarded-For` entry from the right; spoofed prefixes ignored; too-short header -> TCP peer (QA-13, QA-20) | `security/test_proxy_hops.py` (12) |
| Request body cap 256 KiB (`MAX_BODY_BYTES`), enforced before parsing, also for chunked bodies -> 413 | `security/test_http_hardening.py` (45) |
| Every list parameter has `limit <= 200/1000`; queue-simulation policies bounded (QA-12); expensive read params bounded | `security/test_abuse_inputs.py` (148) |
| Schema-driven fuzz of every GET parameter and POST field (SQLi, traversal, NUL, 10k chars, Thai/emoji, CRLF): never 5xx, never a stack trace/path/SQL in the body, DB unchanged | same |
| DB connection pool sized for the 40-thread handler pool, so load causes latency instead of HTTP 500 (QA-19) | the QA log (kept private) phase B, item B2 (load measurement) |

### 3.5 Output and HTTP hardening

| Control | Test |
|---|---|
| `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; `/api/*`: `Cache-Control: no-store`, CSP `default-src 'none'`, `X-Frame-Options` (QA-02) | `security/test_http_hardening.py` |
| Printable HTML reports: no scripts allowed by CSP, user text escaped | same; `test_abuse_inputs.py` (stored `<script>` returns as JSON data only) |
| CORS: only configured origins, no credentials, GET/POST/OPTIONS only (production web proxies same-origin, so CORS is only for local dev) | `security/test_http_hardening.py` |
| Error envelope `{"error":{code,message,details}}` everywhere; `OverflowError` -> 422 (QA-04); `X-Request-ID` sanitised (QA-05) | same |

### 3.6 Uploads (CV prototype)

| Control | Test |
|---|---|
| Allowed types by content (magic bytes + structure), not by name/declared type; polyglot tails rejected; metadata stripped; random stored names; quota; 5 MiB cap; decompression-bomb limits; corrupt images -> 415 before storage (QA-14) | `security/test_uploads_extended.py` (88), `test_uploads.py` |

### 3.7 Audit trail (ADR-013)

| Control | Test |
|---|---|
| Append-only `audit_logs` with SHA-256 chain; edits to any field, deleted middle rows and forged rows are detected | `security/test_session_isolation.py` (tamper tests), `test_audit.py` |
| Audit endpoint verification is incremental above 20,000 rows (QA-10, fixed 2026-11-22): measured full walk 0.10 s at 10k rows, 1.05 s at 100k, 2.17 s at 200k; incremental call 1–2 ms | `integration/test_audit_chain_cost.py` (3) |

Documented audit limitations (pinned by tests): truncating the newest rows, or rewriting the whole table with recomputed hashes, is
**not** detectable (no external anchor). Above 20,000 rows the endpoint only re-checks rows after its in-memory checkpoint; an edit to an
older row is caught by a full walk (`verify_chain`, `python -m app.seed.validate`, or a process restart), not by the endpoint.

## 4. LLM key handling

* Default `LLM_PROVIDER=none`: the Copilot runs a deterministic tool router; no external call, no key.
* Optional providers (`openai_compatible`, `anthropic`) read `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` (and `LLM_BASE_URL`) from the environment / `.env` only.
  `.env` is git-ignored; `.env.example` contains no value.
* The key is a plain string setting (not a `SecretStr`): never log the settings object. The key is not returned by any endpoint (`/api/v1/meta` exposes only `copilot_mode`).
* The LLM never gets SQL access: it can only call the same allow-listed tools as the router, output is verified (numbers, causal claims, instruction-like text) and rejected answers fall back to deterministic text.
* **Never exercised against a real provider** (fake provider + mocked HTTP only). Before enabling: set a spend limit at the provider, use a key scoped to this app, and keep the per-session rate limit.

## 5. NOT implemented / open (honest list)

| Item | Status |
|---|---|
| Real authentication / authorization | Not implemented by design: roles are simulated viewpoints (§2) |
| Shared-table writes on read paths | `GET /maintenance/recommendations` (and pages that call it) lazily create rule-generated recommendation catalog rows (ids 9,000,000+) in the shared `ai_recommendations` table. Bounded by equipment x rules, idempotent, contain no visitor input, but a public **read** writes to a shared table (orchestrator item 11) |
| QA-06 | `/ai/models` per-label evaluation table names 13 held-out `injected_events` codes (evaluation transparency by design; owner may prefer to anonymise) |
| QA-07 | Scenario field `expected_effects` actually carries *measured* effects (naming only) |
| QA-09 | ML artifacts trained once; at demo clocks before 2026-10-15 their output is in-sample. Only `/ai/oer/explanation` says so |
| QA-15 | HTTP 500 responses (Starlette's outermost handler) carry the JSON envelope but not `X-Request-ID`, CORS or security headers |
| QA-16 (rest) | Equipment health risk sub-score, recommendation priority, scenario catalogue counts and the Copilot `open_alerts` tool still read the STORED (episode-peak) severity of ML alerts; `/alerts`, executive and twin views are fixed. Proper fix: write severity as known at `detected_at` in `app/ml/train.py` before the final data rebuild |
| Rate limiter is in-process | One API process only; several replicas need a shared store (Redis). The per-IP limit is weak behind shared NAT / mobile carriers; the per-session limit is easy to evade by rotating session ids (each new id gets a fresh bucket) — it limits honest heavy use, not attackers. The per-IP bucket is the only abuse brake, and only as good as the proxy-hop configuration (DEPLOYMENT.md) |
| Admin-only actions are only "simulated admin" | Because roles are headers, any visitor can send `X-Demo-Role: system_admin` and call `POST /demo/reset-all` (clears every visitor sandbox; seeded data and audit log are untouched). Block this path at the proxy in a public deployment, or accept it |
| QA-21 (config) | `infra/docker/docker-compose.yml` sets `TRUST_PROXY_HEADERS=true` although Next.js (the only hop) does not append `X-Forwarded-For`: the per-IP key becomes client-chosen. Not fixed (infra file, never run); DEPLOYMENT.md §3/§5 give the correct values |
| No WAF, bot protection, CAPTCHA, request signing | Not implemented; would be the hosting layer's job |
| HSTS / TLS | Not set by the app; must be done by the TLS reverse proxy (DEPLOYMENT.md) |
| Dependency scanning / SBOM | Not set up; versions are pinned in `requirements.lock` / `pnpm-lock.yaml` |
| Penetration test by a human | Not done. All findings above come from automated tests written by AI agents (QA phase A/B) |
| Docker images, CI, PostgreSQL | Configured, never built / run / verified (no Docker daemon, no GitHub run, no Postgres server) |

## 6. Reporting

This is a personal portfolio project. Report issues to the repository owner (see README). Please do not test against a
deployment you do not own.
