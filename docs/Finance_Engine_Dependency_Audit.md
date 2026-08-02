# Dependency audit — feat/billing-engine-steps-1-6 vs origin/main
| Path | On origin/main | Port risk |
|------|----------------|-----------|
| `backend/alembic/versions/y2z3a4b5c6d7_case_monthly_billing_first_class.py` | no | ADD_NEW |
| `backend/alembic/versions/z3a4b5c6d7e8_period_charges_retainer_flags.py` | no | ADD_NEW |
| `backend/alembic/versions/a4b5c6d7e8f9_step6_windows_rate_addon.py` | no | ADD_NEW |
| `backend/app/models/billing_step6.py` | no | ADD_NEW |
| `backend/app/services/billing_step6_service.py` | no | ADD_NEW |
| `backend/app/services/billing_ledger_service.py` | yes | PORT_WITH_DIFF |
| `backend/app/api/v1/ledger_billing.py` | yes | PORT_WITH_DIFF |
| `backend/app/api/v1/daily_logs.py` | yes | PORT_WITH_DIFF |
| `backend/app/api/v1/admin.py` | yes | PORT_WITH_DIFF |
| `backend/app/api/v1/cases.py` | yes | PORT_WITH_DIFF |
| `backend/app/core/billing_validation.py` | yes | PORT_WITH_DIFF |
| `backend/app/core/config.py` | yes | PORT_WITH_DIFF |
| `backend/app/core/database.py` | yes | PORT_WITH_DIFF |
| `backend/app/core/feature_flags.py` | no | MAIN_MISSING_FILE—CHECK_STAGING_ONLY |
| `backend/app/models/__init__.py` | yes | PORT_WITH_DIFF |
| `backend/app/models/case.py` | yes | PORT_WITH_DIFF |
| `backend/app/models/ledger_billing.py` | yes | PORT_WITH_DIFF |
| `backend/app/models/session.py` | yes | PORT_WITH_DIFF |
| `backend/app/schemas/billing.py` | yes | PORT_WITH_DIFF |
| `backend/app/services/allotment_service.py` | yes | PORT_WITH_DIFF |
| `backend/app/services/session_service.py` | yes | PORT_WITH_DIFF |
| `backend/app/tests/test_billing_pay_share.py` | yes | PORT_WITH_DIFF |
| `backend/app/tests/test_billing_eligibility_step5.py` | no | ADD_NEW |
| `backend/app/tests/test_billing_step6.py` | no | ADD_NEW |
| `backend/app/tests/test_monthly_billing_rate_guard.py` | no | ADD_NEW |
| `backend/app/tests/test_period_charge_calculator.py` | no | ADD_NEW |
| `backend/scripts/staging_step5_eligibility_acceptance.py` | no | ADD_NEW |
| `backend/scripts/verify_july_2026_therapist_payout.py` | no | ADD_NEW |
| `frontend/src/components/admin-portal/AdminCaseAllotmentWizard.jsx` | yes | PORT_WITH_DIFF |
| `frontend/src/lib/productFeatureFlags.js` | yes | PORT_WITH_DIFF |
| `docs/ENVIRONMENT_VARIABLES.md` | yes | PORT_WITH_DIFF |
| `CHANGELOG.md` | yes | PORT_WITH_DIFF |

## Notes
- `x1y2z3a4b5c6` (prior down_revision for y2z3) is **not** on origin/main — rebuild parent to merge of main heads.
- `backend/app/core/feature_flags.py` exists on billing WIP but **not** on origin/main — port ENABLE_BILLING / BILLING_LEDGER_WRITES into main's config location.
- Blind copy of `session_service.py` / `daily_logs.py` from billing WIP would pull clinical deltas — surgically patch ledger call sites only.
