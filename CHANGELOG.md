## [Unreleased]

### Fixed
- Clinical observation `GET /api/v1/reports/{id}/evidence-summary` no longer 500s when a case has session logs: shared `daily_log_narrative` helpers replace the missing `_log_has_narrative` (latent since reports engine launch).

### Added
- Integration scope `ops:aggregate:read` (off until an admin grants it) and `GET /api/v1/integrations/v1/ops/aggregate?from=&to=` for organisation-wide operational counts. Case grants are not required. Counts only; case codes appear on exception lists capped at 50. No migration.
- Parent portal hub: cleaner home (upcoming sessions + CM meetings, attendance alerts, therapist chat tab), next-open-slot booking with meeting-request fallback, profile change-password and collapsible backup contact, email prefs aligned to session logs / leave / billing / meetings. APIs: `POST /auth/change-password`, parent therapist chat, parent meeting requests (assignment-validated). Alembic `31fb30395ec2` → `pmr7req20261005`.
- Staff end-of-day ops snapshot: `GET /api/v1/admin/ops/daily-snapshot?date=YYYY-MM-DD` (Asia/Kolkata, end exclusive at next midnight). Ticket status, incident status, and session-log approval are reconstructed as of that instant from append-only `ops_state_transitions` (Alembic `st4ff4tt3nd2` → `31fb30395ec2`). `GET /incidents` no longer escalates or notifies on read, and `GET /sessions` no longer auto-ends stale sessions. `GET /billing-approvals` lists billing-change requests for staff without billing payloads.
- Staff attendance clock-in: work from office (500 m geofence) or work from home (15 days per IST month), mandatory GPS snapshot at start, HR map link on attendance detail/export. Alembic `tvault001` → `st4ff4tt3nd2`.
- Super-admin `/admin` home is a period-aware leadership overview (IST month): current vs during-period labels, all six case statuses, assignment gaps, session categories, finance snapshot cards, open vs in-progress tickets, in-app staff attendance, work queues that are not summed together, plus drill-downs for **Therapist attention** (`/admin/therapist-attention`) and **Data exceptions** (`/admin/data-exceptions`). Failed modules error locally instead of showing 0. `GET /api/v1/admin/dashboard/summary` now includes `leadership`; `GET /api/v1/admin/leadership/*` serves the detail reports.
- Metric contracts in [docs/REPORT_METRICS.md](docs/REPORT_METRICS.md): payout preview vs collections, Support ticket report vs HR parent-tickets export, login vs activity, current vs period, confirmed vs pending. Production totals are not verified in this environment.
- Support hub **Ticket report** for staff who already handle tickets: read-only counts (status, category, module, who raised, who replied, first-reply hours, aging, repeating questions) and the open plus in-progress queue, with the same filters and an Excel download. POSH and CPP stay as counts. The page does not reply, close, or change a ticket. `GET /api/v1/admin/support/ticket-report` and `GET /api/v1/admin/support/ticket-report.xlsx`.
- Month-end auto-submit raises therapist payout invoices still missing at 11:59 PM IST on the last day of the month (`scripts/auto_submit_month_end_invoices.py`, Railway cron `29 18 * * *`). A manual `--month YYYY-MM` backfill uses the same submit path.
- Integration keys can grant every case (`all_cases`) and read receivables and ledger totals with `finance:read` on `/api/v1/integrations/v1/finance/*` and MCP tools `get_finance_receivables` / `get_finance_ledger`. An empty case list is zero access, not an empty month. Alembic `tp_qual_cards_1001` → `i2all3cases4fin`.
- Integration keys can list and create therapist website profiles (`profiles:read` / `profiles:write`) from `GET/POST /api/v1/integrations/v1/therapist-profiles` and MCP tools `list_therapist_profiles` / `create_therapist_profile`. Listing fields only; create status is always `PENDING`.
- Super admin **Integrations** screen: API keys, webhooks, and MCP, with read/write, token life, key validity, and seven information-access toggles. Writes land as structured `pending_review` signals and cannot complete a report. Alembic `st1ff4tt3nd1` → `bb6328f4ca05`.
- Therapist invoice: **In this pay / Waiting on review / Doesn’t change pay** buckets; next-month **session count** for non-counselling homecare package/per-session; consolidated PDF with Insighte Childcare letterhead (`INVOICE_COMPANY_*`); HR TDS % on profile; submit prefills TDS (default 10%).
- Support & Incidents History KPI cards are clickable filters (tickets / incidents / needs attention / clear). Canonical status helpers (`support_status.py` / `supportStatus.js`) collapse ticket+incident statuses to open / in_progress / closed / escalated without a DB enum migration.
- Expandable Description cells on People & HR report previews (parent support tickets + incident reports).
- Meetings page: Export CSV/Excel, All-years filter, category (Admin/Case manager/Therapist) + multi-select people filter; HR reports Case manager filter is multi-select; inactive-clients adds Case/Therapist Status; parent-portal-usage adds Case Status and excludes only CLOSED/DEACTIVATED; silent parent portal auto-suspend/reactivate on case close/reopen.
- HR case view redesign: `GET /api/v1/hr/caseload` therapist caseload lens with client/therapist/case id, pending-reassignment filter, 14-day slot fill, remuneration gated on `case.billing.update`, and inline status change for `case.status_manage`.
- Admin Service profiles: soft-delete therapist listings (`DELETED` + restore), **Needs listing** / **Deleted** / **No logs 15d** filters and KPIs, audit backfill for historically hard-deleted profiles. Alembic `a8b9c0d1e2f3` → `j0merge2therapist`.
- Cloud Agent dev environment config (`.cursor/environment.json` + `scripts/cloud-agent-install.sh`): reproducible SQLite-based local stack (no Docker/Postgres/Redis needed) that installs backend + frontend deps, seeds the demo database on first run, and starts the FastAPI API (`:8000`) and Vite dev server (`:5173`).
- Shadow cases default to school venue (`SessionMode.SCHOOL`); existing shadow sessions with `HOME` are backfilled. Alembic `k1shadow2lumpsum3` → `k2pct2lumpfix` (leftover `PERCENTAGE` mode cleanup when fixed pay already set).
- Parent Name column on remaining operational downloads (session logs XLSX/PDF, case session-log export, session-log PDF, monthly/observation PDF meta, payout preview, case records CSV, therapist invoice CSV).
- HR report exports include **Child Name**, **Parent Name**, **Therapist Name**, and **Therapist ID** (with Case ID) on all case-linked reports so rows are readable without looking up IDs alone. Downloads are date-stamped (`report-key-YYYY-MM-DD`) and XLSX/PDF titles include the generation date.
- Bulk attendance and monthly session summary split mid-month therapist replacements into separate case×assignment rows with **Assignment Start** / **Assignment End** (session metrics scoped to each window).
- Secure external integration layer (read-only): machine principals (`integration_clients` / credentials / case grants), short-lived scoped JWTs, masked `/api/v1/integrations/v1/*` APIs, admin client management, audit with `integration_client_id`, and remote MCP Streamable HTTP at `/mcp`. Alembic `i0merge1integration` → `i1integr2api3layer`.

