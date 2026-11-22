# API image. STATUS: built and smoke-tested in GitHub Actions CI (2026-11-22).
# Build from repo root:  docker build -f infra/docker/api.Dockerfile -t dml-api .
#
# The synthetic dataset and the trained models are generated at BUILD time (both are deterministic:
# `python -m app.seed` then `python -m app.ml.train`, ~10 s + ~90 s on a multi-core machine), so the container
# starts instantly and every container serves identical data. Nothing real or private is copied in.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=demo \
    DATABASE_URL=sqlite:///data/demo.db

WORKDIR /srv/app/apps/ai-api

COPY apps/ai-api/requirements.lock ./requirements.lock
RUN pip install -r requirements.lock

COPY apps/ai-api/ ./
# Files the API reads at run time relative to the repo root (REPO_ROOT = /srv/app):
#   data/kb            sample knowledge-base documents (Copilot RAG)
#   docs/ai            model cards served by /ai/model-cards
COPY data/kb /srv/app/data/kb
COPY docs/ai /srv/app/docs/ai
COPY infra/docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh

RUN pip install --no-deps -e . \
    && chmod +x /usr/local/bin/api-entrypoint.sh \
    && mkdir -p /srv/app/data/synthetic /srv/app/data/models /srv/app/data/dev \
    && python -m app.seed \
    && python -m app.ml.train \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser /srv/app

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
