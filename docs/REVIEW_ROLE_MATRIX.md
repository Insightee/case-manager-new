# Review role and account matrix

Password for all demo accounts: `demo123`

| Email | Role(s) | Portal after login | Module assignments | Primary review flows |
|-------|---------|-------------------|--------------------|----------------------|
| `superadmin@demo.com` | SUPER_ADMIN | `/admin` | All features | Full regression, pipeline, workbench, billing approve |
| `moduleadmin@demo.com` | MODULE_ADMIN | `/admin` | homecare + shadow + billing (write) | RBAC editor, all programme nav |
| `admin@demo.com` | MODULE_ADMIN | `/admin` | `homecare` (write) | Programme admin (narrower modules than moduleadmin) |
| `support@demo.com` | MODULE_ADMIN | `/admin` | `homecare`, `billing` | Support tickets, client billing |
| `casemanager@demo.com` | CASE_MANAGER | `/admin/cm` | `homecare`, `shadow_support` | My caseload, team cases, workbench |
| `supervisor@demo.com` | CASE_MANAGER | `/admin/cm` | `shadow_support` | Shadow caseload (migrated from legacy SUPERVISOR) |
| `viewer@demo.com` | CASE_MANAGER (view-only) | `/admin/cm` | homecare + shadow **view** grants | Read-only CM; mutations blocked |
| `finance@demo.com` | FINANCE | `/admin/invoices` | `billing` | Finance home queues, client claims, payouts |
| `therapist@demo.com` | THERAPIST | `/therapist` | `homecare`, `shadow_support` | Slots, sessions, logs, invoices, reschedule confirm |
| `parent@demo.com` | PARENT | `/parent` | — | Book, reschedule, reports, billing, support |
| `hr@demo.com` | HR | `/hr` | `homecare`, `shadow_support` | Leave, therapists, memos |

**Not assignable for new staff:** `ADMIN`, `SUPERVISOR`, `VIEWER` — use `MODULE_ADMIN` or `CASE_MANAGER` with per-module view/write grants.

## Environment commands

```bash
cd backend && python3 -m app.seed.demo_seed
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
python3 -m pytest app/tests -q   # from backend/
cd frontend && npm run test:e2e  # requires API + UI
```

Optional one-off role migration (non-seed DBs):

```bash
cd backend && python3 scripts/migrate_staff_roles.py
```

## Portal routing

Portal is chosen in `AuthContext` from roles (login tabs are cosmetic). `PARENT` > `HR` > admin roles > `THERAPIST`.

`GET /api/v1/admin/home` returns `landing_route` and `dashboard_variant` (`module_admin`, `finance`, `caseload`, `legacy_admin`, `operations`).

## Recent-change regression anchors

| Feature | Route / API |
|---------|-------------|
| My caseload | `/admin/cm`, `GET /api/v1/admin/cm/home` |
| Finance home | `/admin/invoices`, finance widgets on home API |
| Pipeline kanban | `/admin/cases` (board view), `GET /api/v1/admin/cases/pipeline` |
| Pending reschedules | Workbench `reschedules` section → `/admin/cases/{id}?tab=scheduling&slotId=` |
| CM supervision filter | `/admin/cm-meetings?queue=supervision` |
