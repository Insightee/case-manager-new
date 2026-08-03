# Finance Dashboard Revamp — work packages

status: PLANNING
initiative: [docs/initiatives/finance-dashboard.md](../initiatives/finance-dashboard.md)
open_questions: [docs/plans/finance-open-questions.md](./finance-open-questions.md)
baseline_sha:            # set by FIN-00. No loop may run while this is empty.
discovery_run: yes       # A–J staleness audit completed 03-08-2026 against HEAD 16fdc06
frozen_selectors: []     # set by FIN-01. FIN-12 verifies against this list, not the full suite.

Discovery staleness audit has run (A–J below). Package sections below remain skeletons: `/grind-plan` fills permitted files, acceptance criteria and test selectors. FIN-00 and FIN-00b are specified because their facts were verified during scaffolding.

> **STALE — action required before FIN-00.** Section A is stale: `origin/main` has drifted from `1e85aa2` (handover doc, 02-08-2026) to `f0f4f47`, and HEAD from `8a57ad7` to `16fdc06`. The FIN-00 baseline gate must carve `feat/billing-engine-steps-1-6` from **current** `origin/main` (`f0f4f47`) and record that `baseline_sha` — do not branch from the stale handover SHA. The behavioural sub-finding (ledger writes outside `require_billing`) remains verified and is what FIN-00b will gate. No verdict was overridden to unblock a package; no loop is armed.

## Status board

| ID | Work package | Status | Dependency | Risk |
|----|--------------|-------:|------------|------|
| FIN-00 | Baseline gate (human-executed, not a loop) | Active | None | High |
| FIN-00b | Ledger write gating | Blocked | FIN-00 | High |
| FIN-01 | Domain and calculation audit | Blocked | FIN-00b | Medium |
| FIN-02 | Role and route protection | Blocked | FIN-01 | High |
| FIN-03 | Therapist billing overview | Planned | FIN-02 | Medium |
| FIN-04 | Session breakdown | Planned | FIN-03 | Medium |
| FIN-05 | Late session workflow | Planned | FIN-04 | High |
| FIN-06 | Absence disputes | Planned | FIN-04 | High |
| FIN-07 | Adjustments ledger | Planned | FIN-01, FIN-02 | High |
| FIN-08 | Therapist submission | Planned | FIN-05, FIN-06, FIN-07 | High |
| FIN-09 | Finance workflow board | Planned | FIN-08 | Medium |
| FIN-10 | Admin approval workflow | Planned | FIN-09 | High |
| FIN-11 | Payment status | Planned | FIN-10 | Medium |
| FIN-12 | Regression and release | Planned | FIN-01–FIN-11 | High |

Status values: `Planned` · `Blocked` · `Active` · `Done`. A package is `Blocked` while any dependency is not `Done`, or while an open question or stale audit section blocks it.

## Prior-audit staleness table

Every section of [docs/Cursor_Handover_Finance_Module_Build_Readiness.md](../Cursor_Handover_Finance_Module_Build_Readiness.md) needs a verdict with a proving repo path before a package may rely on it. Filled by `/grind-plan`. Audited 03-08-2026 against HEAD `16fdc06` (branch `billing`).

