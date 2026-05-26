# Role model & module access — phased backlog

Tracks the **access-control / role-model** programme (distinct from [PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md) release phases A/B/C).

**Source of truth for editor behaviour:** [RBAC_SCOPE.md](./RBAC_SCOPE.md)

---

## Programme modules (commercial SKUs)

| Module ID | Label | Case products | Typical roles |
|-----------|-------|---------------|---------------|
| `homecare` | Homecare | `homecare` | CM, Module Admin, HR |
| `shadow_support` | Shadow Support | `shadow_support` | CM, Module Admin, HR |
| `billing` | Billing & finance | (org-wide) | Finance, Module Admin |
| *(dynamic)* | Service categories | same as category id | Configured per category |

**Features inside clinical modules:** `cases`, `session_logs`, `reports`, `iep`, `cm_meetings`, `tickets`, `incidents`.  
**Billing module:** `invoices`, `dashboard`.

---

## Phase status

| Phase | Goal | Status |
|-------|------|--------|
| **RBAC v1** | Access editor, grants on user, catalog + preview APIs | **Done** |
| **C** | Case Manager home `/admin/cm`, CM nav, caseload API | **Done** |
| **B** | Per-module view/write on APIs + main case UI | **Done** |
| **A** | Migrate `ADMIN` → `MODULE_ADMIN`; hide/retire `VIEWER` & `SUPERVISOR` for new users | **Done** |
| **D** | CM change / suspension approval workflows | **Pending** |
| **E** | Rename `SUPERVISOR_REVIEW` doc status; map supervisor duties to CM | **Done** |

---

## RBAC v1 (done)

- [x] `module_access_grants`, `feature_overrides`, `is_view_only` on users
- [x] `GET /api/v1/admin/rbac/catalog`, `POST /api/v1/admin/rbac/preview`
- [x] Staff invite/create/PATCH wired to grants
- [x] `RbacEditor` on People → Staff
- [x] `MODULE_ADMIN` role + `moduleadmin@demo.com`
- [x] `/auth/me` exposes `modules[].access`, `is_view_only`
- [x] Nav filtering via `moduleIds` + features in `PortalShell`
- [x] View-only / partial view-only banners

---

## Phase B — per-module write (done)

### Backend

- [x] `module_write.py` helpers (`ensure_case_write_access`, `ensure_billing_write_access`, `ensure_feature_write_access`, `guard_clinical_case`)
- [x] Cases, assignments, daily logs, admin case/IEP/status-request routes
- [x] `require_mutation_permission` for global view-only users
- [x] Invoice / client-billing / payout mutations (`ensure_billing_write_access`)
- [x] Bulk report approve/reject (`guard_clinical_case` + reports feature)
- [x] Tickets staff mutations, incidents PATCH/owner messages, CM meetings CRUD
- [x] Staff user create/PATCH access fields (`require_mutation_permission`)

### Frontend

- [x] `useModuleWrite` hook + `AuthContext` module helpers
- [x] Cases pipeline, detail, drawer, kanban
- [x] Workbench status requests, observations, client claims, reports sections
- [x] Allotment wizard submit gate
- [x] Reports page/drawer/table, client invoices, therapist payouts, IEP builder, tickets panel

---

## Phase A — role migration (done)

- [x] Seed/docs: `MODULE_ADMIN` for ops users; demo `admin@` / `support@` migrated
- [x] `backend/scripts/migrate_staff_roles.py` for existing DBs (or re-run `demo_seed`)
- [x] `SUPERVISOR` / `VIEWER` / `ADMIN` not assignable via API or RBAC catalog
- [x] Demo `supervisor@` → `CASE_MANAGER`; `viewer@` → `CASE_MANAGER` + view-only grants
- [x] `REVIEW_ROLE_MATRIX.md`, login hints, `dashboard_variant` on `/admin/home`
- [x] Role dashboards: CM `/admin/cm`, Finance queues on `/admin/invoices`, Module Admin `/admin`

---

## Phase D — CM approval workflows (pending)

- [ ] Case manager reassignment requires approver (admin/module admin)
- [ ] Case suspension/close approval queue (or status-request integration)
- [ ] Notifications to approvers

---

## Phase E — supervision naming (done)

- [x] Document status `SUPERVISOR_REVIEW` → `CM_REVIEW` (Alembic + API normalization for legacy rows)
- [x] Case document review queue uses case manager permissions (not legacy SUPERVISOR role)
- [x] Therapist profile supervision dropdowns use CM / Module Admin (not SUPERVISOR role)
- [x] UI labels: “Case manager review”, “CM / mentor” on profiles

---

## Other app modules / epics (not access phases)

| Area | Notes |
|------|--------|
| **Tickets & incidents** | Cross programme; feature flags per module |
| **IEP goals (R-009)** | Product roadmap P1 |
| **Parent payments (R-008)** | Billing module |
| **Pipeline scale (R-006)** | Cases API pagination |
| **Therapist onboarding** | Still uses legacy `ModulePicker` — should adopt grants shape later |
| **HR portal** | Shares People page; HR role + modules |
| **Exports / audit pack (R-017)** | P3 compliance |

---

## Demo accounts (quick test)

| Email | Use for |
|-------|---------|
| `moduleadmin@demo.com` | Full programme modules, write |
| `casemanager@demo.com` | `/admin/cm`, team cases |
| `viewer@demo.com` | CM view-only → `/admin/cm` |
| `supervisor@demo.com` | CM shadow caseload → `/admin/cm` |
| `finance@demo.com` | Billing only |

Password: `demo123` — see [backend/README.md](../backend/README.md).
