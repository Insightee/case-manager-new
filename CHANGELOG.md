## [Unreleased]

### Fixed
- Production reports match staging/dev: Coming Soon is removed and the reports revamp dashboard is live on insighte.org. Billing remains gated.
- Production API: `ENABLE_CLINICAL_REPORTS_ENGINE=true` so observation and IEP builders are available (was 404 "not available in this environment").
- Alembic `tr1a2n3s4t5` Postgres deploy: use `postgresql.ENUM(create_type=False)` so `case_therapist_transitions` does not re-create `casetherapisttransitionstatus` after the DO-block.

### Added
- Case-centric filtered session log Excel export on admin case logs, therapist case history, and parent session updates (when a child is selected); default summary columns with optional full log content, excluding internal notes for parents.
- Approved session logs can be downloaded as a PDF by case managers, therapists, and parents; pending or rejected logs stay view-only.
- Structured session evidence (flagged off): `iep_goal_items` / `iep_strategy_items` identity registry, `session_goal_entries` / `strategy_use_events` taps on daily-log create/update/resubmit. Alembic `s4e5v6i7d8e9` (parents `ba5p6p7r8v9`). Gate: `ENABLE_STRUCTURED_EVIDENCE` / `VITE_ENABLE_STRUCTURED_EVIDENCE`. Reword-merge debt: `docs/plans/session-structured-evidence-v1-debt.md`.
- Reassignment payout flags: admins can privately flag an outgoing therapist while changing therapist, so finance sees a payout warning for that billing month; the flag clears automatically once the payout is paid and stays hidden from therapists.
- Tech support tickets: `TECH` category for therapist, parent, and staff ticket forms; new tickets route unassigned to the Tech department queue for any Tech staff member to pick up.
- Transition log identity: therapists see handover-day context before submission and persistent role/day labels afterward; Case Managers see the submitting therapist and outgoing/incoming role during approval.
- Therapist My Cases: “Under transition” badge on case cards (and table view) when a therapist handover is scheduled or active.
- Therapist transition workflow: day-type gating, leave-aware three-day calendar, protected rescheduling/cancellation, case write locks, transition log labels, and separate fixed transition pay in therapist invoices and finance payout reports.
- Finance Calculation Engine Steps 1–6 (isolated branch): `MONTHLY_FIXED` case billing, four-way ledger calculator, timestamp eligibility holds, assignment windows / leave ladder / rate periods / add-ons. Alembic `b1c2d3e4f5a6` → `y2z3a4b5c6d7` → `z3a4b5c6d7e8` → `a4b5c6d7e8f9` → `c2d3e4f5a6b7`.
- Flags: `ENABLE_BILLING` (routers), `BILLING_LEDGER_WRITES` (session/log ledger mutations) — both default **false**.
- Hard `MISSING_PACKAGE_COUNT` (no `package_session_count or 1` guess); payout attribution via date-active assignment (`ASSIGNMENT_GAP` / `ASSIGNMENT_OVERLAP`).
- Stage 1 read-only Finance Control Tower: `GET /api/v1/admin/finance-control-tower/*` (SUPER_ADMIN/FINANCE), `VITE_ENABLE_FINANCE_DASHBOARD_V1`, `FINANCE_CUTOVER_COMPLETE`, ConfidenceBadge + Overview tab rebuild.
- Gate 1 local/CI validation tests for Control Tower zero-write / RBAC / write-path matrix (`test_finance_control_tower_gate1_validation.py`).
- Stage 2 client billing: engine-aware invoice composer (`blockingExceptions` / `canBuild` / `postableDraftCharges` / confidence), Zoho Books sync stub seam, `VITE_ENABLE_CLIENT_BILLING` (+ legacy `VITE_ENABLE_BILLING` fallback), admin/parent billing runtime-config endpoints, Forest Light reskin for parent billing + composer.

### Fixed
- IEP identity registration: unique conflict on `(iep_plan_id, statement)` rolls back to a savepoint and re-selects so concurrent GET `/iep-plan` does not 500.

### Docs
- `docs/Cursor_Handover_Finance_Module_Build_Readiness.md`
- `docs/Cursor_Handover_Finance_Dashboard_Stage1.md`
- `docs/Cursor_Handover_Finance_Dashboard_Stage1_Staging_Acceptance.md` (`STAGE_1_LOCALLY_VALIDATED_PENDING_LIVE_STAGING`)
- `docs/finance_control_tower_stage1_human_uat_script.md`
- `docs/Cursor_Handover_Finance_Dashboard_Stage2.md` (`STAGE_2_READY_FOR_STAGING`)
- `docs/Cursor_Handover_Finance_Merge_Local_Runbook.md` (`FINANCE_MERGE_LOCAL_RUNBOOK_GREEN`)
- `docs/Cursor_Handover_Clinical_Reports_Structure.md` (clinical reports schema / UI / generation / storage)
- `docs/Cursor_Handover_Admin_Operational_Reports.md` (Finance / HR / CRM admin Reports exports)
- `docs/Cursor_Handover_Production_Readonly_Postgres.md` + `docs/sql/create_production_readonly_role.sql`

# Changelog

All notable changes to InsighteCase are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

**How to update:** Add bullets under `[Unreleased]` when your PR merges. Before each production release, move `[Unreleased]` into a dated section (`## [YYYY-MM-DD]`) and run `./scripts/pre-release-check.sh`.

---

## [Unreleased]