| Section | Verdict | Proving path | Blocks packages |
|---------|---------|--------------|-----------------|
| A. Git and deployment state | stale | git identifiers drifted: `git rev-parse HEAD`=`16fdc06` vs doc `8a57ad7`; `git rev-parse origin/main`=`f0f4f47` vs doc `1e85aa2`. Write-path sub-finding still verified: [backend/app/api/v1/daily_logs.py](../../backend/app/api/v1/daily_logs.py) L394-402, [backend/app/services/session_service.py](../../backend/app/services/session_service.py) L261 | FIN-00 (baseline must re-derive from current `origin/main`, not doc SHA) |
| B. Engine implementation inventory | verified | [backend/app/services/billing_step6_service.py](../../backend/app/services/billing_step6_service.py) L406 `compute_monthly_fixed_amount_v6`, L672 `build_step6_monthly_periods`; untracked migrations `y2z3a4b5c6d7`, `z3a4b5c6d7e8`, `a4b5c6d7e8f9`; still uncommitted per working tree | — |
| C. Read-only dashboard API contract | verified | [backend/app/api/v1/finance_ops.py](../../backend/app/api/v1/finance_ops.py) (finance-overview/summary, finance-reports) | — |
| D. Existing frontend inventory | verified | [frontend/src/components/admin-portal/AdminFinanceOverviewTab.jsx](../../frontend/src/components/admin-portal/AdminFinanceOverviewTab.jsx), `AdminInvoicesPage.jsx`, `InvoiceComposer.jsx`, `AdminClientInvoicePage.jsx` | — |
| E. Forest design-system inventory | verified | [frontend/src/styles/forest-light-theme.css](../../frontend/src/styles/forest-light-theme.css), [docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md) present; no `ConfidenceBadge` component/token (missing sub-item holds) | — |
| F. RBAC and privacy | verified | [backend/app/core/permissions.py](../../backend/app/core/permissions.py) L46-48, L154-156 (`invoice.generate`/`invoice.approve`/`payout.override`) | — |
| G. Exception system readiness | verified | `BillingCalcException` [backend/app/models/billing_step6.py](../../backend/app/models/billing_step6.py) L54, `BillingPeriodFlag` [backend/app/models/ledger_billing.py](../../backend/app/models/ledger_billing.py) L140, `BillingDispute` [backend/app/models/client_billing.py](../../backend/app/models/client_billing.py) L188 | — |
| H. Stage 1 build boundary | verified | advisory boundary; host surface exists at [frontend/src/components/admin-portal/AdminFinanceOverviewTab.jsx](../../frontend/src/components/admin-portal/AdminFinanceOverviewTab.jsx) | — |
| I. Required documents | verified | three named docs still absent (glob 0 hits); [docs/billing-architecture.md](../billing-architecture.md) present | — |
| J. Readiness table | verified | rollup of A-I; git-hygiene rows inherit A staleness | — (inherits A) |

---

## FIN-00 — Baseline gate

**Human-executed. This is not a loop.** No agent may perform it: it involves branch creation, commit selection and cherry-picking across 131 dirty files.

**Outcome:** a clean, committed baseline that loops can diff and revert against, with its SHA recorded on this board.

**Why:** the finance engine exists only as uncommitted working-tree files — `backend/app/services/billing_step6_service.py`, `backend/app/models/billing_step6.py` and three Alembic revisions (`y2z3a4b5c6d7`, `z3a4b5c6d7e8`, `a4b5c6d7e8f9`) are untracked; `backend/app/services/billing_ledger_service.py` is modified. A loop on this tree cannot tell its own edits from pre-existing work and has no revert point.

**Steps (human):** carve `feat/billing-engine-steps-1-6` from `origin/main`, commit engine-only changes, keep the ~84-commit clinical/voice stack out of it, keep `ENABLE_BILLING=false` on production, then record the SHA below and in the `baseline_sha` header.

**Completion:** `git status --porcelain` is empty and `baseline_sha` is set.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-00b — Ledger write gating

**First loop.** Dependencies: FIN-00.

**Outcome:** no ledger write occurs while the billing module is off.

**Why:** [backend/app/api/v1/daily_logs.py](../../backend/app/api/v1/daily_logs.py) calls `billing_ledger_service.upsert_from_daily_log_approved`, `consume_package_session`, `ensure_period_charges` and `sync_session_status` on log approve, and [backend/app/services/session_service.py](../../backend/app/services/session_service.py) writes on `end_session` — all outside `require_billing`. Code-without-cutover is not behaviour-without-cutover until these no-op with the flag off.

**Migration required:** no.

**Permitted scope:** `backend/app/api/v1/daily_logs.py`, `backend/app/services/session_service.py`, `backend/app/core/feature_flags.py`, one new backend test file.

**Non-goals:** changing calculation logic, ledger schema, status names or flag defaults; touching any frontend.

