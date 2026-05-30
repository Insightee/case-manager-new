# GitHub repository setup (team admins)

One-time (or audit) configuration so [CONTRIBUTING.md](../CONTRIBUTING.md) rules are **enforced**, not optional.

## Branch protection on `main`

**Settings → Branches → Add rule → Branch name pattern: `main`**

Enable:

| Setting | Value |
|---------|--------|
| Require a pull request before merging | Yes |
| Required approvals | **1** |
| Dismiss stale pull request approvals when new commits are pushed | Recommended |
| Require review from Code Owners | Yes (after CODEOWNERS usernames are set) |
| Require status checks to pass before merging | Yes |
| Require branches to be up to date before merging | Recommended |
| Do not allow bypassing the above settings | Yes (including admins, if acceptable) |
| Restrict who can push to matching branches | Optional — limit to release manager |

### Required status checks

Add these from CI (`.github/workflows/ci.yml`):

- `backend`
- `frontend`
- `vercel-monorepo-build`
- `contributor-guards`

If check names differ, open a recent PR and copy exact names from the Checks tab.

## CODEOWNERS

1. Edit [`.github/CODEOWNERS`](../.github/CODEOWNERS) — replace `@Insightee/TBD` with real GitHub usernames or teams.
2. Update [TEAM_OWNERSHIP.md](./TEAM_OWNERSHIP.md) table to match.

## Verify with GitHub CLI

```bash
gh api repos/Insightee/case-manager-new/branches/main/protection --jq '.required_status_checks.contexts'
```

Expect the four CI job names listed above.

## Optional: merge queue

For busy teams, enable **merge queue** on `main` so PRs serialize merges after CI (Settings → General → Pull Requests).

## Release discipline

Before production promote:

1. `./scripts/pre-release-check.sh`
2. [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) manual steps
3. Move [CHANGELOG.md](../CHANGELOG.md) `[Unreleased]` → dated section

## Secrets

- Never store Railway/Vercel tokens in the repo.
- Use GitHub **Environments** (`production`) with required reviewers for deploy workflows if you add automated deploy later.
