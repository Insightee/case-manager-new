# Business logic registry

Founder-readable rules with audit IDs. **Source of truth** = the place that actually decides, not the nicest comment.

Columns: **SOT** = source of truth. **FE** = frontend. **BE** = backend. **DB** = tables. **Tests** = closest automated cover. **Recent?** = changed in last ~90–120 days. **Conflict?** = see `04_CONFLICT_AND_LEGACY_REGISTER.md`.

Evidence grade is **CONFIRMED** unless marked.

---

## CASE — case and client lifecycle

| ID | Domain | Rule in plain English | SOT | FE | BE | DB | Other consumers | Tests | Recent? | Conflict? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CASE-001 | Case | A new case starts as **Pending allotment**, not Active. | `Case.status` default | Allotment UI | `allotment_service.allot_case` | `cases.status` | Calendar `pending_allotment` | allotment / client status | May 29 activate gate | With CASE-003 |
| CASE-002 | Case | Activating allotment requires an **active assignment** and moves Pending → Active. | `activate_allotment` | Allotment wizard | `allotment_service.activate_allotment` | `cases`, `case_assignments` | Parent invite, offer sent | allotment tests | May 29 | Soft acceptance off |
| CASE-003 | Case | Assigning a therapist can **also** promote Pending → Active (not only activate). | `assignments.assign_therapist` + `change_client_status` | Admin assign | `assignments.py` | `cases.status` | Audit | `60e06f2c` era tests | Jul 10 | **Yes** vs CASE-002 |
| CASE-004 | Case | Live client status **is** case status. There is no second client_status column. | `cases.status` | Status cards | `client_status_service` | `cases` | Finance cutoff, parent hide | `test_client_status.py` | Jun 16 | Naming only |
| CASE-005 | Case | Admin/HR may: Pending→Active; Active→Suspended / Pending replacement / Closed; Suspended or Replacement→Active or Closed; Closed/Deactivated→Pending (reopen). | `ADMIN_ALLOWED_TRANSITIONS` | `CaseClientStatusCard` | `change_client_status` | `cases`, `case_client_status_audit` | Bookings | `test_client_status.py` | Jun–Jul | DEACTIVATED leftover |
| CASE-006 | Case | Therapists may **request** Active→Suspended/Closed and Suspended→Active. They cannot request replacement. | `THERAPIST_ALLOWED` | Status request (limited) | `case_status_request_service` | `case_status_requests` | CM notify | `test_case_status_requests.py` | Jun 16 | Approve fallback |
| CASE-007 | Case | New closes must be **CLOSED**, not DEACTIVATED. DEACTIVATED is legacy terminal with same close side-effects. | Comment + transition map | Labels “Closed (legacy)” | `client_status_service` | enum still has DEACTIVATED | Billing cutoff | client status | Jun 16 | Billing filters still offer DEACTIVATED |
| CASE-008 | Case | Close **ends** active assignments, cancels future slots/sessions and recurring schedules. Suspend/replace **cancel future bookings only** — assignments stay. | `apply_case_closed_side_effects` vs `_cancel_future_bookings` | — | `case_close_service`, `client_status_service` | assignments, slots, sessions | Payout, parent | `test_case_close.py` | Jun 17 | vs CASE-020 |
| CASE-009 | Case | Close is blocked if draft/generated **client invoices** exist. | `assert_no_blocking_invoices_for_close` | Error on close | `case_close_service` | `client_invoices` | Finance | case close tests | | Flag-dependent |
| CASE-010 | Case | Last non-terminal case Closed/Deactivated **deactivates parent login**. Reopen can reactivate only if last suspend was auto. | `_maybe_auto_suspend_parent_portal` | — | `client_status_service` | `users.is_active` | Auth | `test_parent_portal_auto_suspend.py` | | No email |
| CASE-011 | Case | Parents do not see Closed or Deactivated cases. **Suspended stays visible.** | `PORTAL_HIDDEN_CASE_STATUSES` | Parent lists | `case_portal_visibility` | — | Parent APIs | parent portal tests | Jun 9–17 | Product question |
| CASE-012 | Case | Reopen Closed/Deactivated needs admin/HR/`admin.override`. | `user_can_reopen_case` | Status card | `client_status_service` | `cases.status` | | client status | | |
| CASE-013 | Case | Case manager has `case.update` so **can** change status via the “update or status_manage” helper. CM does **not** have `case.assign`. | `ROLE_PERMISSIONS` | Hidden assign | `user_can_manage_client_status` | — | | `test_phase0_access_lockdown.py` | Jul 10 | Easy to confuse with assign |
| CASE-014 | Case | B2B cases are visible to CMs even when not assigned. | case scope | Admin list | `case_scope_check` | `cases` | | Jul 25 carve-out | Jul 25 | vs Jun 20 assigned-only |
| CASE-015 | Case | Commercial terms (client rate, package, therapist lump, billing type) are set **at case create** and may be revised later with history. | `cases` billing columns | `CaseBillingForm` | allotment + `billing_rate_history_service` | `cases`, `case_billing_rate_changes` | Invoices | billing tests | Aug 29 as-of | |
| CASE-016 | Case | Profit below ₹5,000 routes to billing approval before allotment proceeds. | `billing_minimum_profit_inr` (5000) | Allotment | `billing_approval_service` | `billing_approval_requests` | | `test_low_margin_billing_approval.py` | Aug 17 | |
| CASE-017 | Case | Shadow and B2B require day type Half or Full at allotment. Homecare does not. | `DAY_TYPE_PRODUCT_MODULES` | Allotment | `validate_allotment_day_type` | `cases.day_type` | Payout calendar-day | day type tests | Aug 13 | INTENTIONAL |
| CASE-018 | Case | Reassignment requires billing setup (rates on the new assignment). | transition / assign | Transition UI | assignment + billing approval | assignment snapshot | Payout flags | reassignment billing tests | Aug 4 | |
| CASE-019 | Case | Therapist “intake” can create a Pending allotment case with provisional assignment. Recurring slots can still be booked. | `therapist_intake_service` | Intake form | intake + calendar | `cases`, slots | Calendar | `test_pending_allotment_recurring_calendar.py` | | Pending + booked |
| CASE-020 | Session | A therapist **cannot start** a session if the case is Closed or Deactivated, or a pause/close request is pending. **Suspended and Pending replacement are not blocked.** | `assert_case_allows_new_session` | Start button | `session_service` | `cases.status` | | session start tests **do not cover suspend** | | **Yes** vs CASE-008 |
| CASE-021 | Session | Start is allowed only on **today (IST)** for scheduled sessions; past/future → forgot-to-log path. | `today_ist` | `sessionStartRules.js` | `start_session` | `sessions.scheduled_date` | | `test_session_start_rules.py` | Jun | Aligned FE/BE |
| CASE-022 | Session | Cannot start if the latest completed visit on that case has **no daily log**. | `pending_log_gate_service` | Conflict codes | `assert_may_start_new_session` | sessions, daily_logs | | `test_pending_log_gate.py` | Aug 3 | |
| CASE-023 | Session | Cannot start if child-absence is pending/approved. | absence asserts | FE parsers | `session_absence_service` | `session_absence_requests` | | `test_session_absence.py` | Jun 12 | |
| CASE-024 | Session | Parent acceptance can block start **only if** `acceptance_gating_enabled` (default **false**). | settings | — | `assert_therapist_may_start_session` | assignment timestamps | | | May 29 | Soft |
| CASE-025 | Session | End session does **not** create a log. Day-end cron ends IN_PROGRESS at 22:00 IST without a log. | `end_session`, `auto_close_open_sessions_at_day_end` | Time confirm | session + day-end | `sessions` | Pending-log gate | `test_session_day_end_autoclose.py` | Jun 24 | |
| CASE-026 | Session | Log can be created only when session is **COMPLETED**. | `create_daily_log` | Log form | `daily_logs.py` | `daily_logs.session_id` unique | | daily log tests | | |
| CASE-027 | Session | Forgot-to-log can complete a scheduled past/today session **without** IN_PROGRESS. | `complete_forgotten_session` | Forgot form | `session_service` | `sessions` | | | | |
| CASE-028 | Session | Void-before-log: completed, no log, not invoiced, within 168 hours → back to scheduled or cancelled. | `void_session_before_log` | | `session_service` | sessions | | `test_session_void_before_log.py` | | |
| CASE-029 | Session | Statuses `NO_SHOW` and `RESCHEDULED` exist on the enum; start/end/void/absence paths reviewed **do not write them**. | enum only | Filters omit them; add **FLAGGED** | — | `sessions.status` | | none | May 20 | FE/BE drift |
| CASE-030 | Assignment | There is **no** `case.therapist_id`. Live therapist = active `case_assignments` row. | assignments | Case hub | `assignment_service` | `case_assignments` | All clinical + pay | doctrine + models | | Do not reintroduce |
| CASE-031 | Assignment | Allotment **picker** requires active user + product-eligible + (default) approved profile. Assignment **API does not re-check**. | `list_allotment_therapists` vs `create_assignment` | Picker | allotment vs assignment | users, profiles, assignments | | `test_allotment_therapist_scope.py` only picker | | **Yes** HR-003 |
| CASE-032 | Assignment | Creating an assignment ends the previous one as TRANSFERRED (replace-in-service). | `replace_assignment_in_service` | | `assignment_service` | assignments | Payout flag | | | |
| CASE-033 | Transition | Handover uses exactly **three IST dates**; completion can end incoming assignment per service logic. | `therapist_transition_service` | Transition UI | same | `case_therapist_transitions` | Payout split | `test_therapist_transition.py` | Aug 13–20 | |
| CASE-034 | Session | A therapist cannot start a new session if a pending-log, child-absence, wrong day, or closed case blocks it. Suspended case is **not** in that list. | combined start asserts | `sessionStartRules.js` | `start_session` | sessions, cases | | start + gate tests | | See CASE-020 |