**Backend acceptance criteria:**

- [ ] With billing off, approving a daily log writes no `billing_ledger` row.
- [ ] With billing off, `end_session` writes no ledger row.
- [ ] With billing on, existing ledger behaviour is byte-identical to baseline.
- [ ] Gating is a shared predicate, not duplicated inline conditionals.
- [ ] Session and log approval still succeed with billing off — no user-facing error.

**Permission and audit:** no permission change. Skipped writes must be observable (log or counter), not silent.

**Targeted tests:** `./scripts/agent-pytest.sh app/tests/<new_test>.py::<test_name>` for both flag states.

**Completion:** `./scripts/grind-check.sh backend <selectors>`

**Risk:** High. **max_attempts:** 4.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-01 — Domain and calculation audit

Dependencies: FIN-00b. Risk: Medium. max_attempts: 3.

**Outcome:** the staleness table above is complete, and the **frozen finance backend test selector list** is recorded in the `frozen_selectors` header. FIN-12 verifies against that list, not the full suite.

**Non-goals:** any code change. This package is read-and-record only.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-02 — Role and route protection

Dependencies: FIN-01. Risk: High. max_attempts: 4.

**Outcome:** every finance route enforces the correct role and case scope before any financial figure is exposed. Includes deciding whether `finance_ops` moves behind `require_billing`.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-03 — Therapist monthly billing overview

Dependencies: FIN-02. Risk: Medium. max_attempts: 4.

**Outcome:** therapist selects an eligible billing month and sees backend-authoritative totals with status, client-wise figures reconciling to the monthly total, and loading, empty, error and unauthorized states.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-04 — Client-wise earnings and session breakdown

Dependencies: FIN-03. Risk: Medium. max_attempts: 4.

**Outcome:** session-level breakdown per client, every line traceable to a backend line item.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-05 — Late session addition workflow

Dependencies: FIN-04. Risk: High. max_attempts: 4.

**Outcome:** therapist adds an eligible late session with a required reason, captured as auditable structured data.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-06 — Leave and child-absence dispute workflow

Dependencies: FIN-04. Risk: High. max_attempts: 4.

**Outcome:** absence and leave calculations are visible and contestable, with a documented dispute lifecycle.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-07 — Adjustments and deductions ledger

Dependencies: FIN-01, FIN-02. Risk: High. max_attempts: 4.

**Outcome:** deductions and adjustments are a first-class auditable ledger, separate from session earnings, every entry carrying actor, reason and timestamp. Auditability lands before any admin adjustment UI.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-08 — Therapist preview, approval and submission

Dependencies: FIN-05, FIN-06, FIN-07. Risk: High. max_attempts: 4.

**Outcome:** therapist previews the monthly statement and submits it to finance, with a recorded submission event.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-09 — Finance-admin workflow board

Dependencies: FIN-08. Risk: Medium. max_attempts: 4.

**Outcome:** submitted therapist billing appears as workflow cards, filterable by month, status, therapist and exception type.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-10 — Finance review, return and approval

Dependencies: FIN-09. Risk: High. max_attempts: 4.

**Outcome:** finance approves, returns or adjusts a submission, with a mandatory reason on every adjustment.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-11 — Payment-processing status

Dependencies: FIN-10. Risk: Medium. max_attempts: 4.

**Outcome:** approved billing moves into payment processing with trackable status and exceptions.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```

## FIN-12 — Integration, regression and release readiness

Dependencies: FIN-01 through FIN-11. Risk: High. max_attempts: 3.

**Outcome:** the whole therapist-to-finance-admin monthly journey verified end to end — therapist reviews, disputes, finance sees and returns or approves, adjustments stay auditable, totals reconcile at every stage, unauthorized roles cannot reach payout information.

**Verification:** the frozen selector list from FIN-01, plus frontend unit tests, lint and build. This is an integration loop: it finds and classifies failures, it does not redesign the module.

```
status:
files_changed:
tests_run:
result:
deviations:
new_risks:
baseline_sha:
date:
```
