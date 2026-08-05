# Finance Cutover Runbook (Loop E)

Operational checklist for enabling finance money surfaces **one at a time**. Each step requires human sign-off before the next. Default posture: **provisional / writes off** until the final gate.

**Prerequisites**

- Loops C (payout settlement) and D (dispute grievance) merged or signed-off on draft PRs
- `finance_walkthrough_fixture` regression green on every flag change
- Finance spreadsheet for the verification month ready for reconciliation

**Regression command (run after every flag toggle)**

```bash
cd backend
alembic upgrade head
python3 -m app.seed.finance_walkthrough_fixture  # or fixture_run(force=True) via tests
python3 -m pytest app/tests/test_finance_money_fixes.py app/tests/test_therapist_payout_settlement.py app/tests/test_dispute_grievance_flow.py -q
```

---

## Step 0 — Baseline (no live money)

| Variable | Value | Verify |
|----------|-------|--------|
| `ENABLE_BILLING` | `false` | Admin billing routers 404 or provisional banner |
| `BILLING_LEDGER_WRITES` | `false` | Mutations return 403 pre-cutover |
| `ZOHO_BOOKS_LIVE_PUSH` | `false` | Zoho status `not_configured` / no-op |
| `PAYOUT_EXPORT_ENABLED` | `false` | Export batch button disabled in UI |
| `PAYOUT_RELEASE_ENABLED` | `false` | No live Razorpay calls |
| `FINANCE_CUTOVER_COMPLETE` | `false` | Control Tower shows provisional banner |

**Sign-off:** ☐ Finance lead ☐ Engineering

---

## Step 1 — Zoho Books push (staging key)

| Action | `ZOHO_BOOKS_API_KEY=<staging>` + `ZOHO_BOOKS_LIVE_PUSH=true` |
|--------|----------------------------------------------------------------|
| Verify | New client invoices appear in Books; `external_refs` rows created |
| Rollback | `ZOHO_BOOKS_LIVE_PUSH=false` |

**Sign-off:** ☐ Finance lead

---

## Step 2 — Zoho payment pull (if wired)

| Action | Enable payment reconciliation job or document stub if not built |
| Verify | Recorded payments match Books |
| Rollback | Disable pull job |

**Sign-off:** ☐ Finance lead

---

## Step 3 — Client billing + parent pay (mock gateway)

| Action | `ENABLE_BILLING=true` + `BILLING_LEDGER_WRITES=true` + Vercel `VITE_ENABLE_CLIENT_BILLING=true` |
| Verify | Parent mock pay flow; collectible/hold math on IC-WK-* fixture |
| Rollback | Disable Vite flag; `ENABLE_BILLING=false` |

**Sign-off:** ☐ Finance lead ☐ Product

---

## Step 4 — Payout verification month (export only, no release)

| Action | `PAYOUT_EXPORT_ENABLED=true`, **`PAYOUT_RELEASE_ENABLED=false`**, `PAYOUT_PROVIDER_LIVE=false` |
| Verify | Run one billing month: approve statements → mock export batch → reconcile totals against finance spreadsheet |
| Rollback | `PAYOUT_EXPORT_ENABLED=false`; delete in-flight batches if needed |

**Sign-off:** ☐ Finance lead (reconciliation box below)

### Verification month reconciliation

| Field | Value |
|-------|-------|
| Billing month | |
| Statements exported | |
| Gross / TDS / Net (system) | |
| Gross / TDS / Net (spreadsheet) | |
| Delta within tolerance? | ☐ Yes ☐ No |

---

## Step 5 — Live payout release (last)

| Action | `PAYOUT_RELEASE_ENABLED=true` + `PAYOUT_PROVIDER_LIVE=true` + `PAYOUT_PROVIDER=RAZORPAY` |
| Verify | **One** therapist, **one** transfer; confirm in Razorpay dashboard |
| Rollback | `PAYOUT_RELEASE_ENABLED=false`; failed transfers return to APPROVED queue (Loop C) |

**Sign-off:** ☐ Finance lead ☐ Founder/COO

---

## Step 6 — Cutover complete (final)

Only after Steps 1–5 signed off and verification month reconciled:

| Action | `FINANCE_CUTOVER_COMPLETE=true` |
| Verify | Control Tower drops provisional banner; production smoke on real month |
| Rollback | `FINANCE_CUTOVER_COMPLETE=false` (does not undo ledger rows — use correction flows) |

**Sign-off:** ☐ Finance lead ☐ Founder/COO

---

## Environment reference

See [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) — sections **Billing / finance flags** and **Payout money-OUT (Loop C)**.

## Incident rollback (any step)

1. Set the step's flag(s) back to **false** in Railway/Vercel
2. Re-run fixture regression command above
3. Log incident in finance ops channel with billing month + case codes affected
4. Do **not** set `FINANCE_CUTOVER_COMPLETE=true` until root cause cleared
