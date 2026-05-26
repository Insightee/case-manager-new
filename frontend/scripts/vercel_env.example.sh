#!/bin/sh
# Set Vercel env for the frontend (no SMTP here).
# Usage: copy to vercel_env.sh, adjust URLs, run from frontend/
#   chmod +x scripts/vercel_env.sh && ./scripts/vercel_env.sh
# Requires: npx vercel login && vercel link (in frontend/)

set -e

API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"

cd "$(dirname "$0")/.."

echo "Setting VITE_API_URL=${API_URL} on Vercel (production + preview)..."
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview

echo "Redeploy: npx vercel --prod"
