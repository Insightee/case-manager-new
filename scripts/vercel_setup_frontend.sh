#!/bin/sh
# Link and configure Vercel project insightes-projects/frontend (InsightCase UI).
# Run from repo root after: npx vercel login
# Do not commit .vercel/ or scripts/vercel_env.sh

set -eu

SCOPE="insightes-projects"
PROJECT_NAME="frontend" # Vercel project name — NOT case-manager-new (that is Railway only)
export VERCEL_SCOPE="$SCOPE"
export VERCEL_PROJECT="$PROJECT_NAME"
API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/scripts/vercel_clean_backend_env_api.py" ]; then
  echo "Removing backend-only env vars from Vercel project frontend (if any)..."
  python3 "$REPO_ROOT/scripts/vercel_clean_backend_env_api.py" || true
fi

echo "Linking Vercel ($SCOPE / $PROJECT_NAME) at repo root..."
npx vercel link --scope "$SCOPE" --project "$PROJECT_NAME" --yes

VC="--scope $SCOPE --project $PROJECT_NAME"
echo "Setting VITE_API_URL for production + preview..."
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production $VC --force 2>/dev/null \
  || printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production $VC
printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview $VC --force 2>/dev/null \
  || printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview $VC

echo ""
echo "Vercel dashboard checklist (Project → Settings → General):"
echo "  Root Directory: (empty) — use root vercel.json"
echo "  OR Root Directory: frontend — then override Install to: npm install --no-audit --no-fund"
echo "  Do NOT use: npm ci --prefix frontend"
echo ""
echo "Deploy: npx vercel --prod --scope $SCOPE"
echo "Production URL: copy from Vercel → Settings → Domains (e.g. https://frontend-omega-eight-92.vercel.app)"
echo "Then set Railway FRONTEND_URL + CORS_ORIGINS to that exact URL (no trailing slash)."
