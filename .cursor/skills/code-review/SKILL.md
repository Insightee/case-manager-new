---
name: code-review
description: Review an InsighteCase branch or PR for bugs, regressions, security and cross-portal gaps. Use when asked to "review", "find bugs", "check this PR", "self-review before PR", or when a Cursor agent's branch must be checked before the owner merges. Report-only by default; never approves-and-merges.
license: Apache-2.0 (Sentry); see ../security-review/LICENSE-APACHE-2.0.txt and ../THIRD_PARTY_NOTICES.md
---

# Code Review (find bugs)

## Phase 1: Gather the complete input

1. `git fetch origin main` then `git diff origin/main...HEAD --stat`, then the full diff. If output is truncated, read each changed file until you have seen every changed line.
2. List every changed file before going further. Read the PR description and its cross-portal impact section (`cross-portal-impact`).

## Phase 2: Map the attack and blast surface

For each changed file list: user inputs (path, query, body, headers), DB queries and writes, auth/permission checks, session/state operations, external calls (email, WhatsApp, storage, payments), money calculations, migrations, and which portals render it (parent, therapist, admin/CM).

## Phase 3: Checklist (every item, every file)

Correctness and regressions
- [ ] Runtime errors: `None` access, missing keys, wrong types, unhandled API errors in the UI (error handlers that themselves crash)
- [ ] Side effects: GET/list endpoints that write or commit; duplicate notifications; behaviour changes in other portals
- [ ] Backwards compatibility: API contract changes have every caller updated (all three portals, PWA cache, cron jobs `session-day-end`, `invoice-month-end`, `email-jobs`)
- [ ] Dates: IST business dates, half-open UTC intervals (`docs/REPORT_METRICS.md`), midnight crossings
- [ ] Money: billing engine is the source of truth (`.cursor/rules/insighte-billing.mdc`); no recomputed prices; bill-once; payouts go to the therapist who delivered
- [ ] Performance: N+1 queries (use `selectinload`/`joinedload`), unbounded loops or exports, missing pagination

Security (details in `security-review`)
- [ ] Injection (raw SQL / `text()` with f-strings), XSS (`dangerouslySetInnerHTML`)
- [ ] Authorization / IDOR: parent own cases only; therapist via `case_assignments`; therapists see no client billing
- [ ] Race conditions (read-then-write on bookings, slots, invoices), double submit
- [ ] Information disclosure in errors, logs, notifications, exports; no secrets committed

Tests and UI
- [ ] Tests cover each role that can and cannot act; no weakened or deleted tests; no hard-coded calendar dates
- [ ] UI follows `ui-consistency`; mobile per `mobile-responsive-qa`; tables/reports per `tables-and-reports`
- [ ] Migrations follow `migration-safety`

Flag for owner attention: schema changes, API contract changes, new dependencies, billing/payout logic, auth/RBAC, anything that runs on deploy.

## Phase 4: Verify each finding

Check it is not already handled elsewhere, search for an existing test, read surrounding context. Do not invent issues.

## Phase 5: Pre-conclusion audit

List every file reviewed, each checklist item as clean / issue / could-not-verify, and anything you could not check and why.

## Output

Priority: security > bugs > regressions > code quality. Skip style nits. For each issue:
`file:line` - one-line summary - **Severity** (Critical/High/Medium/Low) - **Problem** - **Evidence** - **Fix**.

Tone: specific and actionable; phrase uncertainty as a question. If nothing significant, say so.

Post the review as a PR comment or in your reply only. Do not approve-and-merge, push to `main`, force-push, or resolve threads on others' behalf. Fix findings only when asked or when they are in your own PR's scope.

---
Adapted from getsentry/skills `skills/find-bugs` and `skills/code-review` (commit d18b7aa8ba87), https://github.com/getsentry/skills. Copyright 2025 Functional Software, Inc. dba Sentry. Licensed under the Apache License 2.0.
Changes: merged the two skills; replaced `gh repo view` with `origin/main`; replaced Django examples with SQLAlchemy; added InsighteCase checks (cross-portal, IST dates, billing SSOT, cron jobs, GET side effects); added the no-merge rule.
