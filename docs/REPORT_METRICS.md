# Reporting metric contracts

Leadership and operational reports on InsighteCase. All business dates use **Asia/Kolkata (IST)**. Timestamp filters use half-open UTC intervals: start inclusive, end exclusive. Date-only columns are compared as dates and are not shifted.

This document is the definition source for cards, detail reports, and exports. Production totals are **not** verified in this environment (no production read). Local fixtures and tests only.

Synthetic identifiers in examples are fictional.

---

## How to read a contract

| Field | Meaning |
|---|---|
| Date basis | Current snapshot, activity during a period, billing-month cohort, or as-of a date |
| Grain | One row / one counted entity |
| Zero vs unavailable | Missing source is labelled unavailable. Zero means the query ran and found none |

---

## Finance Reports (existing product)

### Therapist payout preview

| | |
|---|---|
| **Purpose** | Projected therapist pay for a billing month before close; frozen snapshot after close |
| **Route** | `/admin/finance-reports` · `GET /api/v1/admin/finance-reports/therapist-payout-preview` |
| **Permission** | `invoice.approve` + billing module |
| **Grain** | Case × assignment window (segment) in the billing month |
| **Date basis** | Billing month (`YYYY-MM`, also `Oct 2026` / `October 2026`). Not “paid during the period” — therapist `invoices` have no payout paid-at timestamp |
| **Included** | Live `payout_preview_rows` unless the month is closed, then snapshot rows |
| **Excluded** | Payout formula changes; Control Tower; client collections |
| **Filters** | Billing month; period start/end (IST); product module / case type; report status; case/therapist when sent |
| **Limitation** | Live path is case/segment work. Preview must be explicitly generated. Export may hit `MAX_EXPORT_ROWS` (5000); the UI must not treat a 50-row preview as the full total |

Do not rename this report. Collections, receivables, and contribution are **different** views.

### Collections

| | |
|---|---|
| **Purpose** | Confirmed family payments vs pending claims |
| **Route** | `GET /api/v1/admin/finance-reports/collections` |
| **Permission** | `invoice.approve` |
| **Grain** | One `client_payments` row |
| **Date basis** | Default `cash_period`: `paid_at` in the IST month. Optional `invoice_cohort`: invoice `billing_month` matches. Current outstanding is a different metric |
| **Included in totals** | `payment_status = CONFIRMED` only |
| **Shown separately** | `PENDING_REVIEW` claims; `REJECTED` not in cash totals |
| **Source** | `client_payments.payment_status` (not a `status` field) |

### Outstanding / receivables (API)

| | |
|---|---|
| **Purpose** | Current unpaid balances |
| **Date basis** | **Current snapshot.** If `billing_month` is passed, restrict to invoices of that billing month but amounts remain **today’s** balances, not historical outstanding |
| **Overdue** | Days overdue only when `client_invoices.due_date` is set. Otherwise show invoice age, not “days overdue” |
| **Included statuses** | Unpaid / partial / overdue-class invoices (`GENERATED`, `ISSUED`, `SENT`, `PARTIALLY_PAID`, `OVERDUE`). Not `PAID` / `VOID` / `CANCELLED` |

### Invoice-month billing

Sum of `client_invoices.total_inr` where `billing_month` = selected month. Label **invoiced amount**, never recognised revenue.

### Therapist statements awaiting approval

Count `invoices` (therapist payout) with `status = IN_REVIEW`. Statement month uses stored `Invoice.month` aliases (`2026-10`, `Oct 2026`, `October 2026`).

### Approved awaiting payment

`invoices.status = APPROVED` (and `EXPORTING` if treated as approved-not-paid). Do not label as “paid during the period”.

---

## Support ticket reports (two different products)

### Ticket report (staff hub)

| | |
|---|---|
| **Purpose** | Leadership/staff view of tickets they can already handle |
| **Route** | `/admin/support?tab=ticket-report` · `GET /api/v1/admin/support/ticket-report` |
| **Permission** | `can_view_support_tickets` (same as the ticket desk) |
| **Date basis** | **Opened during IST range** (`created_at` in half-open UTC bounds). Default: current IST month through today |
| **Grain** | Ticket. Queue lists `OPEN` + `IN_PROGRESS` |
| **Counts** | Status, category, module, raiser role, first-reply hours, aging, repeating questions |
| **Queue cap** | Display/export queue may truncate at 500; `queue_total` / `queue_truncated` stay honest. Status totals are complete |
| **Privacy** | No message text, attachments, child names, parent contacts, bank details. POSH/CPP: counts only, omitted from the live queue |
| **Does not** | Reply, close, or change tickets |

### Parent support tickets (HR catalog export)

| | |
|---|---|
| **Purpose** | Parent-raised grievances for HR/CRM export |
| **Route** | `/admin/hr-reports` key `support-tickets-parent` |
| **Permission** | `hr_report.export` or `user.manage` |
| **Date basis** | Calendar month window |
| **Grain** | Parent-raised tickets only |
| **Not the same as** | The Support hub ticket report |

---

## Super-admin `/admin` overview

Each card is labelled **Current**, **During selected period**, or **As of [date]**. Clicking opens the matching filtered list. Payout preview and full margin reconcile stay off this load.

