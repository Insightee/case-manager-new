# Core OS Stabilisation epic

**Baseline:** `main` @ `a8499f24` (2026-09-05), re-checked 2026-09-08.  
**Policy:** DEC-01 / DEC-02 / DEC-03 locked in [10_FOUNDER_DECISIONS_REQUIRED.md](./10_FOUNDER_DECISIONS_REQUIRED.md).  
**Order:** Phase 0 (this doc) → Phase 1 counts → PR1 session start → PR2 eligibility/exit → PR3 package SOT.

## Invariants (done when true)

1. If a case is paused, every path agrees whether service can start.
2. If a therapist is ineligible or exited, every path agrees whether they can hold/operate/login.
3. If a package has X sessions remaining, every production screen returns X.

## Owners

| PR | Owners |
| --- | --- |
| PR1 Session start | Case Ops + Finance |
| PR2 Eligibility / exit | HR + Case Ops |
| PR3 Package SOT | Finance + Case Ops |

## Regression suites (narrow; see plan)

- PR1/G3: session start, pending-log, absence, leave case×day uniqueness, meetings if bookings touched
- PR2/G4: phase0 CM lockdown, allotment scope, auth
- PR3/G5: leave/invoice attendance, package consume paths

## Do not touch in this epic

`resolve_session_financial_effect` wiring; Control Tower; Lead CRM; report cutovers; delete DEACTIVATED/PERCENTAGE/legacy reports; unify Homecare/Shadow; enable payout release; rewrite leave paid-first/Saturday/homecare leave invoice rules; grant CM `case.assign`.

## Phase 1 — integrity freeze

Recorded in section below when DevOps/local read-only checks run. Unexpected post-PR deltas → STOP.

### Flags (code defaults + note)

| Flag | Code default (`config.py`) | Prod note |
| --- | --- | --- |
| `ENABLE_BILLING` / `enable_billing` | false | Verify Railway |
| `BILLING_LEDGER_WRITES` | false | Verify Railway |
| `FINANCE_CUTOVER_COMPLETE` | false | Verify Railway |
| `PAYOUT_EXPORT_ENABLED` | false | Verify Railway |
| `PAYOUT_RELEASE_ENABLED` | false | Verify Railway |
| `ENABLE_CLINICAL_REPORTS_ENGINE` | false | Verify Railway |
| `ENABLE_STRUCTURED_EVIDENCE` | false | Verify Railway |

**Local freeze (2026-09-08):** defaults read from `backend/app/core/config.py` (pydantic not installed in shell; source inspection). Production Railway/Vercel values must be pasted by DevOps before merge to prod.

### Integrity counts

Capture with anonymised SQL against staging/prod (IDs/counts only). Local seed is not production truth.

| Metric | Query intent | Frozen count |
| --- | --- | --- |
| Inactive therapist + ACTIVE assignment | `users.is_active=false` join `case_assignments.status=ACTIVE` | _pending Railway/staging_ |
| SUSPENDED + sessions after effective date | case SUSPENDED + session.scheduled_date >= status_effective_date | _pending Railway/staging_ |
| PENDING_REPLACEMENT + outgoing sessions after cutoff | same pattern for outgoing therapist | _pending Railway/staging_ |
| care_package vs cycle remaining mismatch | used/total vs cycle.remaining_sessions | _pending Railway/staging_ |
| HR update via therapist.read | `hr.update_therapist` uses `therapist.read` | noted; not blocking PR2 |

Phase 1 code-default freeze completed 2026-09-08. Staging/prod row counts remain for DevOps before production cutover of each PR.

## Implementation notes

Implemented against baseline `a8499f24` (2026-09-08):

- **PR1:** `session_operational_gate_service` + start reorder; `SUSPENDED` in portal hide; therapists retain assigned access on SUSPENDED for finish/start gate; G3 tests.
- **PR2:** `therapist_eligibility_service`; assignment/allotment gates; exit ends ACTIVE assignments → `PENDING_REPLACEMENT`; login 403 + `/auth/request-status-restore` HR ticket; CM still no `case.assign`; G4 tests.
- **PR3:** `package_effect_service.apply_package_effect`; consume on log submit/resubmit/approve (idempotent); reverse on reject (invoice-locked blocked); `consume_package_session` wraps SOT; cycles `record_consumption` no-op; G5 + leave/invoice regressions green.
