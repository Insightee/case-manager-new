#!/usr/bin/env bash
# Pre-push quality gate — run from repo root: ./scripts/pre-push-check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> InsightCase pre-push check"
echo ""

if [[ "$(git branch --show-current 2>/dev/null || true)" == "main" ]] || [[ "$(git branch --show-current 2>/dev/null || true)" == "master" ]]; then
  echo "ERROR: You are on 'main'. Create a feature branch before pushing (see CONTRIBUTING.md)."
  exit 1
fi

echo "==> Staged secret / env guard"
"$ROOT/scripts/check_staged_secrets.sh"

echo ""
"$ROOT/scripts/run-ci-parity-checks.sh"

echo ""
echo "OK — safe to push. Open a PR and wait for CI + review (CONTRIBUTING.md)."
