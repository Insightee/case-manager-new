# InsightCase

Case-Centric Operations Platform for Insighte Childcare Pvt. Ltd.

This repository will be built incrementally from the Product Requirements Document (PRD), starting with **Therapist-first workflows** and then expanding to the full case lifecycle.

---

## Local development

**Backend** (from `backend/`):

```bash
python3 -m pip install -r requirements.txt
python3 -m app.seed.demo_seed
uvicorn app.main:app --reload --port 8000
```

**Frontend** (from `frontend/`):

```bash
npm install
npm run dev
```

Open http://localhost:5173 and sign in with demo accounts (e.g. `superadmin@demo.com` / `demo123`, `therapist@demo.com` / `demo123`).

**E2E tests** (from `frontend/`, starts Vite + API if not already running):

```bash
npm install
npx playwright install chromium
npm run test:e2e
```

API-only smoke (backend must be on `:8000`): `python3 scripts/therapist_flow_smoke.py`

See [backend/README.md](backend/README.md) for API details and role matrix. System architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Dev preview (Vercel + API)

To share the UI with reviewers:

1. Deploy the **API** (Postgres + env vars) — see [docs/DEPLOY.md](docs/DEPLOY.md).
2. Deploy **frontend** on Vercel with root directory `frontend` and `VITE_API_URL` pointing at the API.
3. Add your Vercel URL to API `CORS_ORIGINS`, then run seed on the API host.

CI runs backend tests and `npm run build` on push (`.github/workflows/ci.yml`).

---

## Product Overview

InsightCase replaces spreadsheet-led operations with a case-centric system where every converted engagement becomes a unique `Case ID`.

Core principle:
- `Case` is the operational source of truth.
- All activity (assignment, logs, reports, IEP, invoicing, payouts, incidents) links back to the same case timeline.

Outcome goals:
- Better operational visibility
- Strong therapist accountability
- Structured parent transparency
- Audit-ready governance
- Scale without proportional manual coordination growth

---

## Therapist-First Build Strategy

We will deliver in parts so value is visible early and adoption is smooth.

### Why start with Therapist?
- Daily logs are the foundation for attendance, reporting, and invoicing.
- Therapist workflow has highest frequency and strongest impact on data quality.
- Mobile-first therapist UX reduces adoption risk early.

### What Therapist-first includes
- Therapist login and role-scoped access
- Assigned case list and session context
- Mandatory daily log submission
- Log compliance reminders and exception capture
- Monthly report draft inputs from logs
- Invoice draft inputs from logs

---

## Build Plan (Part-by-Part)

## Part 0 - Foundation Setup

Objective: establish production-ready foundations before feature work.

Deliverables:
- Monorepo or structured frontend/backend setup
- Frontend scaffold (React + Vite + Tailwind)
- Backend scaffold (FastAPI + SQLAlchemy + Alembic)
- PostgreSQL local/dev environment
- Auth baseline (JWT + RBAC skeleton)
- Basic CI (lint + test + build)

Exit criteria:
- Health endpoints up
- Local dev runs in one command (or documented minimal steps)
- Migration pipeline functional

## Part 1 - Therapist Core (MVP Start)

Objective: therapist can perform daily work reliably.

Modules:
- Therapist authentication
- Therapist dashboard (today’s sessions, pending logs)
- Assigned case list and case detail snapshot
- Daily log form (date, duration, activities, observations, attendance markers)
- Mandatory log enforcement at session close (or exception reason)

Exit criteria:
- Therapist can submit same-day logs from mobile
- Missing log visibility exists for case manager/admin views (basic)
- Audit event created for log create/update/submit actions

## Part 2 - Supervisor Loop for Therapist Outputs

Objective: convert raw therapist activity into supervised, trusted outputs.

Modules:
- Observation report submission by therapist
- Case manager review flow (approve/reject)
- Monthly report draft compilation from daily logs
- Review queue and status transitions

Exit criteria:
- Observation and monthly report lifecycle works end-to-end
- Rejections include reason and resubmission path
- Parent visibility still blocked until approval state

## Part 3 - Therapist Billing Loop

Objective: link therapist service evidence to invoice workflows.

Modules:
- Invoice generation from validated logs
- Exception handling (absence/leave/policy rules placeholder or configurable rules)
- Finance status sync inside system (Paid / Queried)
- Therapist invoice history and download view

Exit criteria:
- Invoice values traceable to logs
- Finance status transitions auditable
- Paid reference metadata stored

## Part 4 - Full Case-Centric Expansion

Objective: complete platform scope beyond therapist-first flows.

Modules:
- Lead conversion -> case creation
- Therapist assignment/reassignment history
- IEP workflow + parent acknowledgement tracking
- Parent portal for approved artifacts
- HR attendance exports
- Incident/grievance module (POSH/POCSO restricted routing)
- Advanced dashboards and SLA analytics

Exit criteria:
- One-screen case overview reflects full lifecycle state
- Role dashboards operational
- Sensitive data access controls enforced

---

## Recommended Tech Stack (v1)

Frontend:
- React (Vite)
- Tailwind CSS
- TanStack Query
- React Router v6
- shadcn/ui or Radix UI
- PWA support for therapist mobile usage

Backend:
- FastAPI (Python)
- PostgreSQL
- SQLAlchemy + Alembic
- Redis
- Celery + Redis
- Pydantic v2

Infra/Operations:
- Docker + Docker Compose
- GitHub Actions
- Nginx
- Sentry

Integrations (phased):
- Bitrix24
- Zoho Sign
- Zoho Books
- Razorpay
- WhatsApp/Email (Phase 2+)

---

## Initial Domain Model (Therapist-first subset)

Core entities to implement first:
- `Therapist`
- `Case`
- `DailyLog`
- `ObservationReport`
- `MonthlyReport`
- `Invoice`
- `AuditEvent`

Minimum relationships:
- One therapist to many case assignments (with history)
- One case to many daily logs
- Daily logs feed monthly report and invoice computation
- Every state change writes an immutable audit event

---

## Non-Functional Priorities for Early Phases

- Mobile-first therapist UX
- Fast case and therapist search
- Reliable state transitions (log/report/invoice)
- Immutable auditability
- Spreadsheet-friendly exports (phase-aligned)
- Configurable reminders and thresholds

---

## Execution Rules

- No duplicate manual data entry when lead converts to case
- Case ID is globally unique and searchable
- Parent sees only approved artifacts
- Sensitive incidents are strictly role-scoped
- Administrative overrides require permission and audit logs

---

## Success Metrics (Therapist-first)

- % sessions with same-day daily log completion
- Missing-log rate by therapist/case
- Observation report turnaround time
- Monthly report approval timeliness
- Invoice query rate and payout turnaround time

---

## Suggested Next Implementation Steps

1. Set up backend project skeleton with migration-ready PostgreSQL.
2. Define RBAC roles and auth token claims for therapist and case manager.
3. Implement `Case`, `Therapist`, `DailyLog`, `AuditEvent` models and migrations.
4. Build therapist login + dashboard + daily log mobile flow.
5. Add missing-log reminders and basic case manager visibility.

---

## Versioning

- PRD-aligned baseline: `v1.0`
- This README is the implementation starting point and will evolve module-by-module.

