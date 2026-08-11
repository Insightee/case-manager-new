#!/usr/bin/env bash
# E2E backend: migrate, seed with billing, then serve API (used by Playwright webServer).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-sqlite:///${ROOT}/insightcase.e2e.db}"
export ENABLE_BILLING="${ENABLE_BILLING:-true}"
export LAZY_SQLITE_PATCHES="${LAZY_SQLITE_PATCHES:-false}"

if [ "${RESET_E2E_DB:-1}" = "1" ] && [[ "$DATABASE_URL" == sqlite* ]]; then
  DB_FILE="${DATABASE_URL#sqlite:///}"
  rm -f "$DB_FILE"
fi

alembic upgrade head
python3 -m app.seed.demo_seed

exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
