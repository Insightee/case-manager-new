# Changelog

All notable changes to InsightCase are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

**How to update:** Add bullets under `[Unreleased]` when your PR merges. Before each production release, move `[Unreleased]` into a dated section (`## [YYYY-MM-DD]`) and run `./scripts/pre-release-check.sh`.

---

## [Unreleased]

### Added
- Team workflow: `CONTRIBUTING.md`, PR template, CODEOWNERS, pre-push/pre-release scripts, pre-commit hooks, CI contributor guards.
- RBAC editor: bulk Select all / Clear all for service categories, multi-select dropdown, unified clinical features panel.
- People module: central invite policy (max 2 pending per email, one role per email), uniform row actions (staff/therapists/clients), bulk activate/deactivate and bulk invite cancel, client Deactivated when all cases closed with reactivate case flow, case CM edit modal.
- `user.read` permission for Case Manager and Supervisor — read-only Staff directory in People without account management.
- People directory loads all user pages (not just first 100); server-side search by email/name.

### Changed
- *(Add PR bullets here: `- **@author** — short description (#PR)`)*
- People → Clients: family list includes case status, `allCasesClosed`, and primary case id for actions.
- Pending invite UI explains cancel vs post-registration login paths.

### Fixed
- Use current location: reverse geocode now uses API base URL (works on Vercel production).
- Security: active portal users no longer hidden from People when total users exceeds 100.

---

## [2026-05-30]

Support hub, finance/HR ops, billing UX, and environment documentation (`e7d9436`).

### Added
- Support access service and `GET /api/v1/admin/support/capabilities` for hub tab visibility.
- HR reports API/page and finance overview/reports/bulk ops endpoints.
- Demo support tickets in seed data; `test_support_access.py`, finance/HR report tests.
- `docs/ENVIRONMENT_VARIABLES.md`, expanded `docs/README.md`, support/HR handover and ADR-0001.

### Changed
- Admin support hub and sidebar use server capabilities; `tickets`/`incidents` features on billing and hr_ops modules.
- Invoice composer, client billing tabs, therapist payouts dashboard UX.
- Session log test isolation via `session_helpers.py`; incident PATCH requires incidents module feature with DB session.

### Fixed
- Profile session log tests under shared CI DB; incident patch 403 for case managers missing `db` on feature check.

---

## [2026-05-30] — earlier

Therapist reliability, admin onboarding UX, Alembic migration `f7a8b9c0d1e3` (`c93d297`).

---

## Template (copy for new releases)

```markdown
## [YYYY-MM-DD]

### Added
- **@github-user** — Feature summary (#123)

### Changed
- **@github-user** — Behaviour change (#124)

### Fixed
- **@github-user** — Bug fix (#125)
```
