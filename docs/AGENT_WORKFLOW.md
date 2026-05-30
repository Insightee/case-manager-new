# Agent & delivery workflow (from project chats)

Durable preferences extracted from recent Cursor sessions on InsightCase / case-manager-new. Use this when planning features, imports, deploys, or agent tasks—not as a product spec.

**Related:** [ARCHITECTURE.md](./ARCHITECTURE.md), [RBAC_SCOPE.md](./RBAC_SCOPE.md), [HANDOVER_SUPPORT_HR.md](./HANDOVER_SUPPORT_HR.md), [adr-0001-support-hub-access-scopes.md](./adr/adr-0001-support-hub-access-scopes.md), [DEPLOY.md](./DEPLOY.md), [DATA_IMPORT.md](./DATA_IMPORT.md), [../CONTRIBUTING.md](../CONTRIBUTING.md), [../CHANGELOG.md](../CHANGELOG.md), repo root [AGENTS.md](../AGENTS.md).

---

## Target workflow

Build and operate a **case-centric** healthcare ops platform (therapist, parent, admin/CM/HR/finance portals) with **phased delivery**, **module-scoped RBAC**, **real SMTP in production**, and **green CI** before treating deploy env vars as done.

---

## Evidence corpus (parent chats only)

| Topic | Parent conversation | Approx. focus |
|--------|---------------------|---------------|
| Local dev, admin build, RBAC, billing, UI | [Case manager build](3264f04a-7f89-412c-a5f2-4a866995b3e1) | Primary thread: architecture, phased plans, portals, invoices, CI/Railway/Vercel, local host, production import |
| Deploy plugins / commit | [Vercel deploy](5272ef36-8e43-43c6-aead-635088fd0512) | Cloudflare/Vercel, commit to GitHub |

Subagent runs (tests, explore, CI fix) informed implementation but are not cited here.

---

## Preference profile

### Shipping & planning

| Preference | Confidence | Rule for agents |
|------------|------------|-----------------|
| **Phased delivery** over single mega-pass | Strong | Default: core backend + admin MVP → tickets, IEP, exports unless user asks for full build in one go. |
| **Do not edit attached plan files** | Strong | Implement from plan; update todos (`in_progress` / `completed`), do not duplicate todo lists. |
| **Adopt user’s data model corrections** | Strong | One `User` + roles; `case_assignments` with history; `Session` ≠ `DailyLog`; no reliance on `case.therapist_id` alone. |
| **Complete plan todos** | Strong | When user says “implement the plan” / “don’t stop until todos done”, finish all listed todos before stopping. |
| **Commit only when asked** | Strong | Do not git-commit unless the user explicitly requests it. |

### Access control & product modules

| Preference | Confidence | Rule for agents |
|------------|------------|-----------------|
| **Module-based admin access** | Strong | `homecare`, `shadow_support`, `billing` on user create; gate features via module + permissions. |
| **Therapist scope = own data** | Strong | Own cases/assignments, logs, reports, invoices, tickets, profile—not peers’. |
| **Incidents on all relevant lines** | Strong | Shadow + homecare (not one product only). |
| **Legacy roles** | Medium | Migrate `ADMIN` → `MODULE_ADMIN`, `VIEWER`/`SUPERVISOR` → `CASE_MANAGER` in prod; see `backend/scripts/migrate_staff_roles.py`. |
| **Staff tiers** | Strong | SUPER_ADMIN, MODULE_ADMIN (module-scoped), CASE_MANAGER, support-style module admins, FINANCE, HR, THERAPIST, PARENT. |

### Billing & invoices

| Preference | Confidence | Rule for agents |
|------------|------------|-----------------|
| **Set billing at case create** | Strong | Client rate/package + therapist pay share (%, fixed lump) on allot/create; HR/admin may revise later. |
| **PER_SESSION vs PACKAGE** | Strong | Extra sessions: per-session rate or package proration per `invoice_billing_service` / case fields. |
| **Therapist invoice UX** | Strong | Case-by-case preview, review sessions, drop late/extra before submit; admin sees breakdown. |

