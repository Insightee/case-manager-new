#!/bin/sh
# Set Railway FRONTEND_URL + CORS_ORIGINS for insighte.org production (three parallel hosts).
#
# Usage:
#   export RAILWAY_API_TOKEN='...'   # Account → Tokens, Workspace = No workspace
#   chmod +x backend/scripts/railway_set_insighte_domain_cors.sh
#   ./backend/scripts/railway_set_insighte_domain_cors.sh
#
# Or with project token:
#   export RAILWAY_PROJECT_TOKEN='...'
#   python3 backend/scripts/railway_set_insighte_domain_cors.py
set -eu

FRONTEND_URL="${FRONTEND_URL:-https://www.insighte.org}"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,https://www.insighte.org,https://insighte.org,https://frontend-omega-eight-92.vercel.app}"
PROJECT_ID="${RAILWAY_PROJECT_ID:-ead85fb6-1826-4eed-bad9-2513e89c4854}"
BACKEND="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "${RAILWAY_API_TOKEN:-}" ]; then
  echo "Set RAILWAY_API_TOKEN (Account → Tokens, Workspace = No workspace)." >&2
  exit 1
fi
unset RAILWAY_TOKEN

cd "$BACKEND"
npx @railway/cli link --project "$PROJECT_ID" --environment production --service case-manager-new
npx @railway/cli variable set \
  FRONTEND_URL="${FRONTEND_URL%/}" \
  CORS_ORIGINS="$CORS_ORIGINS"

echo "Set FRONTEND_URL=${FRONTEND_URL%/}"
echo "Set CORS_ORIGINS=$CORS_ORIGINS"
echo "Redeploying API..."
npx @railway/cli redeploy --from-source -y -s case-manager-new
