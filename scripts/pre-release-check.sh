#!/usr/bin/env bash
# Pre-release gate — run before production promote: ./scripts/pre-release-check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> InsightCase pre-release check"
echo ""

if ! grep -q '^\## \[Unreleased\]' CHANGELOG.md; then
  echo "ERROR: CHANGELOG.md must contain an [Unreleased] section."
  exit 1
fi

if [[ ! -f CONTRIBUTING.md ]]; then
  echo "ERROR: CONTRIBUTING.md missing."
  exit 1
fi

echo "==> Running CI parity checks (tests + build + alembic)"
"$ROOT/scripts/run-ci-parity-checks.sh"

echo ""
echo "==> Release documentation reminders"
echo "  1. Move CHANGELOG.md [Unreleased] bullets to ## [YYYY-MM-DD]"
echo "  2. Complete docs/RELEASE_CHECKLIST.md (Railway, Vercel, manual smoke)"
echo "  3. Confirm Vercel production domain serves latest deployment"
echo ""
echo "OK — automated release checks passed. Complete manual RELEASE_CHECKLIST before prod."
