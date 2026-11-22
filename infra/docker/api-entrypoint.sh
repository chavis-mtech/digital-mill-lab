#!/bin/sh
# API container entrypoint. STATUS: configured, NOT verified (no Docker daemon in the build environment).
set -e

case "${DATABASE_URL:-}" in
  sqlite*)
    # SQLite: the database was built into the image (seed + ML detections). Nothing to do.
    ;;
  *)
    # External database (e.g. PostgreSQL): create schema, then fill it once. Needs psycopg in the image
    # (see docs/DEPLOYMENT.md); the Postgres path is NOT verified.
    alembic upgrade head
    python -m app.seed --if-empty
    python -m app.ml.train
    ;;
esac

# Several worker processes: a page fires ~20 parallel requests and one worker serialises them (measured by the
# web-verifier and QA). Rate-limit buckets are per process, so the effective limit is WEB_CONCURRENCY times higher.
export SQLITE_WAL="${SQLITE_WAL:-true}"  # several processes share the SQLite file: WAL + busy timeout
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers "${WEB_CONCURRENCY:-3}"
