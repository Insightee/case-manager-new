#!/usr/bin/env bash
# Surgical pytest for agents — ::test_name or -k required.
# Usage from repo root:
#   ./scripts/agent-pytest.sh app/tests/test_foo.py::test_bar
#   ./scripts/agent-pytest.sh app/tests/test_foo.py -k "keyword"
#   ./scripts/agent-pytest.sh --allow-file app/tests/test_foo.py  # rare; explain in chat first
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
ALLOW_FILE=0
PYTEST_ARGS=()

for arg in "$@"; do
  if [[ "$arg" == "--allow-file" ]]; then
    ALLOW_FILE=1
    continue
  fi
  PYTEST_ARGS+=("$arg")
done

if [[ ${#PYTEST_ARGS[@]} -lt 1 ]]; then
  echo "Usage: $0 app/tests/test_file.py::test_name" >&2
  echo "       $0 app/tests/test_file.py -k keyword" >&2
  echo "       $0 --allow-file app/tests/test_file.py  # only after explaining why in chat" >&2
  echo "Forbidden: pytest, pytest app/tests (use pre-push-check.sh for full suite)" >&2
  exit 1
fi

for arg in "${PYTEST_ARGS[@]}"; do
  if [[ "$arg" == "app/tests" ]] || [[ "$arg" == "app/tests/" ]]; then
    echo "ERROR: Full suite forbidden. Use ./scripts/pre-push-check.sh or pass ::test_name / -k." >&2
    exit 1
  fi
  if [[ "$arg" == "pytest" ]] || [[ "$arg" == *"/app/tests" ]] && [[ "$arg" != *"::"* ]]; then
    if [[ "$arg" == "app/tests" ]] || [[ "$arg" == "app/tests/" ]]; then
      echo "ERROR: Full suite forbidden." >&2
      exit 1
    fi
  fi
done

joined="${PYTEST_ARGS[*]}"
if [[ "$joined" != *"::"* ]] && [[ "$joined" != *"-k"* ]]; then
  if [[ "$ALLOW_FILE" -eq 0 ]]; then
    echo "ERROR: Require ::test_name or -k. Bare test file blocked." >&2
    echo "       ./scripts/agent-pytest.sh app/tests/test_foo.py::test_bar" >&2
    echo "       Or use --allow-file after explaining why broader scope is needed." >&2
    exit 1
  fi
fi

cd "$BACKEND"
export PYTHONPATH=".:alembic"

exec python3 -m pytest "${PYTEST_ARGS[@]}" -q --tb=line -x --no-header