---

## HR — people, leave, eligibility

| ID | Domain | Rule in plain English | SOT | FE | BE | DB | Other | Tests | Recent? | Conflict? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HR-001 | People | Login requires `users.is_active`. Employment label is a **different** field. | `auth_service` | Login | auth | `users` | Parent auto-suspend | auth tests | | vs HR-002 |
| HR-002 | People | HR can set `employment_status`; that sets `is_active` only on the HR update path. Admin deactivate flips `is_active` **only**. Therapist PATCH `/me` can set employment **without** `is_active`. | three write paths | People, profile | `hr.update_therapist`, `admin.deactivate_user`, `auth.update_me` | `users` | | **gap** | | **Yes** |
| HR-003 | People | Exit/inactive does **not** end case assignments. | none | Caseload still lists | — | `case_assignments` stay ACTIVE | Payout, sessions | **gap** | | **Yes** CASE-031 |
| HR-004 | People | Direct onboard creates therapist profile as **APPROVED** immediately. | `_create_therapist_profile` | Onboard | `therapist_onboarding_service` | `therapist_profiles.status` | Allotment | profile tests | | |
| HR-005 | Leave | Leave statuses: Pending, Approved, Rejected, Cancelled. Types: Annual, Sick, Casual, Unpaid. | `leave.py` model | Leave pages | leave APIs | `therapist_leaves` | Slots | leave tests | Jun 20 rewrite | |
| HR-006 | Leave | Credits: **1 per calendar month** from employment start. **Homecare-only leave is always unpaid.** Shadow leave can consume credits. | `_paid_unpaid_for_leave` | HR leave | `leave_policy_service` | profiles + leaves | Finance deduction is separate | `test_leave_policy.py` | Jun 20 | vs FIN-020 |
| HR-007 | Leave | Approved non-retro leave cancels booked slots in range and blocks available slots. | `notify_leave_approved` | | `leave_notification_service` | slots, sessions | Parents notified for selected cases | `test_leave_notifications.py` | Jun 26 scope | |
| HR-008 | Leave | Finance desk **sees approved leave only** and cannot approve. | `list_leave` + `is_finance_desk_user` | `FinanceLeavePage` | `leave.py` | same table | Invoice deductions | `test_finance_desk_cases.py` | Aug 20 | |
| HR-009 | Leave | Therapists cannot view credit balances (product decision). | FE hide | Therapist leave | | | | Jul 10 FE | Jul 10 | |
| HR-010 | People | There is **no** training-eligibility state machine. Training appears as payout one-off / ledger event key only. | absent | | `invoice_manual_lines`, ledger `parent_training` | | | | | INTENT UNKNOWN if HR expected one |
| HR-011 | People | Soft-delete therapists (filters + KPI). | profile `DELETED` / `deleted_at` | People | HR/admin | `therapist_profiles` | | Aug 28 | Aug 28 | |
| HR-012 | People | `hr.update_therapist` is permission `therapist.read`, not `user.manage`. | `hr.py` | | | | | **gap** | | Permission risk |

