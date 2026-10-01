# 20 — Rebuild From Scratch

If the codebase were deleted, a team with this document, product access, and credentials could recreate **InsighteCase** as the same product class: case-centric therapy operations with therapist, admin, parent, and finance portals.

This is a **behavioral and architectural blueprint**, not a line-by-line port.

---

## Phase 0 — Product invariants

Recreate these rules first:

1. **Case ID** is the operational anchor; assignments have history.  
2. Parents see **approved/published** content only.  
3. JWT + RBAC + module grants gate every mutation.  
4. Production: Postgres + Redis + R2 + ZeptoMail + split Vercel/Railway deploy.  
5. Billing money writes behind explicit flags and cutover runbooks.  
6. Clinical data: neuro-affirmative structured fields, not diagnosis-first UX.
7. UI: follow [docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md) — Forest Light product foundation, portal-specific shells, no global stylesheet swap.

---

## Phase 1 — Project structure

```
insightcase/
  backend/
    app/main.py
    app/api/v1/
    app/core/
    app/models/
    app/schemas/
    app/services/
    app/storage/
    alembic/
    scripts/
    requirements.txt
    Dockerfile
  frontend/
    src/routes/AppRoutes.jsx
    src/context/AuthContext.jsx
    src/lib/apiClient.js
    src/components/{admin-portal,client-portal,daily-logs,...}
    package.json
    vite.config.js
  docs/
  docker-compose.yml
  vercel.json
  .github/workflows/ci.yml
```

Monorepo; Python 3.11 backend; Node 24 frontend build.

---

## Phase 2 — Dependencies

**Backend (`requirements.txt` equivalent):**

- fastapi, uvicorn, sqlalchemy, alembic, psycopg2-binary, pydantic-settings  
- python-jose, passlib[bcrypt], redis, httpx, pytest  
- boto3 (R2), reportlab (PDFs), openpyxl (exports)  
- mcp (optional integration server)  

**Frontend:**

- react, react-dom, react-router-dom, @tanstack/react-query  
- tailwindcss, vite, @vitejs/plugin-react  
- tiptap (reports), dompurify, recharts, dnd-kit, playwright, vite-plugin-pwa  

**Do not add Celery unless you redesign background jobs.**

---

## Phase 3 — Configure backend core

Implement `Settings` mirroring [config.py](../../backend/app/core/config.py):

- Database URL normalization  
- JWT + refresh secrets and TTLs  
- CORS, FRONTEND_URL  
- Storage provider local/r2  
- SMTP and email throttles  
- All billing/finance feature flags default **safe** (off)  
- Production validation module that **refuses unsafe prod config**

---

## Phase 4 — Configure frontend

- Vite proxy `/api` → `localhost:8000` in dev  
- `apiClient` with Bearer auth, refresh, 30s timeout, production host rewrite rules for `insighte.org`  
- `AuthContext` with portal selection  
- Feature flag reads from `VITE_*` env  

---

## Phase 5 — Database schema

Recreate tables in dependency order (Alembic revisions):

### Identity

- users, roles, permissions, user_roles, role_permissions  
- invite_tokens, password_reset_tokens  

### Case domain

- children, parent_guardians, parent_child_link  
- cases (case_code, status, product_module, billing fields, region, case_manager_user_id)  
- case_assignments, case_services, case_therapist_transitions  
- case_clinical_profiles, observation_checklists  
- case_operational_notes, case_documents (+ versions, workflow events)  

### Operations

- therapy_sessions, daily_logs, session_absence_requests  
- monthly_reports, observation_reports, clinical_reports (+ sections, versions, evidence)  
- iep_plans, attachments, report_images  

### Scheduling

- therapist_slots, recurring_schedule_assignments, appointment_reschedule  
- staff_availability_rules, case_manager_meetings  

### Finance

- invoices, invoice lines, payouts, parent_billing_statements  
- client_invoices, billing_ledgers, product_billing_rules  
- finance_correction_proposals, therapist_payout_batches  

### Support & HR

- support_tickets, memos, incidents  
- staff_attendance, staff_leaves, therapist_leaves, therapist_profiles  
- notifications, audit_events, email_logs  

Use [06_DATABASE.md](./06_DATABASE.md) as table checklist.

---

## Phase 6 — Implement authentication

1. `POST /auth/login` — bcrypt verify, portal check, employment check  
2. Issue access + refresh JWT  
3. Store refresh in Redis with jti/revocation  
4. `POST /auth/refresh`, `POST /auth/logout`  
5. `GET/PATCH /auth/me` with modules/features payload  
6. Invite accept + password reset flow with SMTP templates  
7. Audit login events  

---

## Phase 7 — Implement authorization

1. Seed roles and `ROLE_PERMISSIONS` map  
2. Module catalog: homecare, shadow_support, billing + dynamic service categories  
3. `module_access_grants`, `feature_overrides`, `is_view_only` on user  
4. Dependencies: `require_permission`, module write checks, case scope for CM  
5. Admin RBAC catalog + preview endpoints  

---

## Phase 8 — Implement core APIs (minimum viable product)

Build in order:

