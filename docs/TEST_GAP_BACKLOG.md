# Test gap backlog (post comprehensive review)

## Closed by this review (automated)

| Item | Location |
|------|----------|
| Invoice submit + finance approve + breakdown | `test_comprehensive_review.py` |
| Parent support ticket + staff reply | `test_comprehensive_review.py` |
| Reschedule confirm after parent request | `test_comprehensive_review.py` |
| Workbench reschedules section when pending | `test_comprehensive_review.py` |
| Ticket staff escalate | `test_comprehensive_review.py` |
| AuthZ: viewer assign 403, invalid reschedule 400 | `test_comprehensive_review.py` |
| Role `/auth/me` smoke | `test_comprehensive_review.py` |
| E2E workbench smoke | `frontend/e2e/admin-workbench.spec.js` |

## Remaining gaps (manual or future)

| Priority | Gap |
|----------|-----|
| P1 | Leave deduction in invoice preview |
| P1 | Parent ticket escalate + accept/rate |
| P2 | Assignment `PATCH .../booking` (extend end date) |
| P2 | Shadow-block preview/create HTTP tests |
| P2 | Holiday range / `mark_holiday_range` |
| P2 | `invite-client` scheduling flow |
| P3 | E2E finance invoice full UI path |
| P3 | E2E kanban bulk assign (seed-dependent) |
| P3 | Playwright for `hr@demo.com` portal |
| P3 | `SCHOOL_COORDINATOR` demo login in seed |

## Running tests

```bash
cd backend && python3 -m pytest app/tests -q
cd frontend && npm run lint && npm run build
cd frontend && npm run test:e2e
```
