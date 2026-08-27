## [Unreleased]

### Added
- HR report exports include **Child Name**, **Parent Name**, **Therapist Name**, and **Therapist ID** (with Case ID) on all case-linked reports so rows are readable without looking up IDs alone. Downloads are date-stamped (`report-key-YYYY-MM-DD`) and XLSX/PDF titles include the generation date.
- Finance and billing exports include **Client Name** and **Parent Name** on case-linked reports: monthly billing, outstanding balances, collections, ledger missing, manual adjustments (client lines), margin by case, therapist payout preview, and the billing readiness master sheet.
- Bulk attendance and monthly session summary split mid-month therapist replacements into separate case×assignment rows with **Assignment Start** / **Assignment End** (session metrics scoped to each window).
- Secure external integration layer (read-only): machine principals (`integration_clients` / credentials / case grants), short-lived scoped JWTs, masked `/api/v1/integrations/v1/*` APIs, admin client management, audit with `integration_client_id`, and remote MCP Streamable HTTP at `/mcp`. Alembic `i0merge1integration` → `i1integr2api3layer`.

### Changed
- HR report column label **Client Name** renamed to **Child Name** on case-linked operational and legacy exports for clearer identification (CSV/JSON column order also places Child/Parent/Therapist identity columns together near Case ID). Exports also retain a **Client Name** column (same value as Child Name) for finance-aligned naming.
- Therapist invoices and client period charges use the payout-report cycle engine (gross, no TDS). Homecare bills approved sessions at allotment rates; shadow/B2B bills the same calendar days as therapist pay. Transition pay is therapist-only. Build from ledger posts those period charges when the ledger is empty; finance composer payout matches the therapist invoice.
- Finance workspace: **Client invoices** and **Therapist payouts** are parallel money-in / money-out screens for every admin with billing access (no separate Finance home). Client invoices bill system gross; optional TDS is recorded when the payer withholds it. Therapist payouts show gross → TDS → net, raise-on-behalf, notes, and month records. Finance reports stay in the sidebar.
- Raise-a-payout therapist picker is a single search combobox (no separate dropdown).

### Fixed
- Alembic dual head after finance TDS + case Zoho ID merge: empty merge revision `b95440cc4d91` joins `fn9tds0cl1nt` and `z1o2h3o4i5d6`; registered in Postgres migration proof; single-head test expects the merge tip.
- Step 5 billing eligibility tests force a homecare per-session case so shadow/B2B calendar-day blocking does not skip SESSION ledger holds.
- Therapist payout queue no longer auto-applies 10% TDS or treats pending approval as blocked. Finance enters TDS (0 if none), then approves and marks paid from the same workbench.
- Production reports match staging/dev: Coming Soon is removed and the reports revamp dashboard is live on insighte.org. Billing remains gated.
- IEP landing no longer whitescreens: `canSubmit` was referenced but never defined.
- Alembic `tr1a2n3s4t5` Postgres deploy: use `postgresql.ENUM(create_type=False)` so `case_therapist_transitions` does not re-create `casetherapisttransitionstatus` after the DO-block.

### Added
- CM mentor oversight: mentors must be Case Managers; assigned per therapist; mentored therapists’ cases appear on the mentor’s Cases board (read-only except Mark as reviewed on logs). Tag “Reviewed by mentor” visible to CM and therapist. Alembic `m1n2o3p4q5r6`.
- Case Zoho ID: optional `cases.zoho_id` stored at allotment or later, bulk CSV upload with preview on the Cases board, and a Zoho id column on Export records. Alembic `z1o2h3o4i5d6`. Stored only — not used for Zoho Pay yet.
- Finance desk: view-only **Cases** (overview, activity, session dates, billing) and **Therapist leave** (approved leave and approved child absence) for payout cross-check, without clinical write access.
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