### Changed
- PWA stale shortcut recovery: the version notice inside an old installed app has one action (Install / Open InsighteCase) that opens the canonical portal URL with `?reinstall=1` in the browser. The browser landing shows 1) remove the old app, 2) one-tap `beforeinstallprompt` install (Chrome, Edge) or Share > Add to Home Screen (Safari), then a success message. The landing survives login redirects, suppresses the duplicate stale notice and install banner, and is the same in the parent, therapist and admin portals. Auto-update behaviour from #107 unchanged.
- Recurring schedule booking uses one summary notification per parent, therapist, and case manager (deduped on the recurrence group). Selected weekdays that fall before the start date, or that cannot be booked, are reported instead of dropped quietly. The therapist schedule sheet, add-slot sheet, admin schedule modals, and parent booking actions share a Forest sheet that stays above the mobile bottom nav.
- Finance, HR, and Operations **Downloads** share one report library: pick any permitted export, set month / case type / period start and end / report status, then generate or download. Clinical `/admin/reports` stays the review workspace, with a Downloads tab for the same library.
- Clinical `/admin/reports` month is a real month picker; report status and case type stay visible on the queue and all-reports views.
- Shared billing-month parser (`YYYY-MM`, `Oct 2026`, `October 2026`) for HR, finance, and control-tower month filters. IST defaults replace UTC `toISOString()` / `date.today()` on those surfaces.
- Dashboard ticket cards drill into `/admin/support?tab=ticket-report`. Open and in-progress stay separate; needs action is both.
- HR report categories grouped as Attendance and delivery, Work and session ops, Business and cases, Work and approvals.
- Therapist monthly pipeline **Overdue** is unavailable (no due policy); **Not started** is the supported missing-month count.
- Clinical-engine approve requires `monthly_report.approve` (or admin override), not case visibility alone. The engine is not enabled by this change.
- Integration API key sheet grants cases from a filtered picker (all, assigned to me, status) instead of typing IDs.

