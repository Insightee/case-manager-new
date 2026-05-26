#!/bin/sh
# Copy to railway_link_and_configure.sh, set SMTP_PASSWORD, then run from repo root:
#   chmod +x backend/scripts/railway_link_and_configure.sh
#   ./backend/scripts/railway_link_and_configure.sh
# Requires: npx @railway/cli, railway login
# Do NOT commit railway_link_and_configure.sh

set -e

PROJECT_ID="b5944bdb-23e6-4d32-bf7e-f2eeb9494ca4"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$REPO_ROOT/backend"

# Your Vercel production/preview URL (no trailing slash)
VERCEL_URL="${VERCEL_URL:-https://frontend-omega-eight-92.vercel.app}"
# Public Railway API URL — update after `railway domain` if different
API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"

if [ -z "${SMTP_PASSWORD:-}" ]; then
  echo "Set SMTP_PASSWORD (ZeptoMail send token) before running, e.g.:"
  echo "  export SMTP_PASSWORD='your-token'"
  exit 1
fi

cd "$BACKEND"

echo "Linking Railway project ${PROJECT_ID} (service: backend)..."
npx @railway/cli link --project "$PROJECT_ID"

echo "Setting API variables (SMTP + CORS + frontend URL)..."
npx @railway/cli variables set \
  APP_ENV=production \
  SEED_DEMO_DATA=false \
  EMAIL_PROVIDER=zeptomail \
  SMTP_HOST=smtp.zeptomail.com \
  SMTP_PORT=587 \
  SMTP_USER=emailapikey \
  SMTP_PASSWORD="$SMTP_PASSWORD" \
  SMTP_TLS=true \
  SMTP_FROM_EMAIL=noreply@insighte.in \
  SMTP_FROM_BILLING_EMAIL=billing.noreply@insighte.in \
  SMTP_FROM_VERIFICATION_EMAIL=verification.noreply@insighte.in \
  SMTP_FROM_NAME=Insighte \
  FRONTEND_URL="$VERCEL_URL" \
  CORS_ORIGINS="http://localhost:5173,${VERCEL_URL}"

echo ""
echo "Railway API variables set. Still required in Railway dashboard:"
echo "  - DATABASE_URL = \${{Postgres.DATABASE_URL}}"
echo "  - JWT_SECRET_KEY, JWT_REFRESH_SECRET_KEY (random)"
echo "  - STORAGE_PROVIDER=r2 + R2_* keys (if using production storage)"
echo ""
echo "Vercel (frontend project) — set manually or run:"
echo "  cd frontend && npx vercel env add VITE_API_URL production"
echo "  Value: ${API_URL}"
echo ""
echo "Redeploy API and Vercel after changes."