### UI / UX

| Preference | Confidence | Rule for agents |
|------------|------------|-----------------|
| **Use design skills for portals** | Strong | Login sizing, admin dashboard density, therapist quick actions / modals. |
| **Role-aware login** | Strong | Admin, therapist, parent entry points visible—not therapist/client only. |
| **Data-rich admin** | Medium | High-fidelity, operational dashboards (kanban, queues, filters). |

### Email & deploy

| Preference | Confidence | Rule for agents |
|------------|------------|-----------------|
| **Real SMTP in prod** | Strong | ZeptoMail on `insighte.in` senders; env on Railway only; document in [EMAIL_DNS.md](./EMAIL_DNS.md). |
| **Never commit secrets** | Strong | Rotate tokens if pasted in chat; use `.env` / platform env. |
| **Monorepo deploy** | Strong | **Vercel** = team `insightes-projects`, project **`frontend`** only (`VITE_API_URL`). **Railway** = service **`case-manager-new`** (API + secrets). Never run `vercel env` against `case-manager-new`. |
| **CI must pass** | Strong | Backend pytest + frontend build; Linux CI may need `npm install` vs `npm ci` if lockfile drifts. |
| **Postgres prod schema** | Strong | `alembic upgrade head` / `scripts/migrate_production.py`; SQLite local uses bootstrap patches. |

### Data onboarding

| Preference | Confidence | Rule for agents |
|------------|------------|-----------------|
| **demo_seed = dev only** | Strong | Production therapists/clients via admin bulk APIs or import script—not demo re-seed. |
| **Match keys: email + case_code** | Strong | No external employee/client ID columns yet; mapping sheet → resolve to internal IDs. |
| **Import order** | Medium | Staff → therapists → families → case allot (+ billing). See [DATA_IMPORT.md](./DATA_IMPORT.md). |

---

## Adopt / consider / dismissed

**Adopt (encode in work):**

- Phased delivery and case-centric schema rules above.
- Module RBAC, therapist scoping, billing-at-allotment, invoice preview flows.
- Plan/todo discipline; commits on request only.
- Deploy split: Railway API + Vercel UI; document env; green CI.

**Consider (context-dependent):**

- Bulk case import script for hundreds of rows (API exists for therapists/clients; cases are per-row allot today).
- `external_employee_id` / `external_client_ref` columns if HR/CRM IDs must live in DB.
- Node 20 vs 24 in GitHub Actions (warnings only until upgraded).

**Dismissed (do not treat as standing prefs):**

- Frontend-only / mock-data forever (superseded by full backend).
- One-shot “full build everything” when user already chose phased in plan Q&A.

---

## Agent checklist (quick)

1. Read [AGENTS.md](../AGENTS.md), [CONTRIBUTING.md](../CONTRIBUTING.md), and this file for standing prefs.
2. For schema/API work: assignments + sessions + audit; pass `db` into module feature checks where required.
3. For UI: role-aware login; scoped therapist data; admin density.
4. For prod: migrate → import ([DATA_IMPORT.md](./DATA_IMPORT.md)) → env on Railway/Vercel → [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) smoke login.
5. Run `./scripts/pre-push-check.sh` or `python3 -m pytest app/tests -q` (backend) before claiming CI-ready.
6. Update [CHANGELOG.md](../CHANGELOG.md) `[Unreleased]` when user asks to commit/merge substantial work.
7. Do not commit or push unless asked.

---

## Open questions (non-blocking)

- Preferred production import: admin UI batches only vs committed `import_production.py`?
- Should legacy case numbers always become `case_code`, or only notes until format is validated?
- Canonical HR source of truth for therapist approval before allot (profile status)?

Update this doc when new explicit preferences appear in parent chats (re-run workflow-from-chats quarterly or after major initiatives).