- Therapist listing quality is scored live (photo, address + pincode, 10-digit phone, 40-word public bio, one degree, services). Submit at 50%+; auto-publish above 80% when photo, pincode, bio, and a degree are present. Below that, admin reviews or requests changes. Login popup stays off after a prior submit.
- Therapist profile completion is a reminder, not a hard gate: sessions and session logs stay available. A popup with deadline **3 October** and **Edit your details** appears on login and again on sign-out until the profile is submitted.
- Leave management report tab and CSV export now call `GET /api/v1/leave/period-export` instead of `/leave/report` so browser ad blockers do not silently block the request. Legacy `/leave/report` remains for API clients.
- Integration profile create stays `PENDING`, refuses an existing row including a soft-deleted listing, and omits login email. Saving a key no longer restarts or revives credential expiry. Goal and IEP reads are paged; strategy rows use `linked_goal_card_id`.
- Production CORS / frontend guards treat **only** `insightes-projects/frontend` as the Vercel UI (`frontend*.vercel.app` + `insighte.org`). Retired `insightecasestaging` / `insightecasetesting` hosts no longer match the default regex and fail Railway startup if listed in `CORS_ORIGINS` or `FRONTEND_URL`.
- CM meeting booking: slot picker and validation use the **case manager host calendar** only (therapist/parent availability no longer hides CM open times); conflict checks still apply to all attendees.
- Scheduling: unified staff availability across CM meetings, therapist meeting requests, parent slot booking, and session materialization; `SCHEDULING_WEEKENDS_ENABLED` org default for Sat/Sun; therapists manage hours on `/therapist/meetings?availability=1` with sync to weekly schedule template.
- Meetings: therapist booking uses the same CM availability API as case managers; unchecked weekdays stay closed after CM saves availability; CM-only availability/Google UI hidden on therapist portal; mobile bottom-sheet modals for book/reschedule/cancel. `Session cancelled` / `Paid leave` / `Unpaid leave` (no extra Still paid / Not billed chips); shadow may choose unpaid while credits remain (paid default); parent invoice lines use the same cancelled wording and show planned next-month session count when present.
- Finance snapshot enabled on insighte.org: Railway `ENABLE_BILLING=true` (read-only tower routes); Vercel Production `VITE_ENABLE_FINANCE_DASHBOARD_V1=true` + `VITE_FINANCE_DASHBOARD_ALLOW_PROD=true`. Ledger writes remain off. Runbook: `docs/FINANCE_SNAPSHOT_PROD_CUTOVER.md`, script: `scripts/enable_finance_snapshot_prod.py`.
- Finance therapist payout preview Excel/CSV columns aligned to lumpsum billing: **Billing Type**, **Client Amount (INR)** (was package-only `Lumpsum Amount`), **Therapist Pay (INR)**, **Therapist Unit Pay (INR)** — no share/% headers. Closed snapshots remap legacy headers on read. Postgres migration proof registry includes Alembic head `v6w7x8y9z0a1`.
- Finance Reports stays **Therapist payout preview** with generate-before-run, IST month, and honest pagination (replacing the 10-report card catalog on this page).
- Therapist compensation is lumpsum-only (`FIXED_LUMP`): UI and writers no longer offer percentage; `resolve_therapist_pay` reads `therapist_fixed_pay_inr` with fallback to legacy `pay_share_amount_inr`. Existing PERCENTAGE rows are copy-migrated (amounts already INR — not re-multiplied).
- Finance **Margin by case** report includes `marginPct` and flags rows where Insighte margin is under 30% (`LOW_MARGIN_BELOW_30`); UI highlights those rows.
- Payout preview / HR billing snapshot columns use lumpsum labels (`Therapist Pay (INR)`, `Per Session Pay (INR)`) instead of legacy “share” / PERCENTAGE wording; closed-month snapshots remap old headers on read.
- Admin Session Logs Sessions tab is card-first on ≤1024px with duration, venue, both status pills, and thumb-zone View/Flag actions.
- Superadmin home billing widget links to **Therapist payouts** (`/admin/therapist-payouts?sub=queue`) — the count is `invoices` in `IN_REVIEW`, not client invoices.
- Finance snapshot + Control Tower: non-production builds default the Stage 1 dashboard on when `VITE_ENABLE_FINANCE_DASHBOARD_V1` is unset; canonical production stays gated unless both that flag and `VITE_FINANCE_DASHBOARD_ALLOW_PROD` are true. Empty-state copy clarifies this is an environment gate, not a broken invoices screen.
- HR report column label **Client Name** renamed to **Child Name** on case-linked operational and legacy exports for clearer identification (CSV/JSON column order also places Child/Parent/Therapist identity columns together near Case ID).
- Therapist invoices and client period charges use the payout-report cycle engine (gross, no TDS). Homecare bills approved sessions at allotment rates; shadow/B2B bills the same calendar days as therapist pay. Transition pay is therapist-only. Build from ledger posts those period charges when the ledger is empty; finance composer payout matches the therapist invoice.
- Finance workspace: **Client invoices** and **Therapist payouts** are parallel money-in / money-out screens for every admin with billing access (no separate Finance home). Client invoices bill system gross; optional TDS is recorded when the payer withholds it. Therapist payouts show gross → TDS → net, raise-on-behalf, notes, and month records. Finance reports stay in the sidebar.
- Raise-a-payout therapist picker is a single search combobox (no separate dropdown).

