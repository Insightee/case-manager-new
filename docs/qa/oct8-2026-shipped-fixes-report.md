# QA report — six fixes on `main` (8 Oct 2026)

**Branch:** `cursor/qa-8oct-e2e`  
**Environment:** Local Playwright E2E (SQLite `insightcase.e2e.db`, `alembic upgrade head`, `demo_seed`) + backend pytest. Not production. Postgres/docker-compose not required for this suite (Playwright `webServer` uses SQLite per repo convention).

## Automated runs

| Suite | Result |
|--------|--------|
| `backend` pytest (invoice 422, evidence, transition, recurring, parent chat, cm-meetings) | **29 passed** |
| `frontend` Playwright `e2e/oct8-shipped-fixes-qa.spec.js` | **11 passed**, 1 skipped (recurring mobile UI only on mobile) |
| `frontend` Playwright `e2e/oct8-version-notice-preview.spec.js` (`PLAYWRIGHT_SKIP_WEBSERVER=1`) | **5 passed** |
| `frontend` unit `appVersionUpdate.test.js` + `releaseLabel.test.js` (via preview spec) | **passed** |

## Pass/fail by fix and portal

| Fix | Parent / client | Therapist | Admin / CM | Notes |
|-----|-----------------|------------|------------|--------|
| **#98** Invoice package count 422 | N/A (API) | **Pass** (API fixture) | **Pass** (pytest month-end skip) | Playwright uses DB fixture script; UI copy not re-tested in browser |
| **#99** Evidence summary | **Pass** (403 pytest) | **Pass** (200 pytest) | **Pass** (pytest) | Clinical HTTP routes gated off in default E2E API; contract via pytest |
| **#100** Handover / transition | **Pass** (404 cross-family API) | **Pass** (pytest booking/payout) | **Pass** (pytest) | Full handover window covered in `test_transition_operational_access.py` |
| **#101** Session log submit / disputes / incidents | N/A | **Pass** (Incidents UI) | **Pass** (Disputes tab UI) | Late IST + session-expiry draft: **Pass** via `sessionLogSubmitHelpers.test.js` (unit), not full browser replay |
| **#104** Recurring booking | **Pass** (notification count API) | **Pass** (API + mobile sheet screenshot) | **Pass** (CM/shadow summary notification) | `outside_week` Mon/Wed on Thu start verified |
| **#102** Forest / version / meetings | **Pass** (cm-meetings, chat GET, build label dev + preview) | **Pass** | **Pass** (`/admin/meetings`) | Update banner copy/reinstall: **unit + preview `version.json`**; full PWA banner in preview blocked by prod-only polling (see gaps) |

## Screenshots (375px / preview)

Saved under `/opt/cursor/artifacts/oct8-qa/`:

- `recurring-sheet-mobile.png`
- `therapist-incidents-mobile.png`, `therapist-incidents-desktop.png`
- `admin-disputes-mobile.png`, `admin-disputes-desktop.png`
- `admin-meetings-mobile.png`, `admin-meetings-desktop.png`
- `parent-version-label-desktop.png`
- `preview-build-label-{parent,therapist,admin}.png`

## Gaps / follow-up (not product bugs)

1. **#102 update notice banner in Playwright preview:** `fetchRemoteVersionMeta` only runs when `import.meta.env.PROD` is true; preview + init-script mocking did not surface the banner reliably in automation. **Mitigation:** `version.json` newer label + `appVersionUpdate` unit tests + manual PWA check on Vercel preview recommended.
2. **#98–#99 HTTP on E2E API:** Package-null via public PATCH does not clear `package_session_count` (DB fixture required); clinical reports router disabled without `ENABLE_CLINICAL_REPORTS_ENGINE` on E2E server.
3. **#101:** Session-expiry draft retention and late-after-midnight IST submit not exercised in browser this run (unit coverage only).

## Bugs found

**None** blocking release from this QA pass. No product code changes were made.
