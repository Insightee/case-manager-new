# 09 — API Reference

**Base URL:** `{API_HOST}/api/v1`  
**Interactive docs:** `{API_HOST}/docs` (FastAPI Swagger)  
**Health:** `GET /health` (no prefix)

This document lists **routers and representative endpoints** discovered in `backend/app/api/v1/`. It is not an exhaustive OpenAPI dump — use `/docs` for complete schemas.

**Authentication:** Unless noted, endpoints require `Authorization: Bearer <access_token>`.

---

## Auth (`/api/v1/auth`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/login` | No | Issue access + refresh tokens; optional portal gate |
| POST | `/refresh` | No | Refresh access token |
| POST | `/logout` | Yes | Revoke refresh |
| GET | `/me` | Yes | Current user + modules/features |
| PATCH | `/me` | Yes | Profile updates |
| POST | `/forgot-password` | No | Email reset link |
| GET | `/reset-password/{token}/preview` | No | Validate reset token |
| POST | `/reset-password` | No | Set new password |
| POST | `/accept-invite` | No | Complete invite signup |
| POST | `/request-status-restore` | No | HR restore ticket from login |

Frontend: `LoginPage`, `AuthContext`, password pages.

---

## Cases (`/api/v1/cases`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `` | Paginated case list (scoped) |
| POST | `` | Create case |
| GET | `/{case_id}` | Case detail |
| PATCH | `/{case_id}` | Update case |
| PATCH | `/{case_id}/billing` | Billing fields |
| PATCH | `/{case_id}/day-type` | Calendar day type |
| POST | `/{case_id}/status-requests` | Client status change request |
| GET/PATCH | `/{case_id}/clinical-profile` | Structured clinical JSON |
| GET/PUT | `/{case_id}/observation-checklist` | Observation checklist |
| GET/POST | `/{case_id}/iep-plan` | IEP plan |
| GET | `/{case_id}/session-logs/export/xlsx` | Export |

Implementation: `cases.py`, services in `case_*_service.py`.

---

## Assignments (`/api/v1/cases/{case_id}/assignments`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `` | List assignments |
| POST | `` | Create assignment |
| PATCH | `/{assignment_id}/booking` | Booking mode |

Also: `/api/v1/cases/{case_id}/services/*`, `/api/v1/cases/{case_id}/transitions/*`, `/api/v1/assignments/...` service-level assignment routes.

---

## Sessions (`/api/v1/sessions`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `` | List sessions |
| POST | `/{id}/start`, `/{id}/end` | Session timer |
| POST | void/cancel paths | Session lifecycle (see OpenAPI) |

Related: `/api/v1/sessions/...` absence routes in `session_absence.py`.

---

## Daily logs (`/api/v1/daily-logs`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `` | Inbox/list |
| POST | `` | Create/submit log |
| GET/PATCH | `/{id}` | Read/update |
| POST | `/{id}/approve`, `/{id}/reject` | Admin approval |

Parent-visible logs filtered in `/parent/session-logs`, not here.

---

## Reports (`/api/v1/reports`)

Monthly and observation report pipeline — list, create, submit, approve, publish. See `reports.py` and admin report routes.

Clinical reports engine (separate router, flag-gated): paths under cases for observation/IEP builders — `clinical_reports.py`.

---

## Invoices (`/api/v1/invoices`)

Therapist invoice CRUD, submit, admin review, PDF download — `invoices.py`.

---

## Admin (`/api/v1/admin`)

Large surface — includes:

| Area | Examples |
|------|----------|
| Home | `GET /home` — landing route + widgets |
| RBAC | `GET /rbac/catalog`, `POST /rbac/preview` |
| Users/staff | CRUD, invites, module grants |
| Families/clients | Client profiles |
| Session logs queue | Approve/reject bulk views |
| Reports | Admin review |
| Dashboard stats | KPI endpoints |
| Exports | CSV/XLSX operational reports |

