# Cursor rules — surgical patch agent

**Policy:** one issue → one chat → one file → one function → one test selector → one patch.

| Doc | Purpose |
|-----|---------|
| [AGENT_FIX_POLICY.md](./AGENT_FIX_POLICY.md) | User Rules, fix prompt, skill list, MCP checklist |
| [`.cursor/rules/`](../.cursor/rules/) | 4 always-on + 8 manual domain `.mdc` |
| [`.cursor/skills/`](../.cursor/skills/) | Slash sub-skills only (no routers) |

**Verify:** `./.cursor/verify-rules.sh` · **Agent pytest:** `./scripts/agent-pytest.sh`

---

## 1. Paste User Rules (once per machine)

Open **Cursor Settings** (`Cmd+Shift+J`) → **Rules** → **User Rules**.

Copy from [AGENT_FIX_POLICY.md § User Rules](./AGENT_FIX_POLICY.md#cursor-user-rules-paste-into-settings). Replace long commit/PR/prose rules.

---

## 2. Project rules (committed)

### Always on (4 files)

| File | Role |
|------|------|
| `01-surgical-agent.mdc` | grep → one file → one test; no repo exploration |
| `02-testing-economy.mdc` | **Always-on** test discipline — `::test_name` first |
| `03-insightecase-doctrine.mdc` | Neuro-affirmative, case-centric (slim) |
| `04-vibe-auditor.mdc` | React hygiene, optimistic UI |

### Manual domain (globs — safety guardrails)

`billing-domain` · `fastapi-api` · `fastapi-services` · `sqlalchemy-models` · `postgres-alembic` · `ui-components` · `frontend-lib` · `deploy-infra`

These load when you `@mention` matching paths — **not deleted** until 3 real fixes validate skill-only workflow.

---

## 3. Slash skills (no routers)

Type `/skill-name` directly — skill list in [AGENT_FIX_POLICY.md](./AGENT_FIX_POLICY.md#slash-skills-manual--name-exact-skill-in-prompt).

Do **not** use `/backend-router` etc. (removed).

---

## 4. MCP and plugin hygiene (manual)

See [AGENT_FIX_POLICY.md § MCP](./AGENT_FIX_POLICY.md#mcp-hygiene-configure-manually). Disable unused MCPs and plugin skills. **Developer: Reload Window**.

---

## 5. Per-fix workflow

```bash
./scripts/agent-fix-check.sh
```

| Who | Tests |
|-----|-------|
| Agent | `./scripts/agent-pytest.sh ...::test_name` or `-k` |
| Human pre-push | `./scripts/pre-push-check.sh` |

---

## Related

- [CLINICAL_REPORTS_UI_DESIGN.md](./CLINICAL_REPORTS_UI_DESIGN.md) — strict visual contract for clinical UI rebuilds
- [ANTIGRAVITY_MIGRATION.md](./ANTIGRAVITY_MIGRATION.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 6. Design drift (clinical UI)

Before changing case profile, reports, or clinical dashboard screens, read [CLINICAL_REPORTS_UI_DESIGN.md](./CLINICAL_REPORTS_UI_DESIGN.md).

For the **Insights tab** and Insights Engine work, also read [INSIGHTS_ENGINE.md](./INSIGHTS_ENGINE.md) and design contract §14 (simple snapshot layout — not a heavy dashboard).

If the implementation diverges from the approved Stitch reference or introduces a new dashboard visual language, **stop and ask** — do not “improve” with a generic SaaS layout.

Acceptance: InsighteCase brand retained · Stitch layout hierarchy · backend untouched · role-safe display.
