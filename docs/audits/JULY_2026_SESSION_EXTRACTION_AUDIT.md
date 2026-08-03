# July 2026 Therapist Session Extraction — Audit Summary

**Generated:** 2026-08-02  
**Script:** `backend/scripts/export_therapist_monthly_sessions.py`  
**Report:** `exports/insightecase_july_2026_therapist_sessions.xlsx`  
**Database used for this run:** **Railway production Postgres** (`truthful-blessing` / `api.insighte.org`) via TCP proxy — read-only export.

> Previous local demo run (14 rows, SQLite) superseded by this production export (**6,321 session rows**, **237 therapists**).

---

## Step 1 — Data Model: Tables and Fields Used

### Primary session record (`sessions`)

| Export column | Source field | Notes |
|---------------|--------------|-------|
| Session ID | `sessions.id` | Primary key |
| Scheduled session date | `sessions.scheduled_date` | Calendar date, not used alone for month filter |
| Scheduled start/end | `sessions.start_time`, `sessions.end_time` | Combined with scheduled_date in IST |
| Actual check-in | `sessions.actual_start_at` | GPS: `checkin_lat`, `checkin_lng` |
| Actual checkout | `sessions.actual_end_at` | GPS: `checkout_lat`, `checkout_lng` |
| Edited times | `sessions.edited_start_at`, `edited_end_at` | Used when daily log is APPROVED (`effective_session_datetimes`) |
| Session status | `sessions.status` | SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED, CLIENT_ABSENT, THERAPIST_LEAVE, etc. |
| Auto-closed | `sessions.auto_ended`, `auto_end_reason` | Day-end cron auto-close |
| Manual/backdated | `sessions.actual_times_edited`, `is_additional_visit` | Also `daily_logs.late_addition` |
| Cancellation reason | `sessions.cancellation_reason` | |
| Data quality flag | `sessions.data_quality_flag` | test/duplicate detection |
| Therapist (actual) | `sessions.therapist_user_id` | Attribution for payout |

**No separate attendance table.** Check-in/out timestamps live on `sessions`. Attendance classification is on `daily_logs.attendance_status` (PRESENT, ABSENT, LATE, PARTIAL).

### Attendance / daily log (`daily_logs`)

| Export column | Source field | Notes |
|---------------|--------------|-------|
| Attendance record ID | `daily_logs.id` | 1:1 with session (`session_id` unique) |
| Daily log ID | `daily_logs.id` | |
| Attendance status | `daily_logs.attendance_status` | String, not timestamp |
| Daily log status | `daily_logs.approval_status` | PENDING / APPROVED / REJECTED |
| Daily log approved | derived | `approval_status == APPROVED` |
| Daily log created | `daily_logs.created_at` | Fallback timestamp #4 |
| Daily log submitted | `daily_logs.submitted_at` | Fallback timestamp #4 |

### Therapist identity

| Export column | Source |
|---------------|--------|
| Therapist user ID | `sessions.therapist_user_id` |
| Employee/staff ID | `users.external_employee_id` |
| Therapist name | `users.full_name` |
| Active status | `users.employment_status` |

**PAN / bank account:** Not stored in application schema. Export flags `missing_bank_pan_rate_info` when payout rates are absent on the case.

### Case / client / assignment

| Export column | Source |
|---------------|--------|
| Case ID | `sessions.case_id` |
| Client ID | `cases.child_id` → `children.id` |
| Client name | `children.first_name` + `last_name` |
| Service category | `cases.service_type` |
| Service product | `cases.product_module` |
| Assignment ID | `case_assignments.id` (active on session date) |
| Original assigned therapist | `case_assignments.therapist_user_id` |
| Replacement flag | session therapist ≠ assigned therapist |
| Case manager | `cases.case_manager_user_id` → `users.full_name` |
| Billing type | `cases.billing_type` (PER_SESSION / PACKAGE) |
| Payout type | `cases.compensation_mode` (PERCENTAGE / FIXED_LUMP) |
| Client billing rate | `cases.client_rate_per_session_inr` |
| Therapist payout rate | `cases.pay_share_amount_inr` or `therapist_fixed_pay_inr` |