### Fixed
- Therapist statement PDF (and invoice CSV/breakdown export) returns HTTP 422 with case code when a PACKAGE case has no `package_session_count`, instead of an unhandled 500 (`MISSING_PACKAGE_COUNT`).
- Finance Reports page no longer uses unstyled invoice filter classes, so month, case type, period start/end, and report status are actually pickable on every generateable export. The same library lists payouts, collections, outstanding, and monthly billing.
- Clinical-engine approve rejects therapists with 403 (reviewer role required), not a 400 status-state error.
- Collections totals use `client_payments.payment_status` (not a missing `status` field) and honour cash-period vs invoice-month cohort. Outstanding stays a current snapshot unless the caller asks for a billing-month cohort. Control tower matches therapist `Invoice.month` aliases including `May 2026`. Case status mix includes `PENDING_REPLACEMENT` and `DEACTIVATED`. Monthly/observation completed counts include `PUBLISHED` as well as `APPROVED`. Parent portal export columns say login, not activity.
- CI Alembic head gates now match `tp_qual_level_2703` (academic qualification level) and register that revision in the Postgres migration proof.

- Leave and child absence are unique per **case×day** (disjoint cases the same day stay allowed). Shadow leave counts only dates with a session or booked slot, so a Saturday without a session is not deducted. Paid/unpaid days recompute on approve from live monthly credits; invoice copy explains missing employment start date vs remaining credits.
- Month-spanning leave applies paid credits to the earliest billable days and bills each month by that day’s real paid/unpaid status (no 50/50 rounding that zeroed mixed leave on both invoices).
- Meetings: slot validation no longer blocks double-booking conflict messages; `min_notice_minutes=0` saves correctly; therapist slot picker respects assigned case manager availability windows.
- Therapist session-log submit no longer stops on the duration warning: the banner still prompts a time review, but the first Submit posts the log. Scheduled visits warn only outside a ±15 minute window (not exact scheduled minutes). Session start/end payloads now include `product_module` and `day_type`; therapist home/workspace serialize `day_type` even when Postgres returns a plain string.
- Starting a session when a previous visit still needs a log opens that pending log form first (same Submit) instead of only showing an error. Portal install control is a dropdown with both **Install** and **Refresh**; the primary icon is Install in the browser and Refresh in the installed dock/PWA. Production service workers apply waiting updates automatically.
- Therapist session-log form drops the stacked instructional banners: one short duration line (plus Edit times), a one-line late-reason hint, and a tighter session summary.
- Outgoing Shadow/B2B calendar-day pay no longer treats an out-of-month last approved-log date as a day-of-the-pay-month (e.g. 3 July while computing June). The same day count feeds client gross; receivables and payables both move. Follow-up: [docs/finance/outgoing_calendar_day_clamp.md](docs/finance/outgoing_calendar_day_clamp.md).
- Finance snapshot summary on production: extended control-tower summary fetch to 120s (prod aggregation can exceed the default 30s client timeout and looked like an API connectivity failure).
- Therapist invoice breakdown uses stored payout snapshots (case + session lines) instead of rebuilding from live logs — fixes empty or ₹0 breakdowns on paid/in-review invoices when line items were missing.
- Therapist invoice session breakdown on mobile: stacked session cards, full-height bottom sheets, and thumb-zone Done/Submit actions (no horizontal scroll table).
- Support history KPI counts align with visible rows (search + needs-attention); ticket queue filters and badges use canonical open / in_progress / closed / escalated buckets.
- Case billing forms always show client amount (including monthly); monthly client draft invoices no longer fall back to ₹0.01 MANUAL_FEE when only `client_monthly_rate_inr` is set.
- Therapist pay cannot exceed client billing amount; homecare share under 20% of client amount routes to the low-margin approval queue.
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
