# Review role and account matrix

Password for all demo accounts: `demo123`

## Product portals

| Portal | Who | Login tab |
|--------|-----|-----------|
| **Client** | `PARENT`, `SCHOOL_COORDINATOR` | Client |
| **Therapist** | `THERAPIST` | Therapist |
| **Staff** | `SUPER_ADMIN`, `MODULE_ADMIN`, `CASE_MANAGER`, `FINANCE`, `HR` | Staff |

Legacy `/hr/*` URLs redirect into the staff portal (`/admin/*`).

| Email | Role(s) | Landing route | Module assignments | Primary review flows |
|-------|---------|---------------|--------------------|----------------------|
| `superadmin@demo.com` | SUPER_ADMIN | `/admin` | All features | Full regression, pipeline, workbench, billing approve |
| `moduleadmin@demo.com` | MODULE_ADMIN | `/admin` | homecare + shadow + billing (write) | RBAC editor, all programme nav |
| `admin@demo.com` | MODULE_ADMIN | `/admin` | `homecare` (write) | Programme admin (narrower modules than moduleadmin) |
| `support@demo.com` | MODULE_ADMIN | `/admin` | `homecare`, `billing` | Support tickets, client billing |
| `casemanager@demo.com` | CASE_MANAGER | `/admin/cm` | `homecare`, `shadow_support` | My caseload, team cases, workbench |
| `supervisor@demo.com` | CASE_MANAGER | `/admin/cm` | `shadow_support` | Shadow caseload (migrated from legacy SUPERVISOR) |
| `viewonly@demo.com` | CASE_MANAGER (view-only) | `/admin/cm` | homecare + shadow **view** grants | Read-only CM; mutations blocked |
| `finance@demo.com` | FINANCE | `/admin/invoices` | `billing` | Finance home queues, client claims, payouts |
| `hr@demo.com` | HR | `/admin/people` | `homecare`, `shadow_support` | People, leave, memos |
| `therapist@demo.com` | THERAPIST | `/therapist` | `homecare`, `shadow_support` | Slots, sessions, logs, invoices |
| `parent@demo.com` | PARENT | `/parent` | — | Book, reschedule, reports, billing, support |

**Not assignable for new staff:** `ADMIN`, `SUPERVISOR`, `VIEWER` — use `MODULE_ADMIN` or `CASE_MANAGER` with per-module view/write grants.

## Case Manager scope (staff portal)

Case managers use the **same staff shell** as other admins but typically land on **My caseload** (`/admin/cm`) with a shorter nav.

| In scope | Out of scope (unless another role) |
|----------|-----------------------------------|
| Cases they manage or in their **region**, within **assigned programme modules** | All org cases (`case.read.all`) |
| **Clients** linked to those cases | Org-wide People directory admin |
| **Therapists** on assigned cases | Finance invoices org-wide |
| Session logs, reports, IEP, workbench, pipeline (scoped) | Service category settings |
| Support, CM meetings | RBAC editor (assigned by Module Admin) |

Enforcement: `apply_case_scope`, `case.read.team`, `module_assignments`, `case_scope_check` on report routes.

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

`AuthContext` maps `PARENT` → client, `THERAPIST` → therapist, all staff roles (including `HR`) → **admin** staff shell.

`GET /api/v1/admin/home` returns `landing_route` and `dashboard_variant` (`module_admin`, `finance`, `caseload`, `operations`).

## Regression anchors

| Feature | Route / API |
|---------|-------------|
| My caseload | `/admin/cm`, `GET /api/v1/admin/cm/home` |
| Finance home | `/admin/invoices` |
| Case pipeline | `/admin/cases`, `GET /api/v1/admin/cases/pipeline` |
| HR legacy redirect | `/hr/people` → `/admin/people` |
| CM supervision filter | `/admin/cm-meetings?queue=supervision` |