### Billing ledger (`billing_ledger`)

| Export column | Source |
|---------------|--------|
| Billing ledger ID | `billing_ledger.id` |
| Billing ledger status | `billing_ledger.billable_status` |
| Existing ledger amount | `billing_ledger.total_inr` |

### Therapist payout (`invoice_session_lines` → `invoice_case_lines` → `invoices`)

| Export column | Source |
|---------------|--------|
| Therapist invoice line ID | `invoice_session_lines.id` |
| Existing therapist invoice line amount | `invoice_session_lines.amount_inr` |
| Therapist invoice status | `invoices.status` |

### Client billing (`client_invoice_lines`)

| Export column | Source |
|---------------|--------|
| Client invoice line ID | `client_invoice_lines.id` |
| Existing client invoice line amount | `client_invoice_lines.amount_inr` |

### Absence requests (`session_absence_requests`)

| Export column | Source |
|---------------|--------|
| Client/therapist absent flags | `absence_type`, `status`, `reason` |
| Absence reason | `session_absence_requests.reason` |

### Time audit (`session_time_audit_events`)

Not expanded to separate rows; edits reflected via `sessions.edited_*` and `actual_times_edited`.

---

## Step 2 — Definition of “Session Occurred”

All classifications are deterministic from session timestamps, status, and linked records.

### `CONFIRMED_OCCURRED`

- `actual_start_at` (or approved edited start) exists, **and**
- `actual_end_at` (or approved edited end) exists **or** `auto_ended = true`, **and**
- Status is not cancelled/rescheduled before start

### `LIKELY_OCCURRED_REVIEW`

- Check-in without checkout (or reverse)
- Status COMPLETED but timestamps incomplete
- Daily log exists but attendance unverified
- Manual/backdated session (`actual_times_edited`, `late_addition`, `is_additional_visit`)
- Auto-closed session
- Duration anomaly (>240 min or ≤0)
- Client absent (retained for finance contract review)
- Scheduled-start-only fallback used for reporting date

### `DID_NOT_OCCUR`

- Cancelled / rescheduled / no-show before start
- Therapist absent / therapist leave
- SCHEDULED with no attendance evidence
- Outside July IST reporting window

Client-absent sessions are **not** auto-excluded; they appear in `LIKELY_OCCURRED_REVIEW` with billing-policy fields retained.

---

## Step 3 — Timestamp Rules

**Filter window (IST, exclusive end):**

```text
reporting_start >= 2026-07-01T00:00:00+05:30
AND reporting_start < 2026-08-01T00:00:00+05:30
```

**Reporting start fallback chain:**

1. `sessions.actual_start_at` (or approved `edited_start_at`)
2. Attendance — no separate timestamp; defers to #1
3. `sessions.actual_end_at` when status COMPLETED
4. `daily_logs.submitted_at` → `daily_logs.created_at`
5. Scheduled start — **review dataset only** (`LIKELY_OCCURRED_REVIEW`)

All exported timestamps are converted to Asia/Kolkata ISO format.

---

## Step 8 — Four Definition Totals (production DB, July 2026 IST)

| Definition | Count |
|------------|------:|
| 1. Sessions with completed/valid timestamps (`CONFIRMED_OCCURRED`) | **4,919** |
| 2. Sessions marked `COMPLETED` in session table | **4,919** |
| 3. Sessions with approved daily logs | **4,770** |
| 4. Sessions in therapist payout invoice lines | **0** |

| Delta | Value | Interpretation |
|-------|------:|----------------|
| Timestamps − COMPLETED | **0** | Timestamp and status agree on all confirmed sessions |
| COMPLETED − approved logs | **+149** | 149 completed sessions lack approved daily logs |
| Approved logs − invoice lines | **+4,770** | No July sessions appear in therapist payout invoice lines |