### Added
- Reusable finance walkthrough fixture (`app/seed/finance_walkthrough_fixture.py`) — 10 IC-WK-* cases for money regression tests.
- `test_finance_money_fixes.py` — correction approve, package drawdown, payout ladder floor, cross-surface outstanding, parent scope, notes, CLEAR pill.
- Loop C: therapist payout settlement (TDS ladder, mock Razorpay batch export, idempotent transfers) — draft PR.
- Loop D: billing dispute → support ticket + finance correction resolve path — draft PR.
- `docs/FINANCE_CUTOVER_RUNBOOK.md` — per-surface flag enablement and sign-off gates (Loop E).

### Fixed
- Finance correction approve creates therapist invoice case line when missing (INVOICE_WRONG linked payout).
- Package drawdown counts in master sheet activity (`PACKAGE_CONSUMPTION` + cycle fallback).
- Payout deduction ladder resolves gross from therapist case line; blocks deductions exceeding after-TDS gross; net never negative.
- Finance control tower outstanding uses `admin_receivables_summary` composed source.
- Parent billing dashboard summary respects month/filter scope (no all-time inflation in scoped views).
- Master sheet CLEAR pill for money-clean rows (reports WARN listed but does not override CLEAR).

### Added
- Case close/reopen: required free-text reason and user-chosen termination/reopen date (past dates allowed); Admin and HR can close and reopen; reopen returns the case to pending allotment for therapist reassignment; close/reopen events appear on the case activity timeline.
- Support tickets: searchable case picker (client name, therapist name, or case code) so shadow (`SS`) and other cases are findable beyond the first 100 alphabetically.
- `GET /api/v1/cases` `search` query param; case list responses include active `therapist_name`.
- Team workflow: `CONTRIBUTING.md`, PR template, CODEOWNERS, pre-push/pre-release scripts, pre-commit hooks, CI contributor guards.
- RBAC editor: bulk Select all / Clear all for service categories, multi-select dropdown, unified clinical features panel.
- People module: central invite policy (max 2 pending per email, one role per email), uniform row actions (staff/therapists/clients), bulk activate/deactivate and bulk invite cancel, client Deactivated when all cases closed with reactivate case flow, case CM edit modal.
- `user.read` permission for Case Manager and Supervisor — read-only Staff directory in People without account management.
- People directory loads all user pages (not just first 100); server-side search by email/name.

### Changed
- Closing a case uses status `CLOSED` with the same side effects as the former deactivate path (cancel future sessions, end assignments, billing cutoff). Bare `PATCH` status=CLOSED is rejected in favor of the audited client-status API.
- Support ticket case picker: load all accessible cases once into a local pool, then filter/scroll in memory (no per-keystroke fetch).
- Therapist onboarding pre-selects only **Homecare** and **Shadow support** by default (not every service category).
- **@antigravity** — Enforced role-specific portal logins on backend and frontend, preventing users from logging in via incorrect portal URLs.
- **@antigravity** — Allowed SUPER_ADMIN, ADMIN, and MODULE_ADMIN users to view the Case Manager home dashboard.
- People → Clients: family list includes case status, `allCasesClosed`, and primary case id for actions.
- Pending invite UI explains cancel vs post-registration login paths.

### Fixed
- Align child-absence "today" with IST (`today_ist`) so walk-in conflict checks match absence eligibility on UTC CI hosts.
- Use current location: reverse geocode now uses API base URL (works on Vercel production).
- Security: active portal users no longer hidden from People when total users exceeds 100.

---

## [2026-06-09]

Therapist org IDs on People and duplicate-child prevention on family onboarding.

### Added
- **Therapist ID** — optional `external_employee_id` on therapist create, onboard, and bulk CSV import; **People → Therapists** shows an editable **Therapist ID** column (HR’s existing reference, separate from internal `users.id`).
- Duplicate-child guard on `POST /api/v1/admin/families` and `POST /api/v1/admin/children`: blocks a second child profile for the same parent when first name, last name, and date of birth match an existing linked child.

### Fixed
- Parent portal **Your Active Cases** listed closed and suspended cases; `/api/v1/parent/cases` and `/api/v1/parent/home` now return only `ACTIVE` and `PENDING_ALLOTMENT` cases (direct case URLs still work for history).
- Admin family onboarding could create duplicate client rows for one parent email (same child entered twice); API now returns 400 with the existing child id.

---

## [2026-05-30]

Support hub, finance/HR ops, billing UX, and environment documentation (`e7d9436`).

### Added
- Support access service and `GET /api/v1/admin/support/capabilities` for hub tab visibility.
- HR reports API/page and finance overview/reports/bulk ops endpoints.
- Demo support tickets in seed data; `test_support_access.py`, finance/HR report tests.
- `docs/ENVIRONMENT_VARIABLES.md`, expanded `docs/README.md`, support/HR handover and ADR-0001.

### Changed
- Admin support hub and sidebar use server capabilities; `tickets`/`incidents` features on billing and hr_ops modules.
- Invoice composer, client billing tabs, therapist payouts dashboard UX.
- Session log test isolation via `session_helpers.py`; incident PATCH requires incidents module feature with DB session.

### Fixed
- Profile session log tests under shared CI DB; incident patch 403 for case managers missing `db` on feature check.

---

## [2026-05-30] — earlier

Therapist reliability, admin onboarding UX, Alembic migration `f7a8b9c0d1e3` (`c93d297`).

---

## Template (copy for new releases)

```markdown
## [YYYY-MM-DD]

### Added
- **@github-user** — Feature summary (#123)

### Changed
- **@github-user** — Behaviour change (#124)

### Fixed
- **@github-user** — Bug fix (#125)
```
