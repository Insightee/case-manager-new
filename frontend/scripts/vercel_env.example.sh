#!/bin/sh
# Set Vercel env for insightes-projects/frontend (no SMTP here).
# Prefer: ../scripts/vercel_setup_frontend.sh from repo root (links + env).
# Usage: copy to vercel_env.sh, run from frontend/

set -eu

SCOPE="${VERCEL_SCOPE:-insightes-projects}"
API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"

cd "$(dirname "$0")/.."

echo "Setting VITE_API_URL=${API_URL} on Vercel ($SCOPE)..."
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production --scope "$SCOPE" --force 2>/dev/null \
  || printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production --scope "$SCOPE"
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview --scope "$SCOPE" --force 2>/dev/null \
  || printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview --scope "$SCOPE"

echo "Redeploy from repo root: npx vercel --prod --scope $SCOPE"
