#!/usr/bin/env bash
# Cloud Agent dev-environment install for InsighteCase.
#
# Runs local dev on SQLite (no Docker/Postgres/Redis required): the backend
# defaults DATABASE_URL to a local SQLite file and falls back to in-memory
# refresh-token storage when Redis is absent. Idempotent so it can re-run
# after code changes or against a cached/snapshotted workspace.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing backend Python dependencies"
python3 -m pip install --break-system-packages -q -r backend/requirements.txt

echo "==> Seeding demo SQLite database (first run only)"
if [ ! -f backend/insightcase.db ]; then
  (cd backend && python3 -m app.seed.demo_seed)
else
  echo "    backend/insightcase.db already present; skipping seed"
fi

echo "==> Installing frontend npm dependencies"
(cd frontend && npm install)

echo "==> Install complete"
