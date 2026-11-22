# Digital Mill Lab - developer commands.
# Python service: apps/ai-api (venv at apps/ai-api/.venv, Python 3.12).
# Web app: apps/web (Next.js, owned by frontend-foundation; targets skip it if absent).

SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
API_DIR := $(ROOT)/apps/ai-api
VENV := $(API_DIR)/.venv
PY := $(VENV)/bin/python
PYTHON_BOOTSTRAP ?= $(shell command -v /opt/homebrew/bin/python3.12 || command -v python3.12 || echo python3)
API_PORT ?= 8000
WEB_PORT ?= 3000

.PHONY: help setup setup-py setup-node seed demo-data dev dev-api test test-api lint contracts docs models eval migrate clean-venv

help:
	@echo "Targets: setup seed dev test lint contracts docs models eval migrate"

## setup: create the Python venv from the pinned lock file and install node deps (if any)
setup: setup-py setup-node

setup-py:
	@test -x "$(PY)" || $(PYTHON_BOOTSTRAP) -m venv "$(VENV)"
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r "$(API_DIR)/requirements.lock"
	$(PY) -m pip install -q --no-deps -e "$(API_DIR)"
	@$(PY) -c "import fastapi, sqlalchemy, sklearn; print('python env ok:', fastapi.__version__, sqlalchemy.__version__, sklearn.__version__)"

setup-node:
	@if [ -f "$(ROOT)/pnpm-lock.yaml" ] || ls "$(ROOT)"/apps/*/package.json "$(ROOT)"/packages/*/package.json >/dev/null 2>&1; then \
		cd "$(ROOT)" && pnpm install; \
	else echo "no node packages yet - skipping pnpm install"; fi

clean-venv:
	rm -rf "$(VENV)"

## migrate: apply Alembic migrations to DATABASE_URL (default sqlite:///data/demo.db)
migrate:
	cd "$(API_DIR)" && $(PY) -m alembic upgrade head

## seed: build the canonical synthetic dataset (script owned by data-engine)
seed:
	@if [ ! -f "$(API_DIR)/app/seed/__main__.py" ]; then \
		echo "ERROR: seed script missing: apps/ai-api/app/seed/__main__.py (owned by data-engine, not built yet)"; exit 2; fi
	cd "$(API_DIR)" && $(PY) -m app.seed

## models: train + save ML models (owned by ml)
# One command for the demo database: deterministic seed, then train the models and write
# their detections into the SAME database (ML rows live beside the seed rows).
# `make test` skips the ML endpoint tests until this has been run (they need trained models).
# Test fixtures: backend tests pin seed-only semantics (data/dev/seed-only.db); ML / Copilot / QA tests read an ML-trained copy
# (data/dev/ml.db, data/dev/snapshot-with-ml.db). Copies only - tests never write data/demo.db.
demo-data: seed
	mkdir -p "$(ROOT)/data/dev" && cp "$(ROOT)/data/demo.db" "$(ROOT)/data/dev/seed-only.db"
	$(MAKE) models
	cp "$(ROOT)/data/demo.db" "$(ROOT)/data/dev/ml.db"
	cp "$(ROOT)/data/demo.db" "$(ROOT)/data/dev/snapshot-with-ml.db"

models:
	@if [ ! -f "$(API_DIR)/app/ml/train.py" ]; then \
		echo "ERROR: training script missing: apps/ai-api/app/ml/train.py (owned by ml, not built yet)"; exit 2; fi
	cd "$(API_DIR)" && $(PY) -m app.ml.train

## eval: evaluate models + copilot (owned by ml / copilot)
eval:
	@if [ ! -f "$(API_DIR)/app/ml/evaluate.py" ]; then \
		echo "ERROR: evaluation script missing: apps/ai-api/app/ml/evaluate.py (owned by ml, not built yet)"; exit 2; fi
	cd "$(API_DIR)" && $(PY) -m app.ml.evaluate
	@if [ -f "$(API_DIR)/app/copilot/evaluate.py" ]; then cd "$(API_DIR)" && $(PY) -m app.copilot.evaluate; \
	else echo "note: copilot eval (app/copilot/evaluate.py) not built yet - skipped"; fi

## dev: run API (port $(API_PORT)) and web (port $(WEB_PORT)) if present
dev-api:
	cd "$(API_DIR)" && $(PY) -m uvicorn app.main:app --reload --port $(API_PORT)

dev:
	@if [ -f "$(ROOT)/apps/web/package.json" ]; then \
		trap 'kill 0' EXIT; \
		(cd "$(API_DIR)" && $(PY) -m uvicorn app.main:app --reload --port $(API_PORT)) & \
		(cd "$(ROOT)/apps/web" && PORT=$(WEB_PORT) pnpm dev) & \
		wait; \
	else $(MAKE) dev-api; fi

## test: python tests (+ node tests if a web app exists)
test: test-api
	@if [ -f "$(ROOT)/apps/web/package.json" ] && grep -q '"test"' "$(ROOT)/apps/web/package.json"; then \
		cd "$(ROOT)" && pnpm --filter ./apps/web test; \
	else echo "no web tests yet - skipped"; fi

test-api:
	cd "$(API_DIR)" && $(PY) -m pytest -q

## lint: ruff (python) + web lint if present
lint:
	cd "$(API_DIR)" && $(VENV)/bin/ruff check app tests
	@if [ -f "$(ROOT)/apps/web/package.json" ] && grep -q '"lint"' "$(ROOT)/apps/web/package.json"; then \
		cd "$(ROOT)" && pnpm --filter ./apps/web lint; \
	else echo "no web lint yet - skipped"; fi

## contracts: FastAPI OpenAPI -> packages/contracts/openapi.json -> src/api-types.ts
contracts:
	cd "$(API_DIR)" && $(PY) "$(ROOT)/packages/contracts/scripts/export_openapi.py" "$(ROOT)/packages/contracts/openapi.json"
	$(PY) "$(ROOT)/packages/contracts/scripts/gen_api_contract_md.py" "$(ROOT)/packages/contracts/openapi.json" "$(ROOT)/docs/architecture/API_CONTRACT.md"
	@test -d "$(ROOT)/packages/contracts/node_modules/openapi-typescript" || (cd "$(ROOT)" && pnpm install)
	cd "$(ROOT)" && pnpm --filter @dml/contracts run generate
	@test -s "$(ROOT)/packages/contracts/src/api-types.ts" && wc -l "$(ROOT)/packages/contracts/src/api-types.ts"

## docs: regenerate generated architecture docs (DB schema from models, API contract from OpenAPI)
docs: contracts
	cd "$(API_DIR)" && $(PY) -m app.db.schema_doc "$(ROOT)/docs/architecture/DATABASE_SCHEMA.md"
