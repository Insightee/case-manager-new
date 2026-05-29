# Early pilot — focused release scope

Ship **only** the paths below in one PR. Stash or defer unrelated local WIP (~90 files: billing, reports UI, incidents, CM home, etc.).

## In scope

| Area | Paths |
|------|--------|
| Pilot acceptance (no gating) | `backend/app/core/config.py` (`acceptance_gating_enabled`), `backend/app/services/assignment_acceptance_service.py` |
| Allotment approval | `backend/app/services/allotment_service.py`, `backend/app/api/v1/admin.py` (allot, activate, preview) |
| Acceptance schema/API | `backend/alembic/versions/b3c4d5e6f7a8_assignment_acceptance.py`, `backend/app/models/assignment.py`, `backend/app/api/v1/assignment_acceptance.py`, `backend/app/api/v1/parent.py` (accept route), `backend/app/api/v1/router.py`, `backend/app/schemas/case.py`, `backend/app/schemas/parent_home.py`, `backend/app/schemas/therapist_home.py`, `backend/app/services/assignment_service.py`, `backend/app/services/parent_home_service.py`, `backend/app/services/therapist_home_service.py`, `backend/app/services/parent_service.py`, `backend/app/services/session_service.py`, `backend/app/core/database.py` (sqlite patches) |
| Scheduling fix | `frontend/src/lib/sessionDisplay.js`, `frontend/src/components/admin-portal/CaseSchedulingHub.jsx` |
| Wizard | `frontend/src/components/admin-portal/AdminCaseAllotmentWizard.jsx`, `admin-allotment-wizard.css` |
| Soft UX | `frontend/src/components/client-portal/ClientDashboardPage.jsx`, `frontend/src/pages/TherapistDashboardPage.jsx` |
| Tests | `backend/app/tests/test_admin_portal.py`, `test_pending_allotment_recurring_calendar.py`, `test_pilot_assignment_no_gating.py` |
| Ops | `backend/scripts/migrate_production.py` (`case_assignments` columns in `_REQUIRED_AT_HEAD`) |

## Pilot policy

- `ACCEPTANCE_GATING_ENABLED=false` (default) — acceptance timestamps are **informational**; `ACTIVE` + admin assignment = full access.
- Post-pilot: set `ACCEPTANCE_GATING_ENABLED=true` on Railway to enforce acceptance as a permission layer.

## Pre-push

```bash
cd backend && PYTHONPATH=.:alembic python3 -m alembic heads   # one (head): b3c4d5e6f7a8
cd backend && python3 -m pytest app/tests -q
cd frontend && npm run build
```

## Deploy verify

1. Merge PR → CI green.
2. Railway deploy → log line `Migration complete (revision b3c4d5e6f7a8)`.
3. `curl -s https://case-manager-new-production.up.railway.app/health` → `"db_migration":"b3c4d5e6f7a8"`.
4. Redeploy Vercel `insightes-projects/frontend`.

## Manual smoke (no accept clicks required)

- Admin allot/import → `ACTIVE` → book session → upcoming list shows date/time.
- Therapist: start session + log without accepting.
- Parent: dashboard + case detail + IEP without accepting.
- Optional: banner visible; “reviewed” accept sets `*_accepted_at`.

## Alembic and your PC

Migrations run on **Railway container start** (`start-production.sh`), not on your laptop. Your PC being off does not block production schema updates; only **unpushed** code stays off production.
