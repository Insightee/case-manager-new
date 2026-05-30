# Team ownership

Primary reviewers by area. Update GitHub usernames in [`.github/CODEOWNERS`](../.github/CODEOWNERS) when the team is set.

| Area | Primary owner | Backup | Key paths |
|------|---------------|--------|-----------|
| Backend API & migrations | *@TBD* | *@TBD* | `backend/app/api/`, `backend/alembic/` |
| RBAC & modules | *@TBD* | *@TBD* | `backend/app/core/permissions.py`, `modules.py` |
| Billing & invoices | *@TBD* | *@TBD* | `*invoice*`, `*billing*`, `client_billing_*` |
| Support hub & tickets | *@TBD* | *@TBD* | `support_access_service.py`, `AdminSupportHubPage.jsx`, `ticket_*` |
| HR portal & reports | *@TBD* | *@TBD* | `hr_ops.py`, `hr_reports_*`, `hr-portal/` |
| Therapist / parent UX | *@TBD* | *@TBD* | therapist routes, `test_profile_session_logs.py` |
| Deploy & infra | *@TBD* | *@TBD* | `railway.toml`, `vercel.json`, `docs/DEPLOY.md` |
| Docs & release | *@TBD* | *@TBD* | `docs/`, `CHANGELOG.md`, `CONTRIBUTING.md` |

## Review rules

1. **Author cannot approve their own PR** (enforce in GitHub branch protection).
2. **Migration PRs** — owner of “Backend API & migrations” must review.
3. **RBAC PRs** — owner of “RBAC & modules” must review.
4. **Cross-area PRs** — split if possible; otherwise request both area owners.

## Setting CODEOWNERS

Replace `TBD` placeholders in `.github/CODEOWNERS` with real GitHub handles, e.g.:

```
/backend/app/core/permissions.py @insightee-alice
/backend/app/core/modules.py @insightee-alice
```

GitHub will auto-request reviews when those paths change.
