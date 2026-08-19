# Enable observation/IEP clinical reports on Railway **testing** environment.
# Requires: railway CLI logged in (account token). See docs/RAILWAY_VERCEL.md

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\backend")

Write-Host "-> Switching to Railway testing environment..."
railway environment testing

Write-Host "-> Linking case-manager-new service..."
railway service link case-manager-new

Write-Host "-> Setting ENABLE_CLINICAL_REPORTS_ENGINE=true..."
railway variables --set "ENABLE_CLINICAL_REPORTS_ENGINE=true"

Write-Host "-> Redeploying..."
try {
  railway up --detach
} catch {
  railway redeploy --yes
}

Write-Host ""
Write-Host "Done. After deploy finishes (~2-3 min), verify:"
Write-Host "  Invoke-WebRequest https://case-manager-new-testing.up.railway.app/api/v1/cases/1/reports/iep/summary"
Write-Host "  (401 = engine ON; 404 'not available' = still off)"
Write-Host ""
Write-Host "Then refresh the IEP builder in the therapist portal."