### Classification breakdown (in reporting window)

| Classification | Count |
|----------------|------:|
| `CONFIRMED_OCCURRED` | 4,919 |
| `LIKELY_OCCURRED_REVIEW` | 947 |
| `DID_NOT_OCCUR` | 455 |
| **Total in window** | **6,321** |

### Top therapists by confirmed sessions (production)

| Therapist | ID | Confirmed | Review | Approved logs | In invoice | Exceptions |
|-----------|---:|----------:|-------:|--------------:|-----------:|-----------:|
| Anusha Alva B | 339 | 81 | 0 | 81 | 0 | 0 |
| Siri S Kamath | 126 | 79 | 5 | 78 | 0 | 9 |
| Mariyam Shadin | 131 | 62 | 2 | 62 | 0 | 2 |
| Pratiti Das | 127 | 61 | 11 | 60 | 0 | 23 |
| Oindrila Bhattacharya | 141 | 57 | 1 | 56 | 0 | 1 |
| Krupa Mohan | 129 | 54 | 8 | 52 | 0 | 13 |
| Khushi Bid | 199 | 52 | 2 | 52 | 0 | 6 |
| Aifha P | 348 | 52 | 0 | 51 | 0 | 8 |

**237 therapists** · **385 client–therapist assignment pairs**

**Pipeline loss visible on production:**

```text
4,919 confirmed by timestamps (= COMPLETED status)
  ↓ −149 missing log approval
4,770 approved daily logs
  ↓ −4,770 no therapist invoice lines recorded
0 therapist invoice lines
```

---

## Main Discrepancy Categories (production)

| Category | Count | Sheet |
|----------|------:|-------|
| Missing daily log or unapproved log | 1,096 | `04_Missing_Logs` |
| Missing billing ledger row | 1,084 | `05_Missing_From_Billing` |
| Missing therapist invoice line | 5,866 | `06_Missing_From_Payout` |
| Timestamp exceptions | 4,820 | `07_Timestamp_Exceptions` |
| Duplicate/overlap candidates | 914 | `08_Duplicates_Overlaps` |
| Rate/assignment issues | 58 | `09_Rate_Assignment_Issues` |

---

## Schema / Data Quality Observations

1. **No separate attendance record table** — attendance is `daily_logs.attendance_status`; check-in/out are on `sessions`.
2. **No `daily_logs.approved_at`** — approval is boolean status only; export uses `approval_status == APPROVED`.
3. **Employee ID** is `users.external_employee_id` (nullable; empty in demo).
4. **PAN/bank/TDS** not in schema — cannot export; masked by omission.
5. **Therapist payout math** reuses `invoice_billing_service.compute_session_line_amount()` for recalculation.
6. **Production billing module** is feature-flagged off; ledger/invoice rows may be sparse even when sessions occurred.
7. **Production schema drift:** ORM model includes `daily_logs.parent_voice_attachment_id` which is not yet on production Postgres. Export script uses raw SQL for daily_logs to avoid this.

---

## Sample Rows for Manual Verification (demo DB — all 14 rows)

