#!/usr/bin/env bash
# Objective DONE gate for a grind work package.
# Scoped on purpose: run-ci-parity-checks.sh runs the FULL pytest suite, which is
# unusable as a loop gate while unrelated WIP is in the tree.
#
# Usage from repo root:
#   ./scripts/grind-check.sh frontend
#   ./scripts/grind-check.sh backend app/tests/test_billing_step6.py -k monthly
#   ./scripts/grind-check.sh both app/tests/test_billing_step6.py::test_full_month_flat
#
# backend/both require explicit test selectors — agent-pytest.sh rejects bare files.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCOPE="${1:-}"
shift || true
SELECTORS=("$@")
failed=()

case "$SCOPE" in
  frontend|backend|both) ;;
  *)
    echo "Usage: $0 <frontend|backend|both> [pytest selectors...]" >&2
    exit 2
    ;;
esac

run_step() {
  local label="$1"
  shift
  echo ""
  echo "==> $label"
  if "$@"; then
    echo "    ok: $label"
  else
    echo "    FAILED: $label"
    failed+=("$label")
  fi
}

if [[ "$SCOPE" == "backend" || "$SCOPE" == "both" ]]; then
  if [[ ${#SELECTORS[@]} -eq 0 ]]; then
    echo "ERROR: $SCOPE scope needs pytest selectors (::test_name or -k)." >&2
    echo "       The frozen finance selector list lives in docs/plans/finance-dashboard-revamp.md" >&2
    exit 2
  fi

  run_step "Alembic single head" bash -c '
    cd backend
    PYTHONPATH=.:alembic python3 -m alembic heads > /tmp/grind_alembic_heads.txt 2>&1 || exit 1
    count="$(grep -c "(head)" /tmp/grind_alembic_heads.txt || true)"
    if [[ "$count" -ne 1 ]]; then
      echo "Expected exactly one Alembic head, found $count"
      cat /tmp/grind_alembic_heads.txt
      exit 1
    fi
  '

  run_step "Targeted backend tests" ./scripts/agent-pytest.sh "${SELECTORS[@]}"
fi

if [[ "$SCOPE" == "frontend" || "$SCOPE" == "both" ]]; then
  run_step "Frontend unit tests" bash -c 'cd frontend && npm run test:unit'
  run_step "Frontend lint" bash -c 'cd frontend && npm run lint'
  run_step "Frontend build" bash -c 'cd frontend && npm run build'
fi

echo ""
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "GRIND-CHECK FAIL ($SCOPE): ${failed[*]}"
  exit 1
fi
echo "GRIND-CHECK PASS ($SCOPE)"
