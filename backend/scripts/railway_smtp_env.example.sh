#!/bin/sh
# Copy to railway_smtp_env.sh, fill SMTP_PASSWORD, then run after: railway login
# Prefer railway_link_and_configure.example.sh for full SMTP + CORS setup.
# Do NOT commit railway_smtp_env.sh

set -e
cd "$(dirname "$0")/.."

PROJECT_ID="b5944bdb-23e6-4d32-bf7e-f2eeb9494ca4"
FRONTEND_URL="${FRONTEND_URL:-https://frontend-omega-eight-92.vercel.app}"

npx @railway/cli link --project "$PROJECT_ID"

npx @railway/cli variables set \
  EMAIL_PROVIDER=zeptomail \
  SMTP_HOST=smtp.zeptomail.com \
  SMTP_PORT=587 \
  SMTP_USER=emailapikey \
  SMTP_TLS=true \
  SMTP_FROM_EMAIL=noreply@insighte.in \
  SMTP_FROM_BILLING_EMAIL=billing.noreply@insighte.in \
  SMTP_FROM_VERIFICATION_EMAIL=verification.noreply@insighte.in \
  SMTP_FROM_NAME=Insighte \
  FRONTEND_URL="$FRONTEND_URL" \
  CORS_ORIGINS="http://localhost:5173,${FRONTEND_URL}"

# Set secret separately (prompts or paste once):
# npx @railway/cli variables set SMTP_PASSWORD='YOUR_ZEPTOMAIL_SEND_TOKEN'

echo "Set SMTP_PASSWORD manually, then redeploy the API service."
