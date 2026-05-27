#!/bin/sh
# Link and configure Vercel project insightes-projects/frontend (InsightCase UI).
# Run from repo root after: npx vercel login
# Do not commit .vercel/ or scripts/vercel_env.sh

set -eu

SCOPE="insightes-projects"
PROJECT_NAME="frontend"
API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_ROOT"

if [ -x "$REPO_ROOT/scripts/vercel_clean_backend_env.sh" ]; then
  echo "Removing backend-only env vars from Vercel (if any)..."
  "$REPO_ROOT/scripts/vercel_clean_backend_env.sh" || true
fi

echo "Linking Vercel ($SCOPE / $PROJECT_NAME) at repo root..."
npx vercel link --scope "$SCOPE" --project "$PROJECT_NAME" --yes

echo "Setting VITE_API_URL for production + preview..."
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production --scope "$SCOPE" --force 2>/dev/null \
  || printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production --scope "$SCOPE"
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview --scope "$SCOPE" --force 2>/dev/null \
  || printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview --scope "$SCOPE"

echo ""
echo "Vercel dashboard checklist (Project → Settings → General):"
echo "  Root Directory: (empty) — use root vercel.json"
echo "  OR Root Directory: frontend — then override Install to: npm install --no-audit --no-fund"
echo "  Do NOT use: npm ci --prefix frontend"
echo ""
echo "Deploy: npx vercel --prod --scope $SCOPE"
echo "Production URL: https://frontend-insightes-projects.vercel.app"
echo "Then set Railway FRONTEND_URL + CORS_ORIGINS to that URL."
