# Project Handover — InsighteCase

**Audience:** Developers joining Insighte Childcare’s case operations platform with no prior context.  
**Scope:** Technical blueprint reverse-engineered from repository `Insightee/case-manager-new` (facts from code and existing docs; gaps marked explicitly).  
**Last compiled:** September 2026.

---

## Quick Start

→ [04_LOCAL_DEVELOPMENT.md](./04_LOCAL_DEVELOPMENT.md) — clone, env, DB, seed, run API + UI, verify health and tests.

---

## Architecture

→ [02_ARCHITECTURE.md](./02_ARCHITECTURE.md) — system tiers, request flows, deployment topology.  
→ [01_PROJECT_OVERVIEW.md](./01_PROJECT_OVERVIEW.md) — product purpose, users, workflows.

---

## Repository

→ [03_REPOSITORY_STRUCTURE.md](./03_REPOSITORY_STRUCTURE.md) — monorepo layout and ownership boundaries.

---

## Database

→ [06_DATABASE.md](./06_DATABASE.md) — Postgres/SQLite, Alembic, entities, ER diagram.

---

## Backend & API

→ [07_BACKEND.md](./07_BACKEND.md) — FastAPI structure, services, middleware.  
→ [09_API_REFERENCE.md](./09_API_REFERENCE.md) — route inventory (prefix `/api/v1`).  
→ [10_AUTHENTICATION_AND_AUTHORIZATION.md](./10_AUTHENTICATION_AND_AUTHORIZATION.md) — JWT, RBAC, portals.

---

## Frontend

→ [08_FRONTEND.md](./08_FRONTEND.md) — Vite/React portals, routing, API client.  
→ [docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md) — canonical UI/UX contract (Forest Light).

---

## Business & Features

→ [11_BUSINESS_LOGIC.md](./11_BUSINESS_LOGIC.md) — rules embedded in services.  
→ [12_FEATURES.md](./12_FEATURES.md) — end-to-end feature map.

---

## Operations

→ [05_ENVIRONMENT_VARIABLES.md](./05_ENVIRONMENT_VARIABLES.md) — all env vars (no secrets).  
→ [13_THIRD_PARTY_INTEGRATIONS.md](./13_THIRD_PARTY_INTEGRATIONS.md) — Railway, Vercel, R2, ZeptoMail, etc.  
→ [14_DEPLOYMENT.md](./14_DEPLOYMENT.md) — production deploy and rollback.  
→ [15_GIT_AND_DEVELOPMENT_WORKFLOW.md](./15_GIT_AND_DEVELOPMENT_WORKFLOW.md) — PRs, CI, hooks.  
→ [16_TESTING.md](./16_TESTING.md) — pytest, Playwright, CI jobs.  
→ [17_TROUBLESHOOTING.md](./17_TROUBLESHOOTING.md) — common failures.  
→ [18_KNOWN_ISSUES_AND_TECHNICAL_DEBT.md](./18_KNOWN_ISSUES_AND_TECHNICAL_DEBT.md) — debt register.  
→ [19_SECURITY.md](./19_SECURITY.md) — security posture.  
→ [21_HANDOVER_CHECKLIST.md](./21_HANDOVER_CHECKLIST.md) — transfer checklist.

---

## Rebuild From Scratch

→ [20_REBUILD_FROM_SCRATCH.md](./20_REBUILD_FROM_SCRATCH.md) — reconstruction blueprint if the codebase were lost.

---

## Extended index (existing repo docs)

The handover package **does not replace** the living doc index. Use together with:

- [docs/README.md](../README.md) — full documentation index  
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — CTO architecture (May 2026)  
- [docs/RBAC_SCOPE.md](../RBAC_SCOPE.md) — access editor and module catalog  
- [docs/billing-architecture.md](../billing-architecture.md) — invoices and ledger  
- [docs/ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md) — canonical env reference (mirrored in handover 05)  
- [AGENTS.md](../../AGENTS.md) — team deploy split and agent conventions  

**Gaps:** [DOCUMENTATION_GAPS.md](./DOCUMENTATION_GAPS.md)

---

## Critical information (read first)

1. **Product:** Case-centric ops for therapy/homecare/shadow support — every session, log, report, invoice, and incident ties to a **Case** (`case_code`), not a loose client spreadsheet row.
2. **Deploy split:** **Railway** hosts FastAPI + Postgres + Redis (`case-manager-new` service). **Vercel** hosts UI only — project **`insightes-projects/frontend`**; set **`VITE_API_URL`** on Vercel, all secrets on Railway.
3. **Production UI:** Canonical hosts include **`https://www.insighte.org`** (same-origin `/api` rewrites to Railway). Do not use deleted Vercel project `case-manager-new` for UI.
4. **Local default:** SQLite + optional Redis fallback for refresh tokens; Postgres via `docker compose up`.
5. **Migrations:** Postgres/staging/prod use **Alembic only** (`scripts/migrate_production.py`). SQLite dev uses `bootstrap_schema()` + runtime patches — Alembic skipped locally.
6. **Auth:** JWT access + refresh; refresh tokens stored in **Redis** in production (startup fails without `REDIS_URL` when `APP_ENV=production`).
7. **RBAC:** Roles + programme modules (`homecare`, `shadow_support`, `billing`, dynamic service categories) + per-module view/write + feature overrides; **SUPER_ADMIN** bypasses module gates.
8. **Portals:** Separate login surfaces — therapist, parent (`/clientlogin`), admin/staff (`/adminlogin`); wrong portal returns 403 on login.
9. **Parent visibility:** Parents see only **approved/published** artifacts with explicit visibility flags — not raw therapist notes.
10. **Billing/finance:** Heavily **feature-flagged** (`ENABLE_BILLING`, `BILLING_LEDGER_WRITES`, finance cutover flags). Production money writes are intentionally off until cutover runbooks are executed.
11. **Storage:** Production requires **`STORAGE_PROVIDER=r2`** (Cloudflare R2); uploads stream through API, not public URLs.
12. **Email:** ZeptoMail SMTP on Railway; unset SMTP = log-only (`email_logs`, provider `noop`).
13. **No Celery / no in-repo LLM:** Root README lists aspirational stack items; **backend `requirements.txt` has no Celery or OpenAI SDK** — background work is synchronous API + optional external cron scripts under `backend/scripts/`.
14. **CI:** GitHub Actions on `main`/`dev` — backend pytest, Postgres migration proof, frontend build, contributor guards.
15. **Clinical doctrine:** Neuro-affirmative data shapes, structured evidence over free text, AI (if added) must not finalize clinical truth — see repo `.cursorrules` / `AGENTS.md` for product constraints on new work.
