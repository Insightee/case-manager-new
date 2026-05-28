#!/bin/sh
# Remove backend-only variables mistakenly set on Vercel frontend (they belong on Railway only).
#
# Vercel UI project (NOT the GitHub repo name, NOT Railway):
#   Team:   insightes-projects
#   Project: frontend  (prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN)
#
# Railway API service is case-manager-new — never run vercel env against that name.
#
# Usage (repo root):
#   export VERCEL_TOKEN=...
#   python3 scripts/vercel_clean_backend_env_api.py   # preferred (fast, always --project frontend)
#   # or: VERCEL_SCOPE=insightes-projects VERCEL_PROJECT=frontend sh scripts/vercel_clean_backend_env.sh

set -e

SCOPE="${VERCEL_SCOPE:-insightes-projects}"
PROJECT="${VERCEL_PROJECT:-frontend}"

if [ "$PROJECT" = "case-manager-new" ]; then
  echo "ERROR: Vercel project must be 'frontend', not 'case-manager-new' (that name is Railway/API only)." >&2
  exit 1
fi

VERCEL_ARGS="--scope $SCOPE --project $PROJECT"

run_vercel() {
  if command -v vercel >/dev/null 2>&1; then
    vercel "$@"
  else
    npx --yes vercel@latest "$@"
  fi
}

BACKEND_VARS="
R2_SECRET_ACCESS_KEY
R2_ACCESS_KEY_ID
R2_ENDPOINT_URL
R2_BUCKET_NAME
R2_ACCOUNT_ID
STORAGE_ENVIRONMENT
STORAGE_PREFIX
STORAGE_PROVIDER
SMTP_FROM_NAME
SMTP_FROM_EMAIL
SMTP_FROM_BILLING_EMAIL
SMTP_FROM_VERIFICATION_EMAIL
SMTP_TLS
SMTP_USER
SMTP_PASSWORD
SMTP_PORT
SMTP_HOST
PGDATABASE
PGHOST
PGPORT
PGUSER
PGPASSWORD
PGDATA
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
SSL_CERT_DAYS
RAILWAY_DEPLOYMENT_DRAINING_SECONDS
JWT_REFRESH_SECRET_KEY
JWT_SECRET_KEY
DATABASE_PUBLIC_URL
DATABASE_URL
EMAIL_PROVIDER
SEED_DEMO_DATA
APP_ENV
FRONTEND_URL
CORS_ORIGINS
"

echo "Cleaning backend env vars on Vercel: $SCOPE / $PROJECT"
for name in $BACKEND_VARS; do
  run_vercel env rm "$name" production $VERCEL_ARGS --yes >/dev/null 2>&1 && echo "removed $name (production)" || true
  run_vercel env rm "$name" preview $VERCEL_ARGS --yes >/dev/null 2>&1 && echo "removed $name (preview)" || true
done

echo "Done. Only VITE_API_URL should remain on $SCOPE/$PROJECT (plus Vercel system vars)."
