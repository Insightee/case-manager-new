#!/usr/bin/env bash
# Publish local main to https://github.com/Insightee/case-manager-new
set -euo pipefail

REPO_URL="https://github.com/Insightee/case-manager-new.git"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT"

echo "==> Checking GitHub access to Insightee/case-manager-new..."
if ! gh api repos/Insightee/case-manager-new --jq '.permissions.push' 2>/dev/null | grep -q true; then
  echo ""
  echo "ERROR: Your GitHub user does not have push access to Insightee/case-manager-new."
  echo ""
  echo "Ask an Insightee org admin to:"
  echo "  1. Open https://github.com/Insightee/case-manager-new/settings/access"
  echo "  2. Add your GitHub user (midhunnoble) with Write or Maintain role"
  echo ""
  echo "Then re-run this script."
  exit 1
fi

echo "==> Refreshing git credentials (repo scope)..."
gh auth setup-git

echo "==> Pushing main to origin..."
git push origin main

echo ""
echo "Done. Repository:"
echo "  https://github.com/Insightee/case-manager-new"
echo ""
echo "Next: connect Vercel (root directory: frontend) — see docs/DEPLOY.md"
