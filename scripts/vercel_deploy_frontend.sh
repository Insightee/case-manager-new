#!/bin/sh
# Preview-deploy this git branch to insightes-projects/frontend (the only Vercel UI).
# API is Railway production. Does not --prod / promote insighte.org.
# Run from repo root after: npx vercel login  (or export VERCEL_TOKEN)

set -eu

SCOPE="insightes-projects"
PROJECT_NAME="frontend"
API_URL="${API_URL:-https://case-manager-new-production.up.railway.app}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROD="${VERCEL_PROD:-0}"

cd "$REPO_ROOT"

echo "Vercel scope=$SCOPE project=$PROJECT_NAME VITE_API_URL=$API_URL"
echo "Official UI only — do not target insightecasestaging or insightecasetesting."

npx vercel link --scope "$SCOPE" --project "$PROJECT_NAME" --yes

VC="--scope $SCOPE --project $PROJECT_NAME"
if npx vercel env ls $VC 2>/dev/null | grep -q 'VITE_API_URL'; then
  echo "VITE_API_URL already set on $PROJECT_NAME"
else
  printf '%s' "$API_URL" | npx vercel env add VITE_API_URL production $VC || true
  printf '%s' "$API_URL" | npx vercel env add VITE_API_URL preview $VC || true
fi

if [ "$PROD" = "1" ]; then
  echo "Promoting production on $PROJECT_NAME (insighte.org)."
  npx vercel --prod --yes $VC
else
  echo "Preview deploy on $PROJECT_NAME (Railway API, not insighte.org)."
  npx vercel --yes $VC
fi
