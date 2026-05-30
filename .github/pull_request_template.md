## Summary

<!-- What changed and why (1–3 bullets) -->

-

## Area

<!-- Check all that apply -->

- [ ] Backend API
- [ ] Frontend admin portal
- [ ] Frontend therapist / parent portal
- [ ] Database migration (Alembic)
- [ ] RBAC / permissions / modules
- [ ] Billing / invoices
- [ ] Support hub / tickets / incidents
- [ ] Deploy / environment variables
- [ ] Documentation only

## Author checklist

<!-- Required before requesting review -->

- [ ] Branched from latest `main` (not committing directly to `main`)
- [ ] `./scripts/pre-push-check.sh` passes locally **or** equivalent commands below
- [ ] `cd backend && python3 -m pytest app/tests -q` — green
- [ ] `cd frontend && npm run build` — green
- [ ] If `backend/alembic/versions/` changed: `PYTHONPATH=.:alembic python3 -m alembic heads` shows **exactly one** `(head)`
- [ ] If RBAC/modules changed: added or updated tests (`test_rbac_access.py` or feature tests)
- [ ] No secrets in diff (`.env`, tokens, SMTP keys) — see [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)
- [ ] [CHANGELOG.md](CHANGELOG.md) updated under `[Unreleased]` (can be done at merge time)

## How to test

<!-- Steps for reviewer: role, URL, flow -->

1.
2.

## Screenshots / API notes

<!-- UI screenshots or breaking API contract notes; delete if N/A -->

## Related

<!-- Issue, plan doc, or ADR link -->

-

---

**Reviewers:** See [docs/TEAM_OWNERSHIP.md](docs/TEAM_OWNERSHIP.md). CI must be green before merge ([CONTRIBUTING.md](CONTRIBUTING.md)).
