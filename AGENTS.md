## Learned User Preferences

- When implementing an attached plan, do not edit the plan file; use existing todos and mark them `in_progress` rather than creating duplicates.
- Prefer phased delivery (core backend and admin MVP first, then tickets, IEP, exports) unless the user explicitly asks for a full single-pass build.
- Keep a case-centric data model: one `User` with roles/permissions, `case_assignments` with history—never rely on `case.therapist_id` alone.
- Set client billing amounts and therapist pay share when a case is created; admin/HR may revise later.
- Assign module-based product access when creating admin/support users (homecare, shadow_support, billing, etc.).
- Therapist access is scoped to own cases, session logs, invoices, tickets, and profile—not other therapists' data.
- Incident reporting should be available across relevant service lines (e.g. shadow and homecare), not a single product only.
- Use frontend/UI design skills when improving portal layouts (login sizing, admin dashboard density, therapist quick actions).
- Invoice UX should support case-by-case preview, session review, late/extra sessions before submit, and admin breakdown review.

## Documentation

- [docs/README.md](docs/README.md) — full documentation index
- [CONTRIBUTING.md](CONTRIBUTING.md) — team PR workflow, pre-push/release scripts, hooks
- [CHANGELOG.md](CHANGELOG.md) — update `[Unreleased]` on every merge; date section before prod release
- [docs/TEAM_OWNERSHIP.md](docs/TEAM_OWNERSHIP.md) — area owners and CODEOWNERS
- [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md) — branch protection (admins)
- [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) — all env vars (local, Railway, Vercel)
- [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) — delivery, RBAC, billing, deploy, and agent checklists (from chat workflow capture).
- [docs/DATA_IMPORT.md](docs/DATA_IMPORT.md) — production bulk import for therapists, families, and cases (templates and API order).

## Team workflow (humans + agents)

- **Do not push directly to `main`.** Use a PR; CI (`backend`, `frontend`, `vercel-monorepo-build`, `contributor-guards`) must pass.
- **Before push:** `./scripts/pre-push-check.sh` or `make check`.
- **Before production release:** `./scripts/pre-release-check.sh` + [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) + move [CHANGELOG.md](CHANGELOG.md) `[Unreleased]` to a dated heading.
- **One concern per PR** when possible; RBAC/migration changes need tests.
- Agents: still **commit only when the user asks**; when committing, follow [CONTRIBUTING.md](CONTRIBUTING.md) message style.

## Deploy split (do not confuse names)

| Platform | Project / service name | What runs there |
|----------|------------------------|-----------------|
| **Railway** | `case-manager-new` (repo `Insightee/case-manager-new`) | FastAPI API, Postgres, Redis — all backend env vars |
| **Vercel** | **`insightes-projects/frontend`** only (`prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN`) | Vite React UI — **`VITE_API_URL` only** |

Never use Vercel project `case-manager-new` (deleted duplicate). CLI: `vercel … --scope insightes-projects --project frontend`. See [docs/RAILWAY_VERCEL.md](docs/RAILWAY_VERCEL.md).

## Learned Workspace Facts

- Monorepo layout: `backend/` (FastAPI, SQLAlchemy, Alembic), `frontend/` (Vite + React + Tailwind), `docker-compose.yml` for Postgres, Redis, and API.
- Local dev: from `backend/` run `python3 -m app.seed.demo_seed` then `uvicorn app.main:app --reload --port 8000`; from `frontend/` run `npm run dev` on port 5173 with `/api` proxied to the API.
- Demo sign-in uses seeded accounts such as `superadmin@demo.com` and `therapist@demo.com` with password `demo123` (see `backend/README.md` for the full role matrix).
- `Case` is the operational source of truth; sessions, daily logs, reports, invoices, payouts, and incidents link back to cases.
- Seeded roles include SUPER_ADMIN, ADMIN, CASE_MANAGER, SUPERVISOR, THERAPIST, FINANCE, HR, PARENT, and SCHOOL_COORDINATOR.
- Case billing uses `PER_SESSION` and `PACKAGE` types with therapist compensation modes (e.g. percentage share, fixed lump); logic lives in `invoice_billing_service` and admin case forms.
- Product modules are defined in `backend/app/core/modules.py` (`homecare`, `shadow_support`, `billing`) and gate admin/support feature access.
- Frontend portals live under `admin-portal/`, `hr-portal/`, therapist routes, and parent routes, with role-aware login on `LoginPage.jsx`.
- After schema changes, run Alembic migrations (`alembic upgrade head` from `backend/`) before re-seeding or E2E checks.
- Backend tests run with `python3 -m pytest app/tests -q` from `backend/`; billing and admin portal have dedicated test modules.
- The stack is SQL-based (SQLite default locally, Postgres via Docker)—not MongoDB; plugin guidance is advisory only.
