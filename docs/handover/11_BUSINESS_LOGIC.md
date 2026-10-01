# 11 — Business Logic

Rules below are **facts from code/docs** unless labeled **(inference)** or **(assumption)**.

---

## Case as source of truth

- Every operational artifact references `cases.id` (directly or via assignment/session).  
- **Do not** use deprecated single `therapist_id` on case alone for authorization — use `case_assignments` / `case_services` with history (`AGENTS.md`).  
- `case_code` is human-visible Case ID; searchable globally.

---

## Case creation and billing defaults

**(From AGENTS.md / admin flows)** When a case is created, admins set **client billing amount** and **therapist pay share**; HR/finance may revise later. Billing type: `PER_SESSION` vs `PACKAGE` with compensation modes (`CompensationMode` enum in models).

Low-margin changes: if proposed billing yields Insighte profit below `BILLING_MINIMUM_PROFIT_INR` (default ₹5000), **`billing_approval_requests`** route to `BILLING_APPROVAL_APPROVER_EMAIL` before apply.

---

## Assignments and acceptance

- Assignments created via admin/API; history preserved when ended/replaced.  
- `ACCEPTANCE_GATING_ENABLED=false` (default): parent **accept** on assignment is informational — timestamps recorded but do not block work **(pilot default per config comment)**.  
- When gating enabled **(inference)**, acceptance would block downstream flows — verify in `assignment_acceptance.py` before enabling in prod.

---

## Sessions and logs

| Rule | Source |
|------|--------|
| Session start/end drives “visit completed” state | `sessions.py`, session services |
| Daily log linked to session for normal path | `daily_log` model FK |
| Therapist may void completed session without log within `SESSION_VOID_WINDOW_HOURS` (default 168h) | `config.py` |
| Late additions flagged on log (`late_addition`) | model field |
| Admin approve sets `approval_status`, visibility for parent | admin daily log approve endpoints |
| Parent API excludes internal fields (`session_notes`, raw `observations`) | `parent.py` session-logs |

**Visibility enums** (parent sees only approved + `APPROVED_FOR_PARENT` / `SHARED_WITH_PARENT`): documented in [docs/ARCHITECTURE.md](../ARCHITECTURE.md).

---

## Reports

| Report type | Therapist | Admin | Parent |
|-------------|-----------|-------|--------|
| Monthly | Draft → submit | Approve/reject → publish | Published + visibility |
| Observation | Submit | Review | When shared |
| Clinical engine (observation/IEP) | Builder UI | Review events in `clinical_report_*` tables | Parent paths when published |

Monthly report parent approval/feedback endpoints exist under `/parent/reports/monthly/{id}/...`.

---

## IEP and clinical profile

- Structured clinical data stored in separated JSON columns / tables: strengths, support needs, environment, etc. (clinical models).  
- IEP plan suggestions may be enabled with `IEP_REVIEW_SUGGESTIONS_ENABLED`.  
- Parent acknowledge on IEP attachment sets visibility to shared state (`SHARED_WITH_PARENT`).

---

## Invoicing (therapist)

- Invoices derive from validated session/log evidence **(inference from product design; trace in `invoice_billing_service` / related)**.  
- Finance can mark paid/queried; disputes via `therapist_statement_disputes` — legacy free-field adjustment disabled unless `BILLING_DISPUTE_LEGACY_ADJUSTMENT=true`; prefer finance correction service.

---

## Client billing & ledger (flagged)

When `ENABLE_BILLING=true`:

- Routers mount; **`BILLING_LEDGER_WRITES=false`** by default prevents silent ledger mutation on deploy.  
- `FINANCE_CUTOVER_COMPLETE=false` → UI shows provisional banner; amounts not labeled fully reconciled.  
- Cutover sequence: [docs/FINANCE_CUTOVER_RUNBOOK.md](../FINANCE_CUTOVER_RUNBOOK.md).

Zoho Books: no fake success — empty `ZOHO_BOOKS_API_KEY` shows not configured.

---

## Payouts (money OUT)

- `PAYOUT_EXPORT_ENABLED` → batch export mock/live pipeline.  
- `PAYOUT_RELEASE_ENABLED` → mark transfers paid (**enable last** in runbook).  
- `PAYOUT_PROVIDER=MOCK` default; `RAZORPAY` stub until live wiring.  
- Default TDS: `FINANCE_DEFAULT_TDS_RATE_PERCENT` unless therapist profile override.

---

## Parent portal

- Only **approved/published** artifacts with correct visibility.  
- Billing via `parent_billing_statements` — not raw therapist invoices.  
- Session log disputes/comments via dedicated parent endpoints.  
- Booking: cancel/reschedule rules in `parent.py` appointment handlers.

---

## Support tickets

- Attachments: max **3** files, **5 MB** each (types: JPEG, PNG, WebP, PDF, plain text) — `config.py`.  
- Finance/HR assignee emails route L1 desks.  
- Parent can escalate, accept resolution, rate — staff workflows in ticket services.

---

## Incidents

- Created by permitted roles; restricted visibility for sensitive categories **(verify category enums in `incident` model and RBAC)**.  
- Escalation/close workflows in `incidents.py`.  
- Available across service lines per product direction (`AGENTS.md`).

---

## HR & leave

- Staff attendance: clock in/out, pause, forgot clock — `staff_attendance.py`.  
- Therapist leave credits UI hidden by default via `VITE_HIDE_THERAPIST_LEAVE_CREDITS_UI` — backend logic unchanged.  
- Leave migration backfill cutoff: `LEAVE_MIGRATION_END_DATE`.

---

## Notifications

- Created on key events (approvals, tickets, etc.) — see `notification_service.py`.  
- In-app list via `/api/v1/notifications`.

---

## Audit

- `log_audit()` on sensitive actions (login, many mutations).  
- Immutable `audit_events` table — **(inference)** append-only by convention.

---

## Exception queue / review triggers

Product doctrine (`.cursorrules`) defines `review_queue` trigger vectors (`is_edited_after_completion`, `incident_reported`, etc.). **(Verify)** which triggers are fully implemented in DB vs roadmap — grep `review_queue` in codebase during onboarding.

---

## Email

- If `SMTP_HOST` unset or ZeptoMail password empty → **noop** provider, rows in `email_logs` only.  
- Template dedupe and recipient daily caps in config (`email_*` settings).

---

## Module write enforcement

RBAC v1: UI hides destructive actions on **view** grants; API enforcement **partial** for some modules — see [docs/ROLE_MODEL_PHASES.md](../ROLE_MODEL_PHASES.md) and [docs/RBAC_SCOPE.md](../RBAC_SCOPE.md).

---

## Why rules exist (where known)

| Rule | Why |
|------|-----|
| Parent visibility gating | Trust + compliance — families see curated summaries, not draft therapist notes |
| Billing flags default off | Prevent accidental production money writes on merge |
| Redis required in prod | Shared refresh token revocation across workers |
| Portal-specific login | Reduce wrong-portal access and support confusion |
| Case manager region scope | Operational caseload partitioning |

---

## Hidden logic discovery tip

When debugging “why was X rejected?”:

1. Find API route in `app/api/v1/`  
2. Jump to called `app/services/*_service.py`  
3. Grep for `HTTPException`, `raise`, permission deps  
4. Check model status enums in `app/models/`  
