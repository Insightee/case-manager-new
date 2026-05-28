#!/bin/sh
# Copy to railway_link_and_configure.sh, set SMTP_PASSWORD, then run from repo root:
#   chmod +x backend/scripts/railway_link_and_configure.sh
#   ./backend/scripts/railway_link_and_configure.sh
# Requires: npx @railway/cli, railway login
# Do NOT commit railway_link_and_configure.sh

set -e

PROJECT_ID="ead85fb6-1826-4eed-bad9-2513e89c4854"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$REPO_ROOT/backend"

# Your Vercel production URL (no trailing slash)
# Vercel: insightes-projects/frontend (prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN) — copy production domain from Vercel → Settings → Domains
VERCEL_URL="${VERCEL_URL:-https://frontend-insightes-projects.vercel.app}"
# Public Railway API URL
API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"

if [ -z "${RAILWAY_API_TOKEN:-}" ]; then
  echo "Set RAILWAY_API_TOKEN (Account → Tokens, Workspace = No workspace)."
  echo "Project tokens (RAILWAY_TOKEN) cannot run whoami, link, or variable set."
  exit 1
fi
unset RAILWAY_TOKEN

if [ -z "${SMTP_PASSWORD:-}" ]; then
  echo "Set SMTP_PASSWORD (ZeptoMail SMTP send token, not REST API key):"
  echo "  export SMTP_PASSWORD='...'"
  exit 1
fi

cd "$BACKEND"

echo "Checking Railway auth (account token only)..."
npx @railway/cli whoami || {
  echo "whoami failed — use Account → Tokens with Workspace = No workspace, as RAILWAY_API_TOKEN."
  exit 1
}

echo "Linking Railway project ${PROJECT_ID}..."
npx @railway/cli link --project "$PROJECT_ID"

echo "Setting API variables..."
npx @railway/cli variable set \
  APP_ENV=production \
  SEED_DEMO_DATA=false \
  EMAIL_PROVIDER=zeptomail \
  SMTP_HOST=smtp.zeptomail.com \
  SMTP_PORT=587 \
  SMTP_USER=emailapikey \
  SMTP_PASSWORD="$SMTP_PASSWORD" \
  SMTP_TLS=true \
  SMTP_FROM_EMAIL=noreply@insighte.in \
  SMTP_FROM_NAME=Insighte \
  FRONTEND_URL="$VERCEL_URL" \
  CORS_ORIGINS="http://localhost:5173,${VERCEL_URL}" \
  STORAGE_PROVIDER=r2 \
  STORAGE_PREFIX=insightcase \
  STORAGE_ENVIRONMENT=production \
  R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-0409ea66ef188ae9783c5e9aa7af9445}" \
  R2_BUCKET_NAME="${R2_BUCKET_NAME:-insightecase}" \
  R2_ENDPOINT_URL="${R2_ENDPOINT_URL:-https://0409ea66ef188ae9783c5e9aa7af9445.r2.cloudflarestorage.com}" \
  WEB_CONCURRENCY="${WEB_CONCURRENCY:-3}" \
  DB_POOL_SIZE="${DB_POOL_SIZE:-10}" \
  DB_MAX_OVERFLOW="${DB_MAX_OVERFLOW:-20}"

if [ -n "${R2_ACCESS_KEY_ID:-}" ] && [ -n "${R2_SECRET_ACCESS_KEY:-}" ]; then
  npx @railway/cli variable set \
    R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
    R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
else
  echo "Skip R2 keys — set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY in dashboard (R2 → Manage R2 API tokens)."
fi

echo ""
echo "Still set in Railway dashboard if not using references:"
echo "  - DATABASE_URL = \${{Postgres.DATABASE_URL}}"
echo "  - REDIS_URL = \${{Redis.REDIS_URL}} (required in production)"
echo "  - WEB_CONCURRENCY, DB_POOL_SIZE, DB_MAX_OVERFLOW (set above unless overridden)"
echo "  - JWT_SECRET_KEY, JWT_REFRESH_SECRET_KEY (long random strings)"
echo "  - Delete legacy names: SMTP_USERNAME, EMAIL_FROM_DEFAULT"
echo ""
echo "Vercel (frontend project) — set manually or run:"
echo "  cd frontend && npx vercel env add VITE_API_URL production"
echo "  Value: ${API_URL}"
echo ""
echo "Redeploy API and Vercel after changes."