1. **Cases CRUD** + assignments + clinical profile  
2. **Sessions** start/end + **daily logs** submit  
3. **Admin log approve** → visibility fields for parent  
4. **Monthly reports** pipeline  
5. **Parent portal** read APIs with strict filters  
6. **Admin dashboard** home + case hub  
7. **Tickets/support** basic  
8. **Notifications**  

Then expand: booking, IEP, invoices, finance engine, HR attendance, integrations.

Router layout: single `api_router` prefix `/api/v1` as in [07_BACKEND.md](./07_BACKEND.md).

---

## Phase 9 — Implement frontend routes

Mirror [08_FRONTEND.md](./08_FRONTEND.md):

- Public login paths per portal  
- `Protected` portal guard  
- Therapist: dashboard, logs, cases, reports, support  
- Parent: dashboard, cases, session-logs, reports, billing, book  
- Admin: index, cm, workbench, cases, logs, reports, invoices, people, support, HR, integrations  

Use lazy loading for admin/parent chunks.

---

## Phase 10 — Business workflows (must match behavior)

Implement services, not fat controllers:

| Workflow | Must do |
|----------|---------|
| Log approval | Set approval + visibility; strip internal fields from parent reads |
| Report publish | Status + visibility gates |
| Assignment replace | End prior assignment row; create new; audit |
| Invoice generation | Trace to sessions/logs; finance status transitions |
| Billing flags | Routers unmounted when `ENABLE_BILLING=false` |
| Low-margin billing | Approval queue before persist |
| Payout export/release | Separate flags; mock provider default |
| Ticket attachments | 3×5MB limits |
| Session void | Window hours from config |

See [11_BUSINESS_LOGIC.md](./11_BUSINESS_LOGIC.md).

---

## Phase 11 — Storage layer

Abstract interface:

- `local` — filesystem under `uploads/`  
- `r2` — boto3 private bucket; download via authorized API stream  

Report images, ticket files, case documents use same pattern.

---

## Phase 12 — Email layer

- Noop when SMTP unset  
- Log all attempts to `email_logs`  
- Separate From addresses for billing/verification/general  
- Rate limits on forgot-password and invite retries  

---

## Phase 13 — External integrations

Provision:

- Railway project + Postgres + Redis  
- Vercel frontend project + domains  
- Cloudflare R2 bucket + API tokens  
- ZeptoMail domain + SMTP credential  
- Optional Zoho Books, Razorpay (stubs first)  

Wire env vars per [05_ENVIRONMENT_VARIABLES.md](./05_ENVIRONMENT_VARIABLES.md).

---

## Phase 14 — CORS and domains

- `FRONTEND_URL=https://www.insighte.org`  
- `CORS_ORIGINS` lists all active UI origins  
- Vercel rewrites `/api/(.*)` → Railway API URL  

---

## Phase 15 — Deployment pipeline

1. GitHub repo + branch protection  
2. CI: pytest, postgres migration proof, frontend build, contributor guards  
3. Railway Dockerfile + `start-production.sh` (migrate then uvicorn workers)  
4. Vercel root config building `frontend/`  

---

## Phase 16 — Migrations and seed

- Alembic single-head discipline  
- Demo seed script creating role matrix and sample cases  
- Production: never auto demo seed  

---

## Phase 17 — Tests

- pytest conftest with isolated SQLite  
- RBAC tests for each new permission  
- Postgres up/down/up proof script in CI  
- Playwright smoke for admin workbench and login  

---

## Phase 18 — Verify production

Checklist:

- `/health` ok, redis ok, smtp configured, db_migration at head  
- Login all portals  
- Therapist log → admin approve → parent sees sanitized log  
- Upload report image via R2  
- Send invite email  
- Finance flags off → finance routes 404  

---

## Phase 19 — Documentation to regenerate

- Env reference, RBAC scope, billing architecture, deploy runbooks, therapist/parent guides  
- This handover package  

---

## Component checklist (major modules)

| Module | Must do |
|--------|---------|
| `auth_service` | Login, tokens, password rules |
| `case_service` | CRUD, scoping, status requests |
| `assignment_service` | History, replace, booking mode |
| `session_log_service` | Logs linked to sessions |
| `invoice_billing_service` | Therapist invoice computation |
| `billing_ledger_service` | Ledger drafts/writes when flagged |
| `notification_service` | In-app + email triggers |
| `parent_service` | Visibility filters |
| `case_portal_visibility` | Consistent parent/staff views |
| `finance_correction_service` | Writable finance when enabled |
| `storage` service | Local/R2 parity |

---

## What you cannot recreate from docs alone

- Exact PDF/Excel export layouts  
- Every admin CSV column mapping  
- Full finance engine edge cases — require [billing-architecture.md](../billing-architecture.md) + finance handover PDFs + **team walkthrough**  
- Production data migration from legacy spreadsheets — [DATA_IMPORT.md](../DATA_IMPORT.md)  

See [DOCUMENTATION_GAPS.md](./DOCUMENTATION_GAPS.md).

---

## Success criteria for rebuild

A rebuilt system matches the original when:

1. Same role matrix and module grants behave equivalently on test cases.  
2. Case-centric timelines match for sample case lifecycle.  
3. Parent never receives pre-approval therapist notes.  
4. Production guards fail closed on misconfiguration.  
5. Deploy split (Vercel UI + Railway API) works with `insighte.org` rewrites.  
6. Finance remains off until deliberate cutover flag sequence.
