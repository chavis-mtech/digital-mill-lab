# Digital Mill Lab — Intelligent Operations & AI Transformation

**Independent portfolio / concept demo. Not an official system of any company, not affiliated with or endorsed by any company.
All plant, supplier and production data is synthetic (deterministically generated). No internal company data is used.**

A working demo of an industrial-intelligence platform for a palm-oil mill: executive control tower, process digital twin,
maintenance AI with work orders, logistics queue analysis, energy, traceability, ROI/scenario simulator and a grounded
Copilot — all computed by one Python API from a 120-day synthetic dataset with embedded scenario episodes. The AI is
advisory and read-only: it never controls machines, and roles are simulated viewpoints, not real accounts.

What this demo is **not**: it is not connected to any real system, its public deployment runs on free tiers (slow; a rate-limit fix awaits a redeploy; live demo: https://digital-mill-lab-web.vercel.app), several models do not beat
their naive baselines (and say so), and the CI and Docker images were built and smoke-tested on GitHub Actions (PostgreSQL is not verified). See
[docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Quick start (local, macOS / Linux)

Prerequisites (check them first):

```bash
python3.12 --version   # Python 3.12.x (on macOS/Homebrew: /opt/homebrew/bin/python3.12)
node --version         # Node >= 20
pnpm --version         # pnpm 11 (corepack enable, or npm i -g pnpm)
make --version         # GNU make
```

Then, from the repository root:

```bash
make setup        # Python venv (apps/ai-api/.venv) from requirements.lock + pnpm install          (~1 min)
make demo-data    # build data/demo.db: deterministic seed, then train the ML models into it      (~2-7 min)
make test         # API test suite (pytest) + web unit tests (vitest)                             (~2-3 min)
make dev          # API on http://localhost:8000 + web on http://localhost:3000
```

Open http://localhost:3000 (Thai UI by default; language switch in the header) and the API docs at http://localhost:8000/docs.

Other ports: `make dev API_PORT=8120 WEB_PORT=3120` (the web app proxies `/api/v1/*` to `API_PORT`).
No `.env` is needed; copy `.env.example` to `.env` only to override defaults. The Copilot runs without any API key
(`LLM_PROVIDER=none`, deterministic mode).

Times measured from a clean copy on the build machine (see "README verification" below); a first `pnpm install` without a warm
package cache and a busy machine take longer. `make demo-data` also keeps test fixtures in `data/dev/` (git-ignored, ~0.5 GB).

## Commands

| Command | What it does |
|---|---|
| `make setup` | Creates `apps/ai-api/.venv` (Python 3.12) from `requirements.lock`, installs the API package, runs `pnpm install` |
| `make demo-data` | `make seed` + `make models`: builds `data/demo.db` and writes ML detections into the same file |
| `make seed` | Deterministic synthetic dataset only (`python -m app.seed`), validated against `data/synthetic/MANIFEST.json` |
| `make models` | Train + evaluate the ML models, write anomaly events / alerts / predictions into `DATABASE_URL` |
| `make test` | `pytest` for the API (ML/QA suites need `make demo-data` first, else they skip) + `vitest` for the web app |
| `make lint` | `ruff` (API) + `eslint` (web) |
| `make dev` | API (uvicorn, reload) + Next.js dev server; `make dev-api` runs only the API |
| `make eval` | Model evaluation report + Copilot evaluation (`docs/MODEL_EVALUATION.md`, `docs/ai/COPILOT_EVALUATION.md`) |
| `make migrate` | Alembic migrations on `DATABASE_URL` (default `sqlite:///data/demo.db`) |
| `make contracts` / `make docs` | Regenerate OpenAPI -> TypeScript types and the generated architecture docs (maintainers) |

Reset the demo data at any time with `make demo-data` (rebuilds `data/demo.db`). Visitor changes (work orders, approvals)
live in per-browser sandbox sessions and can be reset from the UI or `POST /api/v1/demo/session/reset`.

## Project map

```
apps/ai-api/          FastAPI service: all analytics, rules, ML, Copilot (Python 3.12, SQLAlchemy 2, scikit-learn)
  app/api/v1/         REST endpoints (97 operations)        app/services/   KPI, maintenance, logistics, ROI, ...
  app/ml/             training, evaluation, inference       app/copilot/    tool router, safety, RAG, evaluation
  app/seed/           synthetic data engine                 tests/          pytest (unit, module, security, integration)
apps/web/             Next.js App Router UI (TypeScript, Tailwind, ECharts); proxies /api/v1 to the API
packages/contracts/   generated OpenAPI + TypeScript API types
data/kb/              sample knowledge-base documents for the Copilot (fictional)
data/models/          trained model artifacts (rebuilt by make models)
data/synthetic/       dataset manifest (checksum, episode windows)
infra/docker/         Dockerfiles + compose (images built and smoke-tested in CI; the compose file itself was not run)
.github/workflows/    CI (all jobs green on GitHub, 2026-11-22)
docs/                 product, architecture, AI, security and portfolio documentation
```

## Status (2026-11-22)

| Area | Status |
|---|---|
| Synthetic data engine, 6 scenario episodes, validation (58 checks) | implemented |
| API: 97 operations, simulated roles, session sandbox, audit hash chain | implemented (95 implemented, 2 prototype) |
| Executive, digital twin, maintenance + work orders, logistics, energy, traceability, ROI, scenarios | implemented |
| ML: anomaly detection, forecasts, failure-risk ranking | implemented; OER, energy and arrival forecasts do **not** beat baselines |
| Copilot (deterministic router, grounded answers, refusals) | implemented; LLM mode never run against a real provider |
| CV FFB grading | prototype (no dataset, no accuracy) |
| Docker images, CI | built and passing on GitHub Actions (2026-11-22); docker-compose file and PostgreSQL not verified |
| Public deployment | live on free tiers since 2026-11-23: web on Vercel, API on Render; public-URL e2e not run; rate-limit fix committed, not yet verified there ([DEPLOYMENT](docs/DEPLOYMENT.md) section 11) |

Test evidence and open defects: [SECURITY](docs/SECURITY.md) and [KNOWN_LIMITATIONS](docs/KNOWN_LIMITATIONS.md).

## Documentation

* Product and business: [PROJECT_VISION](docs/PROJECT_VISION.md), [PRODUCT_REQUIREMENTS](docs/PRODUCT_REQUIREMENTS.md),
  [BUSINESS_PROPOSAL](docs/BUSINESS_PROPOSAL.md), [IMPLEMENTATION_ROADMAP](docs/IMPLEMENTATION_ROADMAP.md)
* Architecture: [SYSTEM_ARCHITECTURE](docs/architecture/SYSTEM_ARCHITECTURE.md), [DOMAIN_MODEL](docs/architecture/DOMAIN_MODEL.md),
  [DATABASE_SCHEMA](docs/architecture/DATABASE_SCHEMA.md), [API_CONTRACT](docs/architecture/API_CONTRACT.md) (generated),
  [DECISIONS](docs/DECISIONS.md) (ADRs)
* Data and AI: [DATA_GENERATION](docs/DATA_GENERATION.md), [AI_MODELS](docs/AI_MODELS.md), [MODEL_EVALUATION](docs/MODEL_EVALUATION.md),
  [Copilot](docs/ai/copilot.md), [Copilot evaluation](docs/ai/COPILOT_EVALUATION.md)
* Operations: [API_DOCUMENTATION](docs/API_DOCUMENTATION.md), [SECURITY](docs/SECURITY.md), [DEPLOYMENT](docs/DEPLOYMENT.md),
  [KNOWN_LIMITATIONS](docs/KNOWN_LIMITATIONS.md)
* Portfolio: [TECHNICAL_CASE_STUDY](docs/TECHNICAL_CASE_STUDY.md), [docs/portfolio/](docs/portfolio/)

## README verification

Last verified 2026-11-22 by following this README literally in a fresh copy of the repository without `.venv`, `node_modules`,
`.next`, `data/dev`, `*.db` or `docs/internal` (git-ignored paths removed), on macOS (Apple silicon), Python 3.12.13, Node 25.9, pnpm 11.0,
GNU make 3.81, other workloads running:

| Step | Result |
|---|---|
| prerequisites | all four commands present |
| `make setup` | exit 0, 40 s (warm pnpm cache) |
| `make demo-data` | exit 0, 141 s (395 s on a first attempt while the machine was heavily loaded); 8 models, 163 anomaly events, 64 ML alerts, 18,610 predictions |
| `make test` | exit 0, 140 s: pytest **1136 passed, 2 skipped** (opt-in full-seed test; empty stub parameter set), vitest **75 passed** |
| `make dev API_PORT=8120 WEB_PORT=3120` | both servers up in ~3 s; `GET :8120/api/v1/meta` 200; web `/` 200 (title and synthetic-data notice present); `/api/v1/meta` through the web proxy 200; `/demo/executive` 200 |

The first clean-copy attempt failed `make test` (5 failed, 67 skipped): backend tests assumed a seed-only `data/demo.db` while `make demo-data`
writes ML rows into it, and ML/Copilot/QA tests looked for developer-only snapshot files. Fixed in the `Makefile` (`demo-data` keeps
`data/dev/seed-only.db` and ML-trained copies for the tests) and the test fixtures; the run above is the re-run from a fresh copy.