| session_id | therapist | client | scheduled | reporting_date_ist | status | classification | check_in (IST) | check_out (IST) | log_approved | in_ledger | in_invoice |
|-----------:|-----------|--------|-----------|-------------------|--------|----------------|----------------|---------------|--------------|-----------|------------|
| 8 | Therapist Neha | Aarav M. | 2026-07-08 | 2026-07-08 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 9 | Therapist Neha | Aarav M. | 2026-07-10 | 2026-07-12 | SCHEDULED | DID_NOT_OCCUR | — | — | no | no | no |
| 10 | Therapist Neha | Ira K. | 2026-07-09 | 2026-07-09 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 11 | Therapist Neha | Aarav M. | 2026-07-07 | 2026-07-09 | COMPLETED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 12 | Therapist Neha | Aarav M. | 2026-07-06 | 2026-07-08 | COMPLETED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 13 | Therapist Neha | Aarav M. | 2026-07-09 | 2026-07-09 | COMPLETED | **CONFIRMED_OCCURRED** | 12:13 IST | 12:15 IST | no | no | no |
| 14 | Therapist Neha | Aarav M. | 2026-07-11 | 2026-07-11 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 15 | Therapist Neha | Ira K. | 2026-07-10 | 2026-07-10 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 16 | Therapist Neha | Aarav M. | 2026-07-13 | 2026-07-13 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 17 | Therapist Neha | Ira K. | 2026-07-12 | 2026-07-12 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |
| 18 | Therapist Neha | Ira K. | 2026-07-11 | 2026-07-11 | COMPLETED | **CONFIRMED_OCCURRED** | 23:53 IST | 23:56 IST | no | no | no |
| 19 | Therapist Neha | Aarav M. | 2026-07-12 | 2026-07-12 | COMPLETED | **CONFIRMED_OCCURRED** | 02:41 IST | 04:02 IST | no | no | no |
| 20 | Therapist Neha | Aarav M. | 2026-07-14 | 2026-07-14 | COMPLETED | **CONFIRMED_OCCURRED** | 17:57 IST | 17:58 IST | no | no | no |
| 21 | Therapist Neha | Ira K. | 2026-07-13 | 2026-07-13 | SCHEDULED | LIKELY_OCCURRED_REVIEW | — | — | no | no | no |

Full detail in XLSX sheet `01_Raw_Sessions`.

---

## Exact Command Used (production)

```bash
cd backend
source .venv/bin/activate

# Credentials fetched via Railway CLI (Postgres TCP proxy) — not stored in repo.
# Requires: npx @railway/cli login + link to production environment.

python3 << 'PY'
import json, os, subprocess, sys, urllib.parse
from pathlib import Path

proc = subprocess.run(
    ["npx", "@railway/cli", "variables", "--service", "Postgres", "--json"],
    capture_output=True, text=True, check=True,
)
v = json.loads(proc.stdout)
url = "postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}".format(
    user=v["POSTGRES_USER"],
    pw=urllib.parse.quote_plus(v["POSTGRES_PASSWORD"]),
    host=v["RAILWAY_TCP_PROXY_DOMAIN"],
    port=v["RAILWAY_TCP_PROXY_PORT"],
    db=v["POSTGRES_DB"],
)
env = os.environ.copy()
env["DATABASE_URL"] = url
env["APP_ENV"] = "production"
subprocess.run([
    sys.executable, "-m", "scripts.export_therapist_monthly_sessions",
    "--from", "2026-07-01", "--to", "2026-08-01",
    "--timezone", "Asia/Kolkata",
    "--output", "../exports/insightecase_july_2026_therapist_sessions.xlsx",
    "-v",
], env=env, check=True)
PY
```

---

## Validation Checks (automated)

- [x] Every raw row has a session ID
- [x] No duplicate session IDs in raw sheet
- [x] Summary totals reconcile to raw-session confirmed count
- [x] Timestamps converted to Asia/Kolkata consistently
- [x] Test/deleted records flagged via `data_quality_flag`
- [x] Replacement therapists flagged via assignment comparison
- [x] Scheduled-only sessions not counted as CONFIRMED_OCCURRED
- [x] Orphan approved logs listed separately

---

## Re-run Against Production

Already completed 2026-08-02. To refresh:

1. Ensure Railway CLI is logged in (`npx @railway/cli login`) and linked to production.
2. Run the command above (uses TCP proxy — internal `postgres.railway.internal` URL will not work locally).
3. Compare sheet `03_Client_Therapist_Summary` against the July monthly billing workbook.

**This export performs zero writes** — no ledger generation, no invoice mutation, no status changes.
