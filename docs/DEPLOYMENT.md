# Deployment — Digital Mill Lab

> Independent portfolio / concept demo on synthetic data. Status date 2026-11-22.
> **Verified:** local run (README quick start, proven from a clean copy). **Built and run only on GitHub Actions (2026-11-22, all jobs green; not on the author's machine):** Docker images and
> compose (no Docker daemon on the build machine), GitHub Actions CI (no remote run), PostgreSQL (offline DDL only).
> **No public deployment exists.** Hosting provider, domain and cost are the owner's decision — this document picks nothing
> and nothing was provisioned.

## 1. Local run (verified)

See the [README](../README.md) quick start: `make setup`, `make demo-data`, `make test`, `make dev`.

* API: `make dev-api` (uvicorn with `--reload`, port `API_PORT`, default 8000). Production-style:
  `cd apps/ai-api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2`.
* Web: `make dev` starts both. Production-style web: `cd apps/web && API_PORT=8000 pnpm build && PORT=3000 pnpm start`.
  **Next.js bakes the `/api/v1` rewrite target into the build**: set `API_INTERNAL_URL` (or `API_PORT`) at `next build` time.
* Data: `data/demo.db` (SQLite, ~165 MB after `make demo-data`). Relative SQLite paths in `DATABASE_URL` resolve from the repo root.

## 2. Topology

```
browser ──HTTPS──> [TLS reverse proxy] ──HTTP──> Next.js (web, :3000) ──rewrite /api/v1/*──> FastAPI (api, :8000) ──> SQLite file
                    (owner's choice)               same origin for the browser                 (or PostgreSQL, unverified)
```

The browser only talks to the web origin; Next.js proxies `/api/v1/*` to the API (no CORS needed in production). The API
should not be exposed publicly on its own port.

## 3. Rate limiting behind proxies (read before exposing anything)

The API limits requests per client IP (240/min, burst 40) and per `X-Demo-Session` (120/min). Behind proxies the TCP peer
is always the proxy, so the client IP must come from `X-Forwarded-For` (XFF):

* `TRUST_PROXY_HEADERS=true` makes the API read XFF at all (never enable it if clients can reach the API directly).
* `TRUSTED_PROXY_HOPS=N` = number of trusted proxies that **append** to XFF in front of the API. The client is the N-th entry
  from the right. Entries further left are client-supplied and ignored. If the header has fewer than N entries, the API falls
  back to the TCP peer (one shared bucket, never a client-chosen value).

**Observed Next.js behaviour (verified 2026-11-22, Next.js 16.4.6, both `next dev` and production `next start`, in the clean
copy, with a header-echo server as the rewrite target): Next.js rewrites do NOT add or append `X-Forwarded-For`.** They forward the
client's header verbatim (absent stays absent; `6.6.6.6` arrives as `6.6.6.6`), set `X-Forwarded-Host`, and the API's TCP peer is
always the Next.js process. Next.js therefore does **not** count as a hop, and Next.js alone can never supply a trustworthy client IP.

| Topology | `TRUST_PROXY_HEADERS` | `TRUSTED_PROXY_HOPS` | Effect |
|---|---|---|---|
| Local dev, browser -> API directly | `false` | (ignored) | key = browser address |
| browser -> Next.js -> API (Next.js is the public edge) | **`false`** | (ignored) | every visitor shares one per-IP bucket (Next's address) — the 429s the web verifier saw. `true` here would be worse: the key would be whatever the client writes into XFF (evadable) |
| browser -> TLS reverse proxy that appends/sets XFF (e.g. nginx `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`) -> Next.js -> API | `true` | `1` | key = address nginx saw (the right-most entry); Next.js passes it through |
| browser -> CDN (appends) -> TLS proxy (appends) -> Next.js -> API | `true` | `2` | only if every listed hop appends |

So a public deployment needs a reverse proxy in front of Next.js that sets XFF; with Next.js as the edge, per-IP limiting can only be
a shared bucket (raise `RATE_LIMIT_PER_IP_PER_MINUTE` accordingly and rely on proxy/WAF limits). `infra/docker/docker-compose.yml` currently sets
`TRUST_PROXY_HEADERS=true` with Next.js as the only hop — that makes the per-IP limit client-controlled (QA-21, see §5).

Getting this wrong has two failure modes: too few hops = every visitor shares the proxy's bucket (the web verifier saw real pages
return 429 after one automated scan, because all requests arrived from 127.0.0.1); too many hops = the key becomes a client-supplied
value and the per-IP limit can be evaded by rotating it. Verify after deployment by sending a request with a fake XFF prefix and
checking the API log/limit behaviour.

Honest limits: the per-session limit is the main protection for normal visitors but is trivially evaded by rotating session ids (each new
id gets a fresh bucket); the per-IP limit is the only brake on a scripted client and is coarse behind carrier-grade NAT. The limiter is in
memory: with several API processes (`--workers N`) each process has its own buckets, so the effective limit is N times higher. A WAF or the
proxy's own rate limiting (e.g. nginx `limit_req`) is recommended in front of a public demo. `infra/docker/api-entrypoint.sh` starts uvicorn
with `--proxy-headers`; uvicorn only applies it for peers in `FORWARDED_ALLOW_IPS` (default 127.0.0.1), which is separate from the app's limiter.

### 3.1 Observed XFF header through Next.js (raw)

Echo target on 127.0.0.1:8122, web `next start` on 3122 (clean copy, `API_PORT=8122 pnpm build`):

```
client sends no XFF                 -> API sees x-forwarded-for: null,                  peer 127.0.0.1, x-forwarded-host localhost:3122
client sends "6.6.6.6"              -> API sees x-forwarded-for: "6.6.6.6"
client sends "6.6.6.6, 203.0.113.7" -> API sees x-forwarded-for: "6.6.6.6, 203.0.113.7"
same via the LAN interface address  -> unchanged (no peer address appended)
```

## 4. Environment variables (from `.env.example`)

| Variable | Default | Meaning / production note |
|---|---|---|
| `DEMO_MODE` | `true` | Public demo behaviour (simulated roles, session-scoped writes, rate limits) |
| `APP_ENV` | `development` | `development` / `test` / `demo` (shown in `/api/v1/meta`) |
| `DATABASE_URL` | `sqlite:///data/demo.db` | Relative SQLite paths resolve from the repo root. PostgreSQL: `postgresql+psycopg://...` (needs `psycopg` installed; unverified) |
| `DEMO_ANCHOR` | `2026-11-20` | Last day of the synthetic dataset |
| `DATASET_DAYS` | `120` | Dataset window length |
| `MILL_TIMEZONE` | `Asia/Bangkok` | Business-day timezone |
| `RATE_LIMIT_ENABLED` | `true` | Keep `true` in any exposed deployment |
| `RATE_LIMIT_PER_IP_PER_MINUTE` | `240` | Per client IP (see §3) |
| `RATE_LIMIT_PER_SESSION_PER_MINUTE` | `120` | Per `X-Demo-Session` |
| `RATE_LIMIT_BURST` | `40` | Bucket size (session bucket = burst / 2) |
| `TRUST_PROXY_HEADERS` | `false` | Read `X-Forwarded-For` (only behind trusted proxies) |
| `TRUSTED_PROXY_HOPS` | `1` | Trusted appending proxies in front of the API (§3) |
| `LLM_PROVIDER` | `none` | `none` = deterministic Copilot. `openai_compatible` / `anthropic` never tested against a real provider |
| `LLM_MODEL` | (empty) | Provider model name |
| `LLM_API_KEY` | (empty) | Secret: set only in the host's secret store, never commit |
| `MAX_BODY_BYTES` | `262144` | JSON request-body cap (413 above) |
| `UPLOAD_MAX_BYTES` | `5242880` | CV prototype upload cap |
| `UPLOAD_ALLOWED_TYPES` | `image/jpeg,image/png,image/webp` | Content-checked, not trusted from the client |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | CORS for local dev only (production is same-origin) |
| `LOG_LEVEL` | `INFO` | JSON logs to stdout |

Web (build/run time): `API_INTERNAL_URL` (rewrite target, baked at build), `API_PORT` (fallback target port), `PORT` (web port),
`DOCS_ROOT` (folder with the repo `docs/` that the in-app /docs pages read at run time).

## 5. Docker / compose (images built and smoke-tested in CI; compose file not run)

`infra/docker/api.Dockerfile`, `web.Dockerfile`, `docker-compose.yml`, `api-entrypoint.sh`. The API image seeds the dataset and trains the
models at build time. None of this has been built or run: there is no Docker daemon on the build machine. Issues found by reading
(not by building) that will most likely break or degrade it:

1. `web.Dockerfile` copies `apps/web/public`, which does not exist -> the build step fails until the line is removed or the folder created.
2. The in-app `/docs` pages read markdown from `../../docs` relative to the process cwd (`features/docs/load.ts`, overridable with `DOCS_ROOT`);
   the web image copies no `docs/` folder -> those pages will not find their files.
3. **QA-21**: compose sets `TRUST_PROXY_HEADERS=true` while Next.js (which does not append XFF, §3) is the only hop: any client can choose its
   rate-limit key by sending `X-Forwarded-For`. Set it to `false`, or put an XFF-setting reverse proxy in front and keep `TRUSTED_PROXY_HOPS=1`.
   The API image also runs a single uvicorn process (see §8 for why `--workers 2-4` is advisable).
4. PostgreSQL profile: needs `psycopg[binary]` in the image; never run.

## 6. GitHub Actions (ran on GitHub 2026-11-22: all three jobs green)

`.github/workflows/ci.yml`: lint, migrations on a fresh SQLite DB, seed + validate, train into `data/dev/ml.db`, `pytest`, OpenAPI export,
contract-type drift check, web typecheck/lint/test/build. It ran on GitHub on 2026-11-22 (commit 23b77ad): backend job, contracts + web job and a Docker job (builds both images, starts them on one network, checks health, 12 KPIs, alerts and the web proxy) all passed. With the 2026-11-22 change the
QA suites pick up `data/dev/ml.db`, so they run instead of skipping in CI.

## 7. PostgreSQL (NOT verified)

Models are SQLAlchemy 2.0 and Alembic migrations exist; only offline DDL generation was checked. Not run against a live server. Known
SQLite-specific assumptions: the audit chain relies on the DB serialising writes (ADR-013 recommends `SELECT ... FOR UPDATE` or an advisory
lock on PostgreSQL); the connection-pool sizing in `app/db/session.py` is SQLite-only.

## 8. Capacity snapshot (single API process, measured 2026-11-22)

One uvicorn process, rate limit off, SQLite `data/dev/qa-docs.db` (seed + ML), clock 2026-11-20T08:00Z, `urllib` clients in threads,
n = 10 requests at c=1 and 20 at c=10 per endpoint. **The machine was shared** (load average 13–27: another agent's API at 400–1000 % CPU
and a Playwright run), so absolute numbers are pessimistic and noisy; re-measure on the target host.

* Cold start: process start -> `/health` 200 in 0.7–0.9 s; `/ready` 7 ms. First `/ai/oer/forecast` 660–920 ms (model load), then 31–55 ms.
* Memory (RSS): 144 MB idle, 247 MB after the first requests, 366 MB after the load run.

| Endpoint | c=1 p50 / p95 (ms) | c=1 req/s | c=10 p50 / p95 (ms) | c=10 req/s |
|---|---|---|---|---|
| GET /meta | 1 / 1 | 1,404 | 3 / 4 | 2,686 |
| GET /executive/overview | 211 / 260 | 4.6 | 15,764 / 15,881 | 0.6 |
| GET /executive/kpis | 118 / 153 | 8.1 | 14,649 / 15,494 | 0.7 |
| GET /alerts | 7 / 8 | 133 | 325 / 372 | 30 |
| GET /process/stages | 78 / 80 | 12.8 | 20,437 / 22,258 | 0.5 |
| GET /maintenance/equipment | 77 / 117 | 12.4 | 23,368 / 26,966 | 0.4 |
| GET /maintenance/equipment/18/health | 14 / 15 | 73 | 2,764 / 3,459 | 3.6 |
| GET /maintenance/equipment/18/sensors | 12 / 53 | 63 | 2,262 / 2,409 | 4.4 |
| GET /maintenance/recommendations | 75 / 86 | 13.0 | 14,701 / 15,332 | 0.7 |
| GET /ai/anomalies/equipment | 4 / 4 | 273 | 83 / 119 | 112 |
| GET /ai/oer/forecast | 31 / 37 | 31.6 | 977 / 1,516 | 9.3 |
| GET /logistics/queue | 6 / 6 | 165 | 158 / 206 | 60 |
| GET /traceability/backward (lot 60) | 3 / 3 | 355 | 139 / 163 | 69 |
| GET /production/summary | 21 / 22 | 47 | 433 / 497 | 22 |
| POST /roi/calculate | 2 / 2 | 584 | 12 / 18 | 770 |
| POST /copilot/chat ("What is the OER today?") | 72 / 89 | 13.6 | 4,622 / 5,192 | 2.2 |

An earlier run (same set-up, load 9–17) at **c=30**: `/executive/overview` p50 53.6 s, `/executive/kpis` p50 91 s, `/alerts` p50 1.8 s.

Reading: single requests are fast enough for a demo (most < 0.25 s). But the pandas/SQL-heavy endpoints (overview, KPIs, twin, equipment
list, recommendations) **lose 10–30x throughput under concurrency** inside one process (0.4–0.7 req/s at c=10 vs 4.6–13 at c=1), while light
endpoints degrade only 2–4x. Thread samples under load sit in `sqlite3` `fetchall` (the C loop releases and re-acquires the GIL per row while other
threads run pandas code); a repeat of the same 10-call test gave 0.84 s once and 8.9–10 s otherwise, so machine contention and in-process GIL
contention could not be separated on this shared machine (open finding QA-22). Before QA-19 (fixed) more than 15 concurrent requests also produced
HTTP 500 after a 30 s pool wait.

Recommendations for a public demo (owner's choice, not done): run 2–4 uvicorn worker processes (`--workers N`; measured `/executive/kpis` c=4
median 252 ms with 4 workers vs 539 ms with 1, on the busy machine), put a short-lived response cache in front of the read-only GET endpoints
(responses are deterministic for a given `as_of`/scenario), and re-measure on the target host. Remember that the in-memory rate limiter is per process.

## 9. Pre-exposure checklist

- [ ] Owner decided hosting, domain, budget and who operates it.
- [ ] TLS at the reverse proxy; HSTS set there; HTTP -> HTTPS redirect.
- [ ] Only the web port is public; the API listens on a private interface/network.
- [ ] `RATE_LIMIT_ENABLED=true`, `TRUST_PROXY_HEADERS=true`, `TRUSTED_PROXY_HOPS` matches the real chain (§3) and was tested with a spoofed XFF prefix.
- [ ] Proxy-level rate limiting / bot protection in front (recommended).
- [ ] `LLM_PROVIDER=none`, or a provider key stored only in the host's secret store with a spend cap.
- [ ] `APP_ENV=demo`; `.env` not in the image; no `data/dev/`, `docs/internal/` or `*.db` copied from a developer machine (`.dockerignore`).
- [ ] `make demo-data` run in the build (or the image built from a clean checkout); `python -m app.seed.validate` passes.
- [ ] Synthetic-data and independence notices visible on every page (they are in the UI and `/api/v1/meta`).
- [ ] Health checks: `/health` (liveness, no DB) and `/ready` (DB + data present) wired to the platform.
- [ ] Log retention decided (logs contain request paths and session ids, no personal data by design).
- [ ] Workers / memory sized (§8: ~250 MB RSS per API process after warm-up).

## 10. Backup and reset

* The canonical data is reproducible: `make demo-data` rebuilds `data/demo.db` deterministically (checksum in `data/synthetic/MANIFEST.json`).
  There is nothing to back up except visitor sandbox rows, which are disposable by design.
* Reset one visitor: `POST /api/v1/demo/session/reset` (their session) — the UI has a reset button. Reset all visitors: `POST /api/v1/demo/reset-all`
  with `X-Demo-Role: system_admin` (simulated role: anyone can send it, so a public deployment should block this path at the proxy or accept that
  any visitor can clear the sandboxes).
* `audit_logs` is append-only and is not cleared by resets; it grows with visitor activity (verification is incremental above 20,000 rows).
  To start fresh, rebuild the database.

## 11. Public demo: Vercel (web) + a container host (API) — written, NOT yet deployed

**Why two hosts.** Vercel runs the Next.js web app. It cannot run the API: the API needs Python with pandas/scikit-learn and a ~160 MB SQLite
database, which exceeds the size limits of Vercel's functions. The API therefore runs as a container on another host, and the web app proxies
`/api/v1/*` to it (same origin for the browser, so no CORS).

**Measured memory (peak resident set, author's machine):** seeding the dataset ~940 MB, training the models ~350 MB, API at run time ~240 MB
(one worker). Seeding and training happen when the image is *built*. A 512 MB host can therefore run the API but may fail to build it.

### Step 1 — the API (container host; `render.yaml` is provided for Render)
**Observed 2026-11-22:** letting Render build the image on its free plan was still running after **42 minutes** (seeding needs ~1 GB of RAM and
training is CPU heavy). So the API image is built once in CI and the host only pulls it.
1. CI (job `docker`) builds the image, smoke-tests it and, on `main`, publishes `ghcr.io/<owner>/digital-mill-lab-api:latest` (and a `:<commit sha>` tag).
   The package is private by default (the repository is private).
2. In Render create a **registry credential** (Workspace Settings → Registry Credentials → GitHub Container Registry): user = your GitHub user name,
   password = a *classic* personal access token with **only** `read:packages`. Name it `ghcr-credentials`. (Alternative with no credential: make the
   package public in GitHub — only if you are happy for the API source inside the image to be public.)
3. Render: *New → Blueprint* → pick the repository (it reads `render.yaml`, `runtime: image`) → Apply. Or *New → Web Service → Existing image* and paste the image URL.
   Prebuilt-image services are **not** auto-deployed: after a new image is published, press *Manual Deploy*.
4. Free plan: 0.1 CPU and 512 MB RAM, sleeps after ~15 minutes idle (about a minute to wake). Expect a slow first page because one page fires 13–20 API
   calls; a paid plan with more CPU is the realistic option for a demo you send to people.
5. Note the service URL, for example `https://digital-mill-lab-api.onrender.com`; check `<url>/health` and `<url>/api/v1/meta`.

### Step 2 — the web app (Vercel)
1. *Add New → Project* → import the repository (grant the Vercel GitHub app access to it).
2. **Root Directory:** `apps/web`. Keep *Include source files outside of the Root Directory* ON (the app needs `packages/contracts` and `docs/`).
   Framework: Next.js. Node.js version: 22.x. Install/build commands: defaults (pnpm is detected).
3. **Environment variable `API_INTERNAL_URL`** = the API URL from step 1 (Production and Preview). It is baked into the build, so set it **before**
   the first deployment; changing it later needs a redeploy.
4. Deploy. `next.config.ts` detects Vercel (`VERCEL=1`), turns off `standalone`, and includes the markdown files the `/docs` pages read
   (`docs/internal` is excluded; verified locally by inspecting the traced file lists).

### After deploying
* Open `/`, `/demo/executive` (data should appear within a few seconds; the very first call can be slow if the API was asleep), run the tour.
* Run the browser tests against the public URL: `E2E_BASE_URL=https://<your-vercel-domain> pnpm --dir tests/e2e exec playwright test` (they create and reset
  their own sandbox sessions).
* Rate limiting is per process and per session; behind the web proxy every visitor shares one client address, so keep `TRUST_PROXY_HEADERS=false`
  (already set in `render.yaml`). `POST /demo/reset-all` is refused when `APP_ENV=demo` (it would let any visitor clear everyone's sandbox).
* Vercel *Deployment Protection* may put preview URLs behind a login; production domains are public. The demo is intended to be public.

### Not verified
Never deployed on Vercel or Render by the author. Unknown until tried: Render's build memory limit, cold-start time, whether the `/docs` pages find their
files inside Vercel's function bundle (configured and checked locally, not on Vercel), and Vercel's handling of the monorepo settings above.
