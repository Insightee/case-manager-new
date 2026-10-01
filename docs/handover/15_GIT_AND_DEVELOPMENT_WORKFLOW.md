# 15 — Git and Development Workflow

From [CONTRIBUTING.md](../../CONTRIBUTING.md), [docs/GITHUB_SETUP.md](../GITHUB_SETUP.md), [AGENTS.md](../../AGENTS.md).

---

## Branch model

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready; protected |
| `dev` | CI also runs on push/PR — **verify** if used for integration |
| Feature branches | `feature/*`, `fix/*`, `chore/*`, `docs/*` |

**No long-lived `development` branch documented** — branch from `main`.

---

## Pull request process

1. Branch from updated `main`  
2. Implement single concern  
3. Local checks: `make check`  
4. Open PR to `main` (or `dev` if team uses it)  
5. Required CI green + peer review  
6. Merge (squash or merge commit — **verify team preference**)  
7. Update [CHANGELOG.md](../../CHANGELOG.md) `[Unreleased]`  

---

## Commit conventions

CONTRIBUTING references conventional style in GitLab rule file; repo uses messages like:

- `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`  
- Reference issues when applicable  

Example from practice: descriptive sentences focusing on **why**.

---

## Pre-push hooks (optional)

```bash
make hooks
```

Blocks commits to `main`, blocks `.env` commits, runs tests on pre-push.

---

## Code review expectations

- RBAC/migration changes need tests  
- One Alembic head — use auto-generated revision IDs  
- No secrets in diff  

---

## CODEOWNERS

See [docs/TEAM_OWNERSHIP.md](../TEAM_OWNERSHIP.md) for area owners.

---

## Deployment triggers

| Event | Expected outcome |
|-------|------------------|
| Merge to `main` | Vercel + Railway deploy **(confirm in dashboards)** |
| PR | CI only, preview deploy **(verify Vercel preview env vars)** |

---

## Example commands

```bash
git checkout main && git pull
git checkout -b feature/my-change

# work...

cd backend && python3 -m pytest app/tests -q
cd frontend && npm run lint && npm run build

git add -A
git commit -m "feat: describe why"
git push -u origin feature/my-change

gh pr create --title "..." --body "..."
```

---

## Agent / AI contributors

Read [AGENTS.md](../../AGENTS.md) and [docs/AGENT_WORKFLOW.md](../AGENT_WORKFLOW.md) — deploy split, no commits unless asked, Grok/Composer preference for subagents.

---

## Changelog discipline

Every merge updates `[Unreleased]`; on production release, rename section with date per [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md).
