#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="/app:/app/alembic:${PYTHONPATH:-}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is required in production. Add Postgres and reference \${{Postgres.DATABASE_URL}} on this service."
  exit 1
fi

echo "Running migrations..."
python scripts/migrate_production.py

echo "Seeding demo data (idempotent)..."
python -m app.seed.demo_seed

PORT="${PORT:-8000}"
echo "Starting API on port ${PORT}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
