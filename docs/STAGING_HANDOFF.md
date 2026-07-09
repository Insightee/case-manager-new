# Staging handoff — stabilisation pre-reports rebuild

**Branch:** `staging/stabilisation-pre-reports`  
**Date:** 2026-07-10  
**Production:** Not touched. Deploy this branch to Vercel/Railway **staging** only.

## What this release does

Pauses feature expansion and stabilises therapist session logs + legacy monthly reports pipeline. Half-built report/session UI is **opt-in via env flags** (default off).

## Feature flags (staging Vercel)

Set explicitly on staging; unset = legacy stable behaviour:

| Flag | Purpose |
|------|---------|
| `VITE_ENABLE_REPORTS=true` | Show therapist/admin reports (not Coming Soon) |
| `VITE_ENABLE_REPORT_BUILDER=true` | Observation/IEP builder routes |
| `VITE_REPORTS_REVAMP=true` | Case profile v2 shell (`CaseDetailRevamp`) |
| `VITE_CASE_REPORTS_TAB_V2=true` | **Deferred** Stitch Reports tab — do not enable until rebuild |
| `VITE_GOALS_STRATEGIES_ENGINE_V2=true` | **Deferred** assigned goals UI |
| `VITE_STRUCTURED_SESSION_EVIDENCE=true` | **Deferred** structured session log fields |
| `VITE_MONTHLY_REPORTS_USE_CLINICAL_ENGINE=true` | Engine monthly writes (future) |

**Recommended staging (stable):** `VITE_ENABLE_REPORTS=true` only — pipeline dashboard + legacy monthly panel.

## Bugs fixed / stabilised

1. Reports global route no longer auto-redirects to half-built `CaseReportsTab` unless `VITE_CASE_REPORTS_TAB_V2=true`.
2. Case Reports hub `section=dashboard` falls back to stable `CaseReportsPanel` when tab v2 is off.
3. `GOALS_STRATEGIES_ENGINE_V2` and `STRUCTURED_SESSION_EVIDENCE` changed from opt-out to **opt-in** (reduces field-heavy UI).
4. `VITE_REPORTS_REVAMP` requires explicit `true` (no longer on by default).
5. Production module gates: `VITE_ENABLE_REPORTS` / `VITE_ENABLE_REPORT_BUILDER` default **off** even on preview unless set.
6. `CreateDraftModal` missing `apiFetch` import — draft modal crashed on open (fixed).

## Deferred (not removed — flagged)

- `CaseReportsTab` + summary API UI (`frontend/src/components/clinical/reports-tab/`)
- Goals & strategies v2 tab rewrite
- Structured session evidence panels
- Clinical monthly engine UI (`MonthlyReportRoute` when engine flag on)
- Legacy bridge scripts (`inventory_report_artifacts`, `backfill_legacy_monthly_to_clinical`) — ops only, not run on prod

## Conflicts with `origin/main` (merge before prod)

Files changed on both branches:

- `backend/app/api/v1/admin.py`
- `backend/app/api/v1/parent.py`
- `backend/app/seed/demo_seed.py`
- `frontend/index.html`
- `frontend/src/components/daily-logs/DailyLogsPage.jsx`
- `frontend/src/components/daily-logs/SubmitSessionLogForm.jsx`
- `frontend/src/components/therapist/TherapistSessionComposer.jsx`
- `frontend/src/index.css`
- `frontend/src/layouts/PortalShell.jsx`

Resolve session-log and portal shell conflicts carefully before any prod merge.

## Test results (local)

| Check | Result |
|-------|--------|
| `npm run build` | Pass |
| Backend `test_case_reports_summary_service` + `test_report_artifact_read_service` | Pass |
| Playwright `therapist-portal` + `staging-stabilisation-smoke` | **11 passed**, 1 skipped (no startable session in seed) |
| `npm run lint` | Pre-existing warnings (422); not introduced by this pass |

```bash
cd frontend && npm run build
cd .. && ./scripts/agent-pytest.sh app/tests/test_case_reports_summary_service.py::test_document_report_type_maps_monthly app/tests/test_report_artifact_read_service.py -q
cd frontend && npx playwright test e2e/therapist-portal.spec.js e2e/staging-stabilisation-smoke.spec.js
```

## Risks before reports rebuild

1. **Dual report stacks** still exist in code (`monthly_reports` + `clinical_reports` + `case_documents` PDFs).
2. **Case profile v2** (`CaseDetailRevamp`) is large — enable only with `VITE_REPORTS_REVAMP=true` on staging.
3. **main drift** — 9 conflict files; rebase/merge required before production.
4. **Playwright** assumes `VITE_ENABLE_REPORTS=true` in dev server (see `playwright.config.js`).
5. Do **not** enable `VITE_CASE_REPORTS_TAB_V2` until mobile QA + clinical sign-off on simplified report direction.

## Next branch

After staging validation, start reports rebuild on:

`feature/reports-rebuild-v2` (from `staging/stabilisation-pre-reports`)

Do not enable `VITE_CASE_REPORTS_TAB_V2` until the simplified mobile-first design is ready.
