# Review role and account matrix

Password for all demo accounts: `demo123`

| Email | Role(s) | Portal after login | Module assignments | Primary review flows |
|-------|---------|-------------------|--------------------|----------------------|
| `superadmin@demo.com` | SUPER_ADMIN | `/admin` | All features | Full regression, pipeline, workbench, billing approve |
| `admin@demo.com` | ADMIN | `/admin` | `homecare` | Module-scoped nav vs superadmin |
| `casemanager@demo.com` | CASE_MANAGER | `/admin` | `homecare`, `shadow_support` | Workbench (team scope), cases, reports |
| `supervisor@demo.com` | SUPERVISOR | `/admin` | `shadow_support` | Team read, CM meetings, no cross-region write |
| `finance@demo.com` | FINANCE | `/admin` | `billing` | Invoice approve, client billing read |
| `viewer@demo.com` | VIEWER | `/admin` | `homecare`, `shadow_support` | Read-only banner; PATCH/assign blocked |
| `support@demo.com` | ADMIN | `/admin` | `homecare`, `billing` | Support tickets, escalate |
| `therapist@demo.com` | THERAPIST | `/therapist` | `homecare`, `shadow_support` | Slots, sessions, logs, invoices, reschedule confirm |
| `parent@demo.com` | PARENT | `/parent` | — | Book, reschedule, reports, billing, support |
| `hr@demo.com` | HR | `/hr` | `homecare`, `shadow_support` | Leave, therapists, memos |

## Environment commands

```bash
cd backend && python3 -m app.seed.demo_seed
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
python3 -m pytest app/tests -q   # from backend/
cd frontend && npm run test:e2e  # requires API + UI
```

## Portal routing

Portal is chosen in `AuthContext` from roles (login tabs are cosmetic). `PARENT` > `HR` > admin roles > `THERAPIST`.

## Recent-change regression anchors

| Feature | Route / API |
|---------|-------------|
| My caseload | `/admin/workbench`, `GET /api/v1/admin/workbench/summary` |
| Pipeline kanban | `/admin/cases` (board view), `GET /api/v1/admin/cases/pipeline` |
| Pending reschedules | Workbench `reschedules` section → `/admin/cases/{id}?tab=scheduling&slotId=` |
| CM supervision filter | `/admin/cm-meetings?queue=supervision` (not a separate supervisor inbox) |