---

## FIN — money in and out

| ID | Domain | Rule in plain English | SOT | FE | BE | DB | Other | Tests | Recent? | Conflict? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIN-001 | Billing | Therapist payout invoices (`invoices`) and family invoices (`client_invoices`) are **different money**. | two tables | Different screens | two service families | `invoices` vs `client_invoices` | Control Tower | many | from day 1 | Naming |
| FIN-002 | Billing | Billing API is hidden unless `ENABLE_BILLING`. Ledger rows are not written unless `BILLING_LEDGER_WRITES`. Defaults **false**. | `feature_flags` / `config` | `useBillingRuntimeConfig` | router Depends | — | | release-gate tests | Aug 2 | Env vs UI flags |
| FIN-003 | Money in | Intended client event SSOT is `billing_ledger`. Live family document is `client_invoices` after generate. | doctrine + ledger model | Composer | `billing_ledger_service`, `client_invoice_draft_service` | ledger, invoices | Zoho no-op | `test_ledger_billing.py` | Aug | Writes often off |
| FIN-004 | Money in | Admin can also create a client invoice from **case defaults without ledger rows**. | `admin_create_invoice` / `create_draft_from_case_defaults` | Composer | `client_billing_service` | `client_invoices` | | loop tests | Aug 4 | **Yes** vs FIN-003 |
| FIN-005 | Package | Approving a prepaid log **increments** `care_packages.used_sessions`. | `consume_package_session` | remaining from API | `daily_logs.approve_log` | `care_packages` | | control-tower consume test | | vs FIN-006 |
| FIN-006 | Package | Package **cycle** remaining is a second table. `record_consumption` has **no production caller**. Consume does not update cycles. | `client_package_cycle_service` unused | renewal preview | cycles | `client_package_cycles` | Readiness sheet prefers cycle if present | **gap** | Aug 4 | **Yes** |
| FIN-007 | Package | Remaining shown to parent/admin = `max(0, total − used)` on `care_packages`. Frontend does not recalculate. | `list_packages` | `ParentBillingPage` | `client_billing_service` | care_packages | | | | Display OK if cycles unused |
| FIN-008 | Money out | Therapist month claim is built by `invoice_billing_service` from logs + case/as-of pay, then **stored snapshots** on submit. | submitted invoice | `InvoicesPage` | `submit_invoice_from_preview` | invoice lines + `billing_snapshot` | Settlement | invoice + as-of tests | Aug 27–29 | Live preview ≠ stored |
| FIN-009 | Money out | Therapist pay is a **rupee lump** (`therapist_fixed_pay_inr`). Incoming PERCENTAGE is coerced to FIXED_LUMP. | `billing_validation` + Alembic coerce | `CaseBillingForm` writes both lump fields | `resolve_therapist_pay` | cases | | `test_billing_pay_share.py` | Aug 28 | Enum leftover |
| FIN-010 | Money out | Shadow/B2B **calendar-day** pay: share/30 × (days − unpaid leave), not per completed session. | `uses_calendar_day_pay` | invoiceUtils keeps server share | `invoice_billing_service` | cases.day_type, product | | invoice attendance tests | Aug | INTENTIONAL vs homecare |
| FIN-011 | Money out | After submit, breakdown should come from **stored** lines, not live recompute. | invoice snapshots | therapist mobile breakdown | invoice billing | lines | | Aug 29 commits | Aug 29 | |
| FIN-012 | Rates | Rate changes need `applicable_from`. Invoice/payout/client draft use **as-of** the session/month date. Outgoing assignment snapshot can lock pay. | `billing_rate_history_service` | billing forms | as-of resolvers | `case_billing_rate_changes` | | `test_billing_asof_invoice_paths.py` | Aug 29 | |
| FIN-013 | Payout | Export/release of payout batches is flagged off. Provider default MOCK. | `payout_export_enabled` | Payouts UI | `payout_batch_service` | batches | | settlement tests | Aug 5 | |
| FIN-014 | Session/Finance | **Intended** central rule: `resolve_session_financial_effect(outcome, case, rule)`. **Nobody calls it.** COMPLETED is unhandled (would be non-billable). | dead function | — | `billing_ledger_service` | — | docs | **none** | Jun 24 written | **Yes** FIN-015 |
| FIN-015 | Session/Finance | **Live** package/absence effects use `package_unit_effect_for_status` (step 6) and `upsert_from_session_event`. Therapist leave is **never payable** in step 6; unused resolver allowed shadow paid leave. | step 6 + upsert | — | `billing_step6_service` | ledger | | `test_billing_step6.py` | Aug 2 | **Yes** FIN-014 |
| FIN-016 | Collection | Payment claims move the invoice balance only when finance **confirms**. | `confirm_payment_claim` | Admin payments | `client_billing_service` | `client_payments` | | parent/client billing tests | Aug 4 | |
| FIN-017 | Dispute | Parent line dispute **holds** that line; invoice is not globally DISPUTED. Legacy free-field INR tweak is off. | `_compute_invoice_balances` | Parent billing | client billing | `billing_disputes` | tickets | dispute tests | | |
| FIN-018 | Override | Ledger override blocked if already INVOICED. | `override_billable` | Tower | ledger service | ledger override columns | | | | |
| FIN-019 | Close | Billing cutoff date = `status_effective_date` for Suspended, Replacement, Deactivated, Closed. | `get_case_billing_cutoff` | | billing helpers | `cases` | | | | vs CASE-020 |
| FIN-020 | Leave/pay | Unpaid approved leave deducts on **calendar-day (shadow) cases** in invoice attendance. Not the same formula as HR credits. | `compute_leave_deduction_inr` | Invoice preview | `invoice_attendance_service` | leaves + invoices | Control Tower exceptions | attendance tests | Aug 27 extract | vs HR-006 |
| FIN-021 | Dashboard | Control Tower is role-gated (Finance + Super Admin). Amounts must not be labelled reconciled until `finance_cutover_complete`. | flags + role | Finance dashboard | `finance_control_tower_service` | reads | | gate1 tests | Aug 2–28 | KPI definition churned Aug 4–5 |
| FIN-022 | Leftover | `parent_billing_statements` still seeded and listed. Not the parent portal SSOT. | leftover table | (docs stale) | `parent_service` | `parent_billing_statements` | seed | | May–Jun | **Yes** FIN-003 |
| FIN-023 | FE math | Therapist can exclude session lines locally; UI re-sums. Submit still hits the server. Calendar-day cases keep server share. | `applyLocalExcludes` | `invoiceUtils.js` | `apply_preview_edits` | not stored until submit | | `invoiceUtils.test.js` | | Preview risk |
| FIN-024 | Redaction | Therapists must not see client prices on invoice views. | redaction helpers | invoice UI | invoice APIs | — | | `test_invoice_client_price_redaction.py` | Aug 3 | |

