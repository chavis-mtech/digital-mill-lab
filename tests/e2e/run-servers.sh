#!/usr/bin/env bash
# Start the API (8109) and the production web build (3109) for the e2e suite, on a COPY of the snapshot DB.
# Usage (repo root):  bash tests/e2e/run-servers.sh      then, in another shell:  pnpm --dir tests/e2e test
# Ctrl+C stops both. Never touches data/demo.db.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_PORT="${API_PORT:-8109}"
WEB_PORT="${WEB_PORT:-3109}"
SRC_DB="${E2E_SOURCE_DB:-data/dev/snapshot-with-ml-v2.db}"
DB="data/dev/e2e.db"

cd "$ROOT"
[ -f "$SRC_DB" ] || { echo "missing $SRC_DB (build it with: make demo-data, then copy data/demo.db)"; exit 2; }
cp "$SRC_DB" "$DB"
echo "DB copy: $DB (from $SRC_DB)"

trap 'kill 0' EXIT
# The rate limiter is raised because every browser request reaches the API from the one Next.js proxy address.
(cd apps/ai-api && source .venv/bin/activate && \
  RATE_LIMIT_PER_IP_PER_MINUTE=100000 RATE_LIMIT_PER_SESSION_PER_MINUTE=100000 RATE_LIMIT_BURST=100000 \
  DATABASE_URL="sqlite:///$DB" uvicorn app.main:app --port "$API_PORT") &
if [ "${SKIP_BUILD:-0}" != "1" ]; then API_PORT="$API_PORT" pnpm --filter web build; fi
API_PORT="$API_PORT" pnpm --filter web exec next start -p "$WEB_PORT" &
wait