File: `admin.py` (1000+ lines) — use `/docs` tag **admin**.

---

## Finance (requires `ENABLE_BILLING=true`)

| Router | Prefix | Purpose |
|--------|--------|---------|
| `finance_ops` | `/admin` | Overview, therapist payouts, finance reports |
| `finance_control_tower` | `/admin/finance-control-tower/...` | Read-only tower |
| `finance_writable` | `/admin/finance-writable/...` | Corrections, deductions |
| `ledger_billing` | `/admin/ledger-billing/...` | Product rules, ledger, disputes |
| `client_billing` | `/admin/...` + `/parent/...` | Client invoices |

If flag off, routers not mounted — calls return 404.

---

## Parent (`/api/v1/parent`)

| Area | Path prefix | Purpose |
|------|-------------|---------|
| Home | `/home` | Dashboard |
| Cases | `/cases`, `/cases/{id}` | Case hubs |
| Session logs | `/session-logs` | Approved logs only |
| Reports | `/reports`, `/reports/monthly/...`, IEP paths | Published content |
| Billing | `/billing-summaries` | Parent statements |
| Booking | `/booking/calendar`, `/appointments` | Appointments |
| Support | `/support/tickets`, `/support-requests` | Tickets |
| Incidents | `/incidents` | Parent incident reporting |

File: `parent.py` (very large).

---

## Therapist portal (`/api/v1/therapist`)

Dashboard stats, schedule summaries — complements cases/sessions/logs routes.

---

## Booking & scheduling

| Router | Prefix |
|--------|--------|
| `booking` | `/booking` |
| `slots` | `/slots` |
| `scheduling` | `/scheduling` |
| `calendar` | `/calendar` |

---

## HR & attendance

| Router | Prefix |
|--------|--------|
| `staff_attendance` | `/staff-attendance` |
| `leave` | `/leave` |
| `hr` | `/hr` |
| `hr_ops` | `/admin` (HR reports) |

---

## Support hub

| Router | Prefix |
|--------|--------|
| `tickets` | `/tickets` |
| `support` | `/support` (e.g. `/info`) |
| `memos` | `/memos` |
| `incidents` | `/incidents` |
| `admin_support` | `/admin/support` |

---

## Files & attachments

| Router | Prefix |
|--------|--------|
| `attachments` | `/attachments` |
| `files` | `/files` |
| `case_documents` | case-scoped document routes |

---

## Integrations (`INTEGRATION_API_ENABLED`)

| Router | Prefix |
|--------|--------|
| `integrations` | `/integrations` |
| `admin_integration_clients` | `/admin/integration-clients` |
| `admin_integration_webhooks` | `/admin/integration-webhooks` |

Machine auth via integration JWT — see [docs/INTEGRATIONS_MCP.md](../INTEGRATIONS_MCP.md).

---

## Notifications (`/api/v1/notifications`)

List, mark read, read-all.

---

## Users (`/api/v1/users`)

Availability rules: `GET/PUT /{user_id}/availability`.

---

## Geocode (`/api/v1/geocode`)

Address geocoding — inspect `geocode.py` for external provider and env vars.

---

## Error responses

Typical shapes:

- `401` — missing/invalid token  
- `403` — permission, portal, module, or case scope  
- `404` — entity or disabled feature router  
- `422` — Pydantic validation  
- `409`/custom — integrity conflicts via DB handler  

Frontend parses `detail` string or object (`code`, `message` on login blocks).

---

## Related frontend usage

| Frontend area | Primary API prefix |
|---------------|-------------------|
| Therapist logs | `/sessions`, `/daily-logs` |
| Admin workbench | `/admin/...`, `/daily-logs` |
| Parent feed | `/parent/session-logs` |
| Finance | `/admin/finance-*`, `/admin/ledger-billing` |

**Do not invent endpoints** — when adding features, update OpenAPI by implementing router + regenerate this doc section in future handovers.
