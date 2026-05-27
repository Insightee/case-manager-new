#!/bin/sh
# Diagnose Railway tokens locally. Do not commit tokens.
#
#   export RAILWAY_API_TOKEN='account-token'   # for whoami, link, variable set
#   # OR
#   export RAILWAY_TOKEN='project-token'       # for railway up / CI deploy only
#   sh scripts/verify_railway_token.sh
set -eu

GRAPHQL_URL="https://backboard.railway.com/graphql/v2"

echo "Railway CLI: $(npx -y @railway/cli --version 2>/dev/null || echo unknown)"
echo ""

if [ -n "${RAILWAY_TOKEN:-}" ] && [ -n "${RAILWAY_API_TOKEN:-}" ]; then
  echo "WARNING: Both RAILWAY_TOKEN and RAILWAY_API_TOKEN are set."
  echo "         The CLI prefers RAILWAY_TOKEN — whoami/link may fail unexpectedly."
  echo "         For account commands: unset RAILWAY_TOKEN"
  echo ""
fi

if [ -z "${RAILWAY_TOKEN:-}" ] && [ -z "${RAILWAY_API_TOKEN:-}" ]; then
  echo "Set one of:"
  echo "  RAILWAY_API_TOKEN  — Account → Tokens, Workspace = No workspace (for whoami, link, vars)"
  echo "  RAILWAY_TOKEN      — Project → Settings → Tokens (for deploy/up only; whoami will fail)"
  exit 1
fi

test_account_token() {
  if [ -z "${RAILWAY_API_TOKEN:-}" ]; then
    return 1
  fi
  echo "=== Account token (RAILWAY_API_TOKEN) via API ==="
  resp=$(curl -sS -H "Authorization: Bearer ${RAILWAY_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"query":"query { me { name email } }"}' \
    "$GRAPHQL_URL")
  if echo "$resp" | grep -q '"email"'; then
    echo "API: valid account token"
    echo "$resp" | head -c 200
    echo ""
    echo ""
    echo "=== CLI whoami (needs account token, RAILWAY_TOKEN unset) ==="
    (unset RAILWAY_TOKEN; npx -y @railway/cli whoami) && echo "CLI: whoami OK"
    return 0
  fi
  echo "API: account token rejected or workspace-scoped"
  echo "$resp"
  echo ""
  echo "If you picked a workspace in Account → Tokens, create a new token with"
  echo "Workspace dropdown = No workspace (CLI does not accept workspace-scoped tokens)."
  return 1
}

test_project_token() {
  if [ -z "${RAILWAY_TOKEN:-}" ]; then
    return 1
  fi
  echo "=== Project token (RAILWAY_TOKEN) via API ==="
  resp=$(curl -sS -H "Project-Access-Token: ${RAILWAY_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"query":"query { projectToken { projectId environmentId } }"}' \
    "$GRAPHQL_URL")
  if echo "$resp" | grep -q '"projectId"'; then
    echo "API: valid project token (deploy/up/CI — not for whoami)"
    echo "$resp" | head -c 200
    echo ""
    echo ""
    echo "=== CLI whoami with project token (expected to fail) ==="
    npx -y @railway/cli whoami 2>&1 || true
    echo ""
    echo "This is normal. Use RAILWAY_API_TOKEN (No workspace) for whoami, link, and variable set."
    return 0
  fi
  echo "API: project token invalid or revoked"
  echo "$resp"
  return 1
}

ok=0
if [ -n "${RAILWAY_API_TOKEN:-}" ]; then
  test_account_token && ok=1 || true
  echo ""
fi
if [ -n "${RAILWAY_TOKEN:-}" ]; then
  test_project_token && ok=1 || true
fi

if [ "$ok" -eq 0 ]; then
  echo ""
  echo "No valid token detected. Create a new token in Railway and revoke old ones pasted in chat."
  exit 1
fi

echo ""
echo "Done. Match token type to task:"
echo "  Set env vars / link project  → RAILWAY_API_TOKEN + railway login or whoami"
echo "  Deploy from CI               → RAILWAY_TOKEN + railway up --ci"
