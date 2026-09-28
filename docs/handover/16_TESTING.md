# 16 — Testing

---

## Backend

| Item | Detail |
|------|--------|
| Framework | **pytest** 8.x |
| Location | `backend/app/tests/` |
| Command | `cd backend && python3 -m pytest app/tests -q` |
| Database | SQLite per test worker — configured in `conftest.py` before imports (`APP_ENV=test`) |
| Migration proof | `test_postgres_migration_proof.py` + CI job `postgres-migration-proof` on Postgres 16 |

### Notable test modules (non-exhaustive)

| Module | Focus |
|--------|-------|
| `test_rbac_access.py` | Authorization |
| `test_production_checks.py` | Production env guards |
| `test_refresh_token_storage.py` | Redis refresh behavior |
| `test_finance_*` | Billing/finance flags |
| `test_comprehensive_review.py` | Cross-feature flows (per TEST_GAP doc) |
| `test_admin_home_roles.py` | Admin landing |
| `test_scheduling_unified.py` | Scheduling |

### Alembic gates

```bash
python3 scripts/check_alembic_integrity.py
PYTHONPATH=.:alembic python3 -m alembic heads  # must be 1 head
python3 scripts/postgres_migration_up_down_up.py  # CI parity
```

---

## Frontend

| Type | Framework | Command |
|------|-----------|---------|
| Lint | ESLint 9 | `npm run lint` |
| Build | Vite | `npm run build` |
| Unit | Node test runner | `npm run test:unit` (selected `src/lib/*.test.js`) |
| E2E | Playwright | `npm run test:e2e` |

E2E specs under `frontend/e2e/` (e.g. `admin-workbench.spec.js`, `ux-seo.spec.js`).

Install browsers:

```bash
npx playwright install chromium
```

Combined review script:

```bash
npm run test:review   # lint + build + ux-seo e2e
```

---

## CI (GitHub Actions)

File: `.github/workflows/ci.yml`

| Job | Purpose |
|-----|---------|
| `postgres-migration-proof` | Alembic integrity, up/down/up, migration pytest |
| `backend` | Full pytest suite + dependency parity |
| `frontend` | `npm install` + `npm run build` with `VITE_API_URL` |
| `vercel-monorepo-build` | Root `vercel.json` build parity |
| `contributor-guards` | Policy checks |

Triggers: push/PR to `main` and `dev`.

---

## Coverage

**No enforced coverage percentage found in CI** — qualitative gaps tracked in [docs/TEST_GAP_BACKLOG.md](../TEST_GAP_BACKLOG.md).

---

## What is NOT adequately tested (from TEST_GAP_BACKLOG)

| Priority | Gap |
|----------|-----|
| P1 | Leave deduction in invoice preview |
| P1 | Parent ticket escalate + accept/rate |
| P2 | Assignment booking PATCH |
| P2 | Shadow-block preview/create |
| P2 | Holiday range marking |
| P2 | Invite-client scheduling flow |
| P3 | E2E finance invoice full UI |
| P3 | E2E kanban bulk assign |
| P3 | Playwright for HR demo portal |
| P3 | SCHOOL_COORDINATOR demo login |

---

## Smoke scripts (manual / ops)

| Script | Purpose |
|--------|---------|
| `backend/scripts/production_smoke.py` | Remote health + optional email |
| `backend/scripts/production_api_flow_smoke.py` | API flows |
| `scripts/therapist_flow_smoke.py` | Therapist API smoke (API on :8000) |

Env: `API_BASE_URL`, `SMOKE_*` — see [05_ENVIRONMENT_VARIABLES.md](./05_ENVIRONMENT_VARIABLES.md).

---

## Running full suite locally

```bash
# From repo root
make check

# Or manually:
cd backend && python3 -m pytest app/tests -q
cd frontend && npm run lint && npm run build && npm run test:unit
cd frontend && npm run test:e2e   # longer; needs stack up
```
