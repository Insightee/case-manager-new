#!/usr/bin/env bash
# Enable observation/IEP clinical reports on Railway **testing** environment.
# Requires: npx @railway/cli logged in (account token, not project token).
# See docs/RAILWAY_VERCEL.md

set -euo pipefail
cd "$(dirname "$0")/../backend"

echo "→ Switching to Railway testing environment..."
railway environment testing

echo "→ Linking case-manager-new service..."
railway service link case-manager-new

echo "→ Setting ENABLE_CLINICAL_REPORTS_ENGINE=true..."
railway variables --set "ENABLE_CLINICAL_REPORTS_ENGINE=true"

echo "→ Redeploying so migrations + new env take effect..."
railway up --detach || railway redeploy --yes

echo ""
echo "Done. After deploy finishes (~2–3 min), verify:"
echo "  curl -s https://case-manager-new-testing.up.railway.app/api/v1/cases/1/reports/iep/summary"
echo "  (401 Unauthorized = engine ON; 404 'not available' = still off)"
echo ""
echo "Then refresh the IEP builder in the therapist portal."
