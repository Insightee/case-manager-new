#!/bin/sh
# Set Redis + worker + DB pool vars on the Railway API service (login scale).
# Requires: npx @railway/cli, linked project (backend/), RAILWAY_API_TOKEN or railway login
#
# Usage:
#   cd backend
#   export RAILWAY_API_TOKEN='...'   # Account token, Workspace = No workspace
#   sh scripts/railway_set_production_scale.sh
#
# Or with GraphQL project token:
#   export RAILWAY_PROJECT_TOKEN='...'
#   python3 scripts/railway_set_vars_graphql.py   # includes scale vars

set -eu
cd "$(dirname "$0")/.."

WEB_CONCURRENCY="${WEB_CONCURRENCY:-3}"
DB_POOL_SIZE="${DB_POOL_SIZE:-10}"
DB_MAX_OVERFLOW="${DB_MAX_OVERFLOW:-20}"

if [ -n "${RAILWAY_PROJECT_TOKEN:-}" ]; then
  exec python3 scripts/railway_set_vars_graphql.py
fi

if [ -z "${RAILWAY_API_TOKEN:-}" ]; then
  echo "Set RAILWAY_API_TOKEN (account token) or RAILWAY_PROJECT_TOKEN (runs GraphQL script)."
  exit 1
fi
unset RAILWAY_TOKEN

echo "Setting production scale variables on linked Railway service..."
npx @railway/cli variable set \
  "REDIS_URL=\${{Redis.REDIS_URL}}" \
  "WEB_CONCURRENCY=${WEB_CONCURRENCY}" \
  "DB_POOL_SIZE=${DB_POOL_SIZE}" \
  "DB_MAX_OVERFLOW=${DB_MAX_OVERFLOW}"

echo "Done. Redeploy the API service. Peak DB connections ≈ $((WEB_CONCURRENCY * (DB_POOL_SIZE + DB_MAX_OVERFLOW)))."
