#!/bin/sh
# Set Railway FRONTEND_URL + CORS_ORIGINS for the live Vercel domain (no SMTP changes).
# Usage:
#   export VERCEL_URL='https://frontend-omega-eight-92.vercel.app'
#   export RAILWAY_API_TOKEN='...'   # Account token, workspace = No workspace
#   chmod +x backend/scripts/railway_set_frontend_cors.sh
#   ./backend/scripts/railway_set_frontend_cors.sh
set -eu

VERCEL_URL="${VERCEL_URL:-https://frontend-omega-eight-92.vercel.app}"
VERCEL_URL="${VERCEL_URL%/}"
PROJECT_ID="${RAILWAY_PROJECT_ID:-ead85fb6-1826-4eed-bad9-2513e89c4854}"
BACKEND="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "${RAILWAY_API_TOKEN:-}" ]; then
  echo "Set RAILWAY_API_TOKEN (Account → Tokens, Workspace = No workspace)." >&2
  exit 1
fi
unset RAILWAY_TOKEN

cd "$BACKEND"
npx @railway/cli link --project "$PROJECT_ID"
npx @railway/cli variable set \
  FRONTEND_URL="$VERCEL_URL" \
  CORS_ORIGINS="http://localhost:5173,${VERCEL_URL}"

echo "Set FRONTEND_URL=$VERCEL_URL"
echo "Set CORS_ORIGINS=http://localhost:5173,${VERCEL_URL}"
echo "Redeploy the API service on Railway for changes to take effect."
