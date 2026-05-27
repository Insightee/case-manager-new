#!/bin/sh
# Remove backend-only variables mistakenly set on Vercel frontend (they belong on Railway only).
# Run from repo root after vercel link to insightes-projects/frontend.
set -eu

SCOPE="${VERCEL_SCOPE:-insightes-projects}"

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
SMTP_TLS
SMTP_USER
SMTP_PASSWORD
SMTP_PORT
SMTP_HOST
PGDATABASE
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

for name in $BACKEND_VARS; do
  npx vercel env rm "$name" production --scope "$SCOPE" --yes 2>/dev/null && echo "removed $name (production)" || true
  npx vercel env rm "$name" preview --scope "$SCOPE" --yes 2>/dev/null && echo "removed $name (preview)" || true
done

echo "Keep only VITE_API_URL on Vercel. Backend secrets stay on Railway."