---

## CLIN — reports, visibility, clinical

| ID | Domain | Rule | SOT | FE | BE | DB | Tests | Recent? | Conflict? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CLIN-001 | Reports | Legacy monthly: Draft → Under review → Approved/Rejected → Published. | `ReportStatus` | Monthly reports | `report_service` | `monthly_reports` | publish tests | May | Dual engine |
| CLIN-002 | Reports | Clinical engine (lowercase statuses) is a **second** stack; routes 404 if flag off. | `ENABLE_CLINICAL_REPORTS_ENGINE` | `VITE_REPORTS_REVAMP` | `clinical_reports.py` | `clinical_reports` | report engine tests (flag on) | Aug 19 | Dual |
| CLIN-003 | Parent | Parents see logs only if submitted, approved, and visibility approved/shared. Session notes/observations stripped. | parent serializers | Parent logs | `parent_service` | daily_logs + visibility | parent visibility tests | Jun | |
| CLIN-004 | Parent | Parents see monthly reports when Published + parent-visible visibility. | same | Parent reports | reports + parent | | | | Dual with CLIN-002 |
| CLIN-005 | Evidence | Structured IEP taps on logs do nothing unless `enable_structured_evidence`. | config | log UI may show | evidence services | `session_evidence` | | Aug 18 off | |
| CLIN-006 | Attendance | Model enum is Present/Absent/Late/Partial. Column is a **free string**; FE also sends CLIENT_ABSENT / THERAPIST_LEAVE. | `_normalize_attendance` | log forms | daily_logs | `attendance_status` | | | Drift |

