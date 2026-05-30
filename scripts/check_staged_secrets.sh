#!/usr/bin/env bash
# Block committing .env secrets and common key material. Used by pre-commit and CI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0

check_names() {
  local names="$1"
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    case "$f" in
      *.env.example|*/env.railway.example|*/vercel-env.example|*/vercel_env.example.sh|*/railway_smtp_env.example.sh)
        continue
        ;;
      *.env|*.env.local|*.env.production|*.env.development|.env*)
        echo "BLOCKED: do not commit env file: $f"
        fail=1
        ;;
    esac
  done <<< "$names"
}

if git rev-parse --git-dir >/dev/null 2>&1; then
  if [[ "${1:-}" == "--ci" ]]; then
    base="${GITHUB_BASE_REF:-}"
    if [[ -n "$base" ]] && git rev-parse "origin/${base}" >/dev/null 2>&1; then
      names="$(git diff --name-only "origin/${base}...HEAD" 2>/dev/null || true)"
      diff_range="origin/${base}...HEAD"
    else
      # Push to main or workflow_dispatch: scan latest commit
      names="$(git diff --name-only HEAD~1...HEAD 2>/dev/null || true)"
      diff_range="HEAD~1...HEAD"
    fi
    export INSIGHTCASE_DIFF_RANGE="$diff_range"
    check_names "$names"
  else
    # Pre-commit: staged files only
    names="$(git diff --cached --name-only --diff-filter=ACM || true)"
    check_names "$names"
  fi
fi

# Pattern scan on staged or CI diff content (skip examples)
scan_content() {
  local diff_cmd=("$@")
  if "${diff_cmd[@]}" 2>/dev/null | grep -Ei '(JWT_SECRET_KEY=|SMTP_PASSWORD=|RAILWAY_TOKEN=|VERCEL_TOKEN=|BEGIN (RSA |OPENSSH )?PRIVATE KEY)' | grep -v '.example' | grep -qv 'your-'; then
    echo "BLOCKED: possible secret in diff (JWT/SMTP/token/private key)"
    fail=1
  fi
}

if [[ "${1:-}" == "--ci" ]]; then
  range="${INSIGHTCASE_DIFF_RANGE:-HEAD~1...HEAD}"
  scan_content git diff "$range"
else
  scan_content git diff --cached
fi

if [[ "$fail" -ne 0 ]]; then
  echo "See CONTRIBUTING.md and docs/ENVIRONMENT_VARIABLES.md"
  exit 1
fi

exit 0
