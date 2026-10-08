---
name: tdd
description: Test-first development and verification-before-done for InsighteCase. Use when building a feature or fixing a bug, when asked for "TDD", "red-green", "add tests", or before claiming any fix is done or opening a PR. Covers pytest (backend) and the frontend build/e2e gates.
license: MIT (Matt Pocock); see ../THIRD_PARTY_NOTICES.md
---

# Test-Driven Development

TDD is the red -> green loop. This skill makes that loop produce tests worth keeping, and defines what "done" means in this repo.

## What a good test is

Tests verify behaviour through public interfaces, not implementation details. A good test reads like a specification ("therapist can submit a late log with a late reason") and survives refactors. See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for when to mock. Examples there are TypeScript; the same rules apply to pytest.

## Seams: where tests go in this repo

A **seam** is the public boundary you test at. Before writing tests, list the seams in your plan / PR description with one line each on what they catch and miss. Usual seams here:

| Seam | How |
|------|-----|
| API endpoint, per role | FastAPI test client in `backend/app/tests/`, one test per role that can and cannot act (parent, therapist, CM/admin). RBAC/migration changes **require** tests (`CONTRIBUTING.md`). |
| Service function | `backend/app/services/*_service.py` called directly for pure business rules (billing, payouts, handovers). |
| Migration | Alembic up/down + proof registry (see `migration-safety`). |
| UI flow | `frontend/e2e/` Playwright, or a unit test next to the module (`*.test.js`). |

## Anti-patterns

- **Implementation-coupled:** mocks internal collaborators, tests private functions, or verifies through a side channel. Breaks on refactor without behaviour change.
- **Tautological:** the expected value is recomputed the way the code computes it. Use known literals (e.g. "₹500 handover day", "1,210 rows").
- **Horizontal slicing:** all tests first, then all code. Work in vertical slices: one test -> one implementation -> repeat.
- **Hard-coded calendar dates:** use dates relative to "today in IST" or freeze time explicitly; a fixed date already broke `test_reschedule` once.

## Rules of the loop

- **Red before green.** Write the failing test, watch it fail for the right reason, then write only enough code to pass.
- **One slice at a time.** One seam, one test, one minimal implementation per cycle.
- **Never delete or weaken a test to go green.** Change a test only when the behaviour change is intended, and say so in the PR.
- **No suppressions** (`# type: ignore`, `eslint-disable`, `pytest.skip`) to silence failures.
- Refactoring belongs to review (`code-review`), not the red -> green cycle.

## Verification before done (required)

Inner loop (fast, scoped): `./scripts/grind-check.sh backend app/tests/test_x.py -k name` or `./scripts/grind-check.sh frontend`. Stop after ~10 failed iterations and report what blocks you.

Before you say "done" or open a PR, run and paste the summary lines (not full logs):
1. `./scripts/run-ci-parity-checks.sh` - single Alembic head, full backend pytest, frontend production build.
2. `./scripts/pre-push-check.sh` - refuses `main`, runs `./scripts/check_staged_secrets.sh`.
3. If you touched migrations: `cd backend && PYTHONPATH=.:alembic python3 scripts/check_alembic_integrity.py`.

Report counts exactly (passed / failed / skipped). Unknown is not zero: if a check could not run, say so. PRs only after these pass; never merge or deploy.

---
Adapted from mattpocock/skills `skills/engineering/tdd` (commit f3fc5632f401), https://github.com/mattpocock/skills. MIT License, Copyright (c) 2026 Matt Pocock. `tests.md` and `mocking.md` are copied unmodified.
Changes: replaced "confirm seams with the user" with "write seams into the plan/PR" (cloud agents run unattended); removed the reference to a `codebase-design` skill that does not exist here; added repo seams, the verification gate and the no-suppression rules (from awesome-cursor-skills `grinding-until-pass`, CC0).
