#!/usr/bin/env bash
# Shared test/build gate (no branch check) — used by pre-release-check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Alembic single head"
(
  cd backend
  PYTHONPATH=.:alembic python3 -m alembic heads | tee /tmp/alembic_heads.txt
  count="$(grep -c '(head)' /tmp/alembic_heads.txt || true)"
  if [[ "$count" -ne 1 ]]; then
    echo "ERROR: Expected exactly one Alembic head, found $count"
    exit 1
  fi
)

echo ""
echo "==> Backend tests (full suite)"
( cd backend && python3 -m pytest app/tests -q --tb=line )

echo ""
echo "==> Frontend production build"
( cd frontend && npm run build )

echo ""
echo "OK — tests and build passed."
