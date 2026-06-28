#!/usr/bin/env bash
# Print surgical fix prompt template and policy pointers.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cat <<'EOF'
=== InsighteCase surgical fix ===

Paste into Agent chat:

Fix ONLY this issue:

Target: [file/function/component/test name]

Expected behaviour: [one sentence]

Constraints:
- Smallest safe diff.
- grep → one impl file → one test; no repo exploration.
- Run: ./scripts/agent-pytest.sh app/tests/...py::test_name
- No full pytest / Playwright / docs/sessions/*.jsonl.
- If no test exists, add one focused test only.
- Do not commit unless I ask.
- If scope must widen, explain why first.

Full policy: docs/AGENT_FIX_POLICY.md
Slash skills: /backend-router /pytest-targeting /rbac-fix
EOF
