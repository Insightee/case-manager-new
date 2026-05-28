#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="/app:/app/alembic:${PYTHONPATH:-}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is required in production. Add Postgres and reference \${{Postgres.DATABASE_URL}} on this service."
  exit 1
fi

if [ "${APP_ENV:-}" = "production" ] && { [ "${SEED_DEMO_DATA:-false}" = "true" ] || [ "${SEED_DEMO_DATA:-false}" = "1" ]; }; then
  echo "ERROR: SEED_DEMO_DATA must be false or unset when APP_ENV=production (demo seed can block health checks)."
  exit 1
fi

echo "Running migrations..."
python scripts/migrate_production.py

if [ "${SEED_DEMO_DATA:-false}" = "true" ] || [ "${SEED_DEMO_DATA:-false}" = "1" ]; then
  echo "SEED_DEMO_DATA is set — running demo seed (idempotent)..."
  python -m app.seed.demo_seed
else
  echo "Skipping demo seed (set SEED_DEMO_DATA=true only for demos/staging)."
fi

if [ "${APP_ENV:-}" = "production" ] && [ -z "${REDIS_URL:-}" ]; then
  echo "ERROR: REDIS_URL is required in production. Add a Redis plugin and set REDIS_URL=\${{Redis.REDIS_URL}}."
  exit 1
fi

PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"
POOL_SIZE="${DB_POOL_SIZE:-10}"
POOL_OVERFLOW="${DB_MAX_OVERFLOW:-20}"
MAX_DB_CONNS=$((WORKERS * (POOL_SIZE + POOL_OVERFLOW)))
echo "Starting API on port ${PORT} with ${WORKERS} worker(s)..."
echo "DB pool per worker: size=${POOL_SIZE} max_overflow=${POOL_OVERFLOW} (peak ~${MAX_DB_CONNS} connections)"
if [ "${MAX_DB_CONNS}" -gt 80 ]; then
  echo "WARN: peak DB connections (${MAX_DB_CONNS}) is high — lower WEB_CONCURRENCY or pool sizes if Postgres max_connections is ~97."
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${WORKERS}"