---

## AUTH — access

| ID | Domain | Rule | SOT | FE | BE | Tests | Conflict? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AUTH-001 | Auth | Wrong portal session is cleared and sent to the matching login. | `portal_login` | `AppRoutes` | `portal_login_service` | auth tests | |
| AUTH-002 | Auth | Therapist sees assigned cases only (`case.read.assigned` + active assignment). | `case_scope_check` | nav | permissions | RBAC tests | vs CASE-014 B2B |
| AUTH-003 | Auth | Finance has case.read.all and invoice/payout; no `case.assign` / `leave.manage`. | `ROLE_PERMISSIONS` | nav | deps | phase0 | |
| AUTH-004 | Auth | Hiding a button is not security. Mutations use `require_permission` / `module_write`. | API deps | `AuthContext.can` | FastAPI | phase0, module_write | Weak HR-012 |
| AUTH-005 | Auth | Retired roles SUPERVISOR and VIEWER must not be assigned to new staff. | `validate_assignable_staff_roles` | people | rbac_access | role migration | Legacy users may remain |

---

## AUTO — automations

| ID | Domain | Rule | Trigger | BE | Retry / dup | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| AUTO-001 | Email | Invite/reset retries every 10 min UTC. | Railway cron | `run_email_jobs.py` | `email_next_retry_at` | invite tests |
| AUTO-002 | Meetings | Reminders every 10 min + on create if within an hour. | cron + request | `cm_meeting_service` | | `test_phase5_meeting_reminders.py` |
| AUTO-003 | Sessions | 22:00 IST close all IN_PROGRESS with a start time. | cron 16:30 UTC | `session_day_end_service` | skip_locked | day-end tests |
| AUTO-004 | Incidents | SLA ticks when someone **lists** incidents (no cron). | GET list | `incident_sla_service` | | weak |
| AUTO-005 | Parent | Auto-suspend on last case close (sync). | status change | `client_status_service` | none | parent auto-suspend |

---

## How to use this registry

1. If two IDs say **Conflict? Yes**, do not “fix” in code until `10_FOUNDER_DECISIONS_REQUIRED.md` is answered.  
2. Prefer the **SOT** column over comments in older docs.  
3. New features should add a row here rather than a third implementation of an existing ID.
