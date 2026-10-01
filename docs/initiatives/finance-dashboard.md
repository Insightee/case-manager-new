# Finance Dashboard Improvement Initiative

status: PLANNING
initiative_owner: Midhun
implementation_mode: bounded_work_packages
maximum_work_packages: 13
plan: [docs/plans/finance-dashboard-revamp.md](../plans/finance-dashboard-revamp.md)
open_questions: [docs/plans/finance-open-questions.md](../plans/finance-open-questions.md)

## Intent

Improve the complete finance dashboard so therapists and finance administrators can review, dispute, approve, process and track monthly billing accurately.

This is an initiative, not permission to edit the entire system at once. Execution is one bounded work package at a time via [docs/LOOP_SYSTEM.md](../LOOP_SYSTEM.md).

## Primary users

1. Therapist
2. Finance Admin
3. Super Admin

CRM and HR users may see operational status where authorised, but must not receive confidential billing or therapist payout access unless explicitly permitted. Neither role holds `invoice.*` in the `ROLE_PERMISSIONS` matrix today ([backend/app/core/permissions.py](../../backend/app/core/permissions.py)); confirm the org module map before exposing anything.

## Desired outcome

A reliable monthly finance workflow covering therapist billing review, client-wise earnings, session breakdown, late-added sessions with explanations, invoice preview and approval, leave and child-absence disputes, deductions and adjustments, therapist monthly payout total, finance-admin approval, payment-processing status, and audit history.

## Non-negotiables

- Backend remains FastAPI deployed on Railway.
- Financial calculations are deterministic backend logic.
- Frontend must not calculate authoritative totals.
- Existing role and case permissions must be preserved.
- Every financial adjustment requires an audit trail.
- No silent defaults for missing financial inputs.
- No database migration without a separately reviewed work package.
- No Railway deployment change without explicit approval.
- Use Forest Light design standards ([docs/design/UI_CONTRACT.md](../design/UI_CONTRACT.md)). Finance chrome migrates in the **admin phase**; do not globally retoken the app in a finance PR ([SURFACE_MIGRATION.md](../design/SURFACE_MIGRATION.md)).
- Do not weaken tests to obtain a pass.
- **No loop runs on a dirty tree.** The engine currently exists as uncommitted work; the baseline gate (FIN-00) is human-executed and must record a `baseline_sha` on the plan board before any loop starts.
- **Never infer a missing financial rule.** Ambiguity goes to the open-questions register and blocks the package.

## Current constraints verified in repo

| Constraint | Where |
|-----------|-------|
| `ENABLE_BILLING` / `settings.enable_billing` defaults `False`; gates admin invoice/ledger/client-billing routers via `require_billing()` | [backend/app/core/config.py](../../backend/app/core/config.py), [backend/app/core/feature_flags.py](../../backend/app/core/feature_flags.py) |
| `VITE_ENABLE_BILLING` hides finance nav; forced off on canonical production | [frontend/src/lib/productFeatureFlags.js](../../frontend/src/lib/productFeatureFlags.js) |
| Ledger writes happen on log approve and `end_session` **outside** `require_billing` | [backend/app/api/v1/daily_logs.py](../../backend/app/api/v1/daily_logs.py), [backend/app/services/session_service.py](../../backend/app/services/session_service.py) |
| `finance_ops` routes are not behind `require_billing` | [backend/app/api/v1/finance_ops.py](../../backend/app/api/v1/finance_ops.py) |
| Production runs Alembic migrations on every API start | [backend/scripts/start-production.sh](../../backend/scripts/start-production.sh) |
| Prior audit, treat as **not current** until section-by-section verified | [docs/Cursor_Handover_Finance_Module_Build_Readiness.md](../Cursor_Handover_Finance_Module_Build_Readiness.md) |

## Role and permission baseline

| Role | Billing permissions today |
|------|---------------------------|
| SUPER_ADMIN | all |
| FINANCE | `invoice.approve`, `invoice.generate`, `payout.override` + module `billing` |
| ADMIN / MODULE_ADMIN / CASE_MANAGER | `invoice.approve` |
| THERAPIST | `invoice.generate`, own invoices only |
| PARENT | parent billing APIs only |
| HR / CRM | no `invoice.*` |

Known gaps before any admin-adjustment package: no maker-checker on rate changes, no closed-period lock.

## Known user journeys

### Therapist

1. Opens monthly billing.
2. Sees client-wise earnings.
3. Reviews session-level breakdown.
4. Adds or contests an eligible line item.
5. Provides a reason for late additions.
6. Reviews absence and leave calculations.
7. Sees deductions and adjustments separately.
8. Previews the monthly invoice or payout statement.
9. Approves and submits it to finance.

### Finance Admin

1. Sees submitted therapist billing as workflow cards.
2. Filters by month, status, therapist and exception type.
3. Reviews calculations and disputed items.
4. Approves, returns or adjusts the submission.
5. Records a reason for every adjustment.
6. Moves approved billing into payment processing.
7. Tracks payment status and exceptions.

## Success criteria

Complete only when:

- every displayed total traces to backend line items;
- therapist and finance-admin roles see the correct information;
- disputes have a documented lifecycle;
- adjustments carry actor, reason and timestamp;
- loading, empty, error and permission states exist;
- targeted tests pass for every work package;
- the frozen finance backend selector list from FIN-01 passes;
- frontend unit tests, lint and build pass;
- no unresolved P0 or P1 issue remains;
- no unanswered entry in the open-questions register.

## Required discovery output

Before implementation, `/grind-plan` must produce:

1. A staleness verdict — `verified`, `stale` or `missing`, each with a proving repo path — for **every section A–J** of the prior handover doc. Stale sections are re-derived before dependent packages start.
2. Current finance frontend inventory.
3. Current finance APIs and backend services.
4. Existing database models and statuses.
5. Existing calculation rules.
6. Existing tests, plus the **frozen finance backend test selector list**.
7. Permission model.
8. Current user journey.
9. Gap analysis.
10. Risk register.
11. Proposed work packages and their dependencies.
12. Proposed acceptance tests.

## Work-package rules

Each package must deliver one coherent outcome, name its permitted files, carry measurable acceptance criteria and targeted tests, normally need no more than four attempts, and be verified before any dependent package begins. One package at a time.

## Test commands

Targeted backend (required form):

```bash
./scripts/agent-pytest.sh app/tests/test_billing_step6.py::<test_name>
./scripts/agent-pytest.sh app/tests/test_billing_eligibility_step5.py -k "keyword"
```

Completion gate:

```bash
./scripts/grind-check.sh both app/tests/test_billing_step6.py -k "monthly"
```

Full-suite runs are out of scope for loops; FIN-12 verifies the frozen selector list.