### Business — current case mix

| | |
|---|---|
| **Date basis** | Current snapshot |
| **Grain** | Case |
| **Included** | Every `CaseStatus`: `PENDING_ALLOTMENT`, `ACTIVE`, `SUSPENDED`, `PENDING_REPLACEMENT`, `DEACTIVATED`, `CLOSED` |
| **Scope** | `apply_case_scope` |
| **Detail** | `/admin/cases?status=` |

### Business — movement during period

| Measure | Source | Notes |
|---|---|---|
| New cases created | `cases.created_at` in IST range | Not first activation |
| First activation | First audit row to `ACTIVE` whose `effective_date` is in range | Unavailable/partial if audit coverage is incomplete |
| Reactivation / suspension / closure / deactivation | `case_client_status_audit` `new_status` + `effective_date` | Separate counts. Do not invent opening/closing caseload |

### Assignment gaps (current)

| Measure | Definition | Distinct from |
|---|---|---|
| Awaiting first assignment | `PENDING_ALLOTMENT` or no assignment yet | Replacement |
| Awaiting replacement | `PENDING_REPLACEMENT` | The current therapist may still be delivering |
| Active without active assignment | `ACTIVE` and no `case_assignments.status = ACTIVE` | Replacement pipeline |

Reassignment events come from ended/transferred `case_assignments`. Not every `ENDED` row is a replacement.

### Finance cards (if `invoice.approve`)

| Card | Date basis | Formula |
|---|---|---|
| Invoiced amount | Billing month | Sum `client_invoices.total_inr` for that month |
| Confirmed cash received | During period | Sum confirmed `client_payments` with `paid_at` in range |
| Current outstanding | Current | Sum unpaid balances on open invoices |
| Current overdue | Current | Outstanding where `due_date` is past IST today; if due date missing, do not call it overdue |
| Therapist statements in review | Current | `IN_REVIEW` count |
| Approved awaiting payment | Current | `APPROVED` amount/count — not paid-during-period |

Never “recognised revenue” or “net profit”. Contribution/margin is on-demand, not on first paint.

### Tickets on the overview

| Card | Date basis | Definition |
|---|---|---|
| Open | Current | `OPEN` |
| In progress | Current | `IN_PROGRESS` |
| Needs action | Current | `OPEN` + `IN_PROGRESS` (not a third stored status) |
| Opened during period | During period | `created_at` in range (same basis as ticket report) |

Drill-down: `/admin/support?tab=ticket-report` with matching filters.

### Staff workplace attendance

| | |
|---|---|
| **Source** | In-app `staff_attendance` (clock-in). This **is** workplace attendance for leadership |
| **Date basis** | Work date (date-only, IST calendar) |
| **Not** | Login timestamps, therapy sessions, or an HRIS feed |
| **Gap** | No clock-in that day = attendance gap in this source, not “source disconnected” |
| **Coverage** | Only staff who use in-app clock-in |
| **Detail** | `/admin/attendance` |

### Therapist overdue monthly card

`MonthlyReport` has no due date. The pipeline **Overdue** figure is **unavailable** (not zero). **Not started** (no report for the IST month) is a separate supported count. Observation checklist overdue may use `due_at` where present.

---

## Documentation and logs

| Metric | Completed statuses | Notes |
|---|---|---|
| Monthly/observation completed | `APPROVED` **or** `PUBLISHED` | Approval may publish; APPROVED-only undercounts |
| Session log missing | `COMPLETED` session, no `daily_logs`, scheduled ≤ today−2 IST | Therapist log compliance |
| Auto-closed session | `sessions.auto_ended` | Not proof of attended delivery |

Parent portal HR export: **Last Login** / **Days Since Last Login**. Login is not application activity (`app_usage_chunks`).

---

## Data exceptions (as of generation time)

Live Layer-1 checks. No stored detection history and no auto-repair.

| Rule | Severity | Suggested owner |
|---|---|---|
| Active case, no active assignment | Confirmed | Case manager / allotment |
| Inactive user with active assignment | Confirmed | HR |
| Completed session, no log (2+ days) | Confirmed | Therapist / CM |
| Invoice month not parseable after shared parser | Suspected | Finance |
| Multiple active assignments or multiple invoices for a case-month | Not automatically an error | Inspect handover / billing rules |

---

## Permissions (summary)

| Surface | Gate | Row scope |
|---|---|---|
| `/admin` overview | Admin portal roles | `apply_case_scope`; finance cards need `invoice.approve` |
| Finance Reports payout preview | `invoice.approve` | Billing module |
| HR catalog | `hr_report.export` or `user.manage` | Catalog + case scope |
| Ticket report | Ticket desk access | `staff_ticket_visibility_clause` |
| Clinical approve (engine) | `monthly_report.approve` / share roles — **not** case visibility alone | Must not enable the engine as a side effect |

Department tags are not ACL.

---

## Remaining gaps

- Historical caseload reconstruction is unsupported without complete `case_client_status_audit` coverage (labelled partial).
- Therapist payout **paid during period** is unsupported (no paid-at on `invoices`).
- Ticket SLA is unsupported (no ticket SLA columns).
- Monthly report due dates are unsupported.
- Production reconciliation is unverified until a production read exists.
