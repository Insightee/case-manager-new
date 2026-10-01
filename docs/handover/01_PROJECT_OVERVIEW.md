# 01 — Project Overview

## What is this application?

**InsighteCase** is the internal operations platform for **Insighte Childcare Pvt. Ltd.** It replaces spreadsheet-led coordination with a **case-centric** system: each client engagement gets a unique **Case ID** (`case_code`), and all operational activity (therapist assignment, therapy sessions, daily session logs, monthly reports, IEP, parent portal content, invoicing, payouts, HR leave, support tickets, incidents) links back to that case timeline.

**One-line for a new developer:** Multi-portal React SPA + FastAPI API + Postgres, with JWT auth and granular RBAC, built therapist-first but expanded to admin, finance, HR, and parent experiences.

---

## Company / product

| Item | Value (from repo) |
|------|-------------------|
| Project name | InsighteCase |
| Legal entity (invoices/PDF defaults) | Insighte Childcare Pvt Ltd |
| Public site references | `insighte.org`, `insighte.in` (email domain) |
| Repository | Monorepo `case-manager-new` (GitHub: Insightee/case-manager-new) |

---

## Problem being solved

From [README.md](../../README.md) and [docs/ARCHITECTURE.md](../ARCHITECTURE.md):

- Fragmented ops (spreadsheets, manual handoffs) → single **Case** source of truth  
- Weak therapist accountability → mandatory session logs, approval queues  
- Opaque parent updates → parent portal with **approval-gated** visibility  
- Audit and scale → immutable audit events, role-scoped sensitive data (incidents)  
- Billing traceability → logs and sessions feed invoice/payout pipelines (staged behind flags)

---

## Target users

| Persona | Role(s) in system | Primary portal |
|---------|-------------------|----------------|
| Therapist | `THERAPIST` | `/therapist/*` |
| Parent / guardian | `PARENT` | `/parent/*` (login `/clientlogin`) |
| Case manager | `CASE_MANAGER` | `/admin/cm/*` (staff admin shell) |
| Module / ops admin | `MODULE_ADMIN`, legacy `ADMIN` | `/admin/*` |
| Super admin | `SUPER_ADMIN` | Full admin |
| Finance | `FINANCE` | `/admin/invoices`, finance tools |
| HR | `HR` | `/admin/people`, leave, HR reports |
| School coordinator | `SCHOOL_COORDINATOR` | **UNKNOWN — VERIFY WITH TEAM** (role exists in seed matrix; portal routing not fully documented in handover) |

Demo credentials: [backend/README.md](../../backend/README.md).

---

## Main workflows (high level)

1. **Case lifecycle:** Create case → assign therapist(s) via `case_assignments` / `case_services` → schedule sessions → log work → review → parent visibility.  
2. **Session day:** Start/end session → submit daily log → admin approve → optional parent notes.  
3. **Reports:** Monthly report draft → submit → admin approve/publish → parent download.  
4. **Clinical reports engine (flagged):** Observation/IEP builders under `/api/v1/cases/.../reports/` when `ENABLE_CLINICAL_REPORTS_ENGINE=true`.  
5. **Booking:** Therapist slots + parent booking APIs (`/booking`, `/slots`, `/scheduling`).  
6. **Billing (flagged):** Therapist invoices, client billing, ledger, finance control tower — see [12_FEATURES.md](./12_FEATURES.md).  
7. **Support:** Tickets, memos, incidents across service lines.  
8. **HR:** Staff attendance, leave, therapist profiles, caseload views.

---

## Major features (inventory pointer)

Full end-to-end map: [12_FEATURES.md](./12_FEATURES.md). Categories include:

- Authentication, invites, password reset  
- Cases, assignments, transitions, clinical profile  
- Sessions, absences, daily logs  
- Monthly + observation reports, IEP plans and documents  
- Invoices, payouts, client billing, finance corrections  
- Parent portal (logs, reports, billing summaries, booking)  
- Admin workbench, CM home, platform stats  
- Integrations API + MCP (optional flags)  
- Notifications, memos, tickets, incidents  

---

## User roles (RBAC summary)

Canonical detail: [docs/RBAC_SCOPE.md](../RBAC_SCOPE.md) and [10_AUTHENTICATION_AND_AUTHORIZATION.md](./10_AUTHENTICATION_AND_AUTHORIZATION.md).

Assignable staff roles: `SUPER_ADMIN`, `MODULE_ADMIN`, `CASE_MANAGER`, `FINANCE`, `HR` (+ legacy `ADMIN` migrating to `MODULE_ADMIN`).  
Client-facing: `THERAPIST`, `PARENT`.  
Deprecated for new invites: `VIEWER`, `SUPERVISOR`.

---

## Technology stack (as implemented)

| Layer | Technology | Evidence |
|-------|------------|----------|
| Frontend | React 19, Vite 8, React Router 7, TanStack Query 5, Tailwind 4, TipTap, PWA plugin | `frontend/package.json` |
| Backend | FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2, Alembic | `backend/requirements.txt` |
| Database | PostgreSQL 16 (prod/Docker); SQLite default local | `docker-compose.yml`, `config.py` |
| Cache / sessions | Redis 7 (refresh tokens) | `redis` in requirements, `security.py` |
| Object storage | Local filesystem or Cloudflare R2 (boto3) | `STORAGE_PROVIDER`, `app/storage/` |
| Email | SMTP (ZeptoMail in prod) | `notification_service`, env vars |
| CI | GitHub Actions | `.github/workflows/ci.yml` |
| API docs | OpenAPI at `/docs` | FastAPI default |

**Not present in backend dependencies (despite README “Recommended stack”):** Celery, Nginx in repo, Sentry SDK, in-process LLM clients — treat README stack as **roadmap/aspiration** unless added later.

---

## Current deployment model

| Environment | Frontend | API | Database |
|-------------|----------|-----|----------|
| **Production** | Vercel `insightes-projects/frontend`; domains `www.insighte.org` (+ legacy Vercel URL) | Railway service `case-manager-new` | Railway Postgres |
| **Local dev** | Vite `:5173`, proxy `/api` → `:8000` | Uvicorn `:8000` | SQLite or Docker Postgres |
| **CI** | `npm run build` with fixed `VITE_API_URL` | pytest on SQLite test DB + Postgres migration job | Ephemeral |

Detail: [14_DEPLOYMENT.md](./14_DEPLOYMENT.md), [docs/RAILWAY_VERCEL.md](../RAILWAY_VERCEL.md).

---

## Product principles (constraints on new work)

From `.cursorrules` / `AGENTS.md` (institutional rules):

- **Connection before correction** — UX must guide, not punish; immediate interaction feedback, with clinical/finance outcomes confirmed after server success ([docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md)).  
- **Neuro-affirmative clinical model** — strengths/support/environment, not deficit-first diagnosis architecture.  
- **Case + assignment history** — do not rely on `case.therapist_id` alone.  
- **Token economy** — no LLM calls on `onChange`/page load; explicit user actions only.  
- **Exception queue** — case managers review exceptions, not every row (when `review_queue` triggers apply).

These are **product/engineering constraints** for extensions, not necessarily fully enforced in every legacy code path.
