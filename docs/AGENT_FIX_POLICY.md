# Agent fix policy — surgical patch mode

Canonical reference for Cursor User Rules, per-fix prompts, and test targeting. **Not** loaded as always-on context — paste User Rules into Cursor Settings manually.

**Related:** [CURSOR_RULES.md](./CURSOR_RULES.md) · [`.cursor/rules/`](../.cursor/rules/) · [`.cursor/skills/`](../.cursor/skills/)

---

## Policy

> **One issue → one chat → one target file → one touched function → one exact test selector → one patch.**

**Hard rule:** The agent may not run any test command that can execute more than the touched behaviour unless it explains why first.

---

## Cursor User Rules (paste into Settings)

Copy this block into **Cursor Settings → Rules → User Rules** (replace long rules):

```
You are working on InsighteCase.

Default behaviour:
1. Make the smallest safe diff.
2. Do not commit unless explicitly asked.
3. Do not run full test suites unless explicitly asked.
4. For fixes, identify the touched function/component and run only the smallest matching test function or `-k` selector — never broader without explaining why.
5. Use `pytest -q --tb=line -x` for backend tests (via `./scripts/agent-pytest.sh`).
6. Use targeted frontend/unit tests before Playwright.
7. Do not read large docs, JSONL logs, full test suites, or unrelated files unless blocked.
8. Prefer grep/search → one implementation file → one test file → patch.
9. If a broader change is required, explain why before expanding scope.
10. Preserve InsighteCase doctrine: neuro-affirmative, parent-friendly, audit-safe, billing-safe.
```

After pasting: **Developer: Reload Window**.

---

## Per-fix prompt template

```text
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
```

---

## Backend test command ladder

Use **in order** (narrowest first):

| Tier | Command | When |
|------|---------|------|
| 1 | `./scripts/agent-pytest.sh app/tests/test_foo.py::test_bar` | Exact test known |
| 2 | `./scripts/agent-pytest.sh app/tests/test_foo.py -k "keyword"` | Behaviour keyword only |
| 3 | `./scripts/agent-pytest.sh --allow-file app/tests/test_foo.py` | Rare — agent must explain why in chat first |
| 4 | `./scripts/pre-push-check.sh` or CI | User asks, or before merge/release only |

**Blocked by `agent-pytest.sh`:** bare `pytest`, `pytest app/tests`, `test_file.py` without `::` or `-k`.

**Forbidden in agent chat (unless user explicitly asks):**

- `pytest app/tests`
- bare `pytest`
- Full Playwright suite
- Reading `test_admin_portal.py` unless editing admin portal behaviour
- Reading `docs/sessions/*.jsonl`

**Frontend (before Playwright):**

```bash
cd frontend && npm run test:unit
# or: node --test src/lib/specific.test.js
```

---

## MCP hygiene (configure manually)

Cursor Settings → MCP. Disable servers not needed for the current task. Suggested defaults for daily InsighteCase work:

| Usually off | Enable only when |
|-------------|------------------|
| Supabase, MongoDB | Never (stack is SQLAlchemy + Postgres) |
| Figma | Design-to-code session |
| Notion | Spec sync session |
| Postman, Datadog | API/debug investigation |
| Cloudflare (all) | Workers/R2 debug only |
| Subtext / Higgsfield | Not used |
| Hugging Face | Not used |
| GitLab | If using GitLab remote |

| Optional on | Use for |
|-------------|---------|
| Vercel | Deploy, env, preview URLs |
| GitHub | PR, issues, `gh` workflows |

Reload window after MCP changes.

---

## Plugin skills (configure manually)

`Cmd+Shift+J` → Rules → Skills → disable marketplace skills not needed (Next.js, Supabase, Auth0, etc.).

## Slash skills (manual — name exact skill in prompt)

No router skills (saves tokens). Invoke only what you need:

| Area | Skills |
|------|--------|
| Backend | `/rbac-fix` · `/billing-fix` · `/session-time-fix` · `/attendance-fix` · `/migration-fix` · `/pytest-targeting` |
| Frontend | `/form-fix` · `/table-ui-fix` · `/parent-portal-fix` · `/admin-portal-fix` · `/responsive-ui-fix` |
| Deploy | `/railway-debug` · `/vercel-debug` · `/env-debug` · `/zeptomail-debug` · `/r2-storage-debug` |

**Manual domain `.mdc`** rules (`billing-domain`, `fastapi-api`, etc.) still apply when globs match — kept for safety until validated, then may be deleted.

---

## Humans vs agents

| Actor | Tests before push |
|-------|-------------------|
| **Agent** | `./scripts/agent-pytest.sh` — one `::test_name` or `-k` |
| **Human** | `./scripts/pre-push-check.sh` — full CI parity |

---

## Operating habits

- **New chat** per discrete fix
- **@mention** only the target file
- **Agent mode** for ≤3-file fixes (not Plan mode)
- Paste **last failure line** only, not full pytest output
