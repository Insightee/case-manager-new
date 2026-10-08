---
name: cross-portal-impact
description: Mandatory before implementing any InsighteCase fix or feature. Produces a cross-portal impact and risk analysis (backend, parent/client, therapist, admin/CM, notifications, billing/payouts, permissions/IDOR, mobile/PWA) and writes it into the PR description before code is written. Use for every bug fix, feature, refactor or UI change, even when the request names only one portal.
---

# Cross-Portal Impact and Risk (InsighteCase)

**Owner rule:** every fix is scoped across all three portals (parent/client, therapist, admin/CM). No single-portal patches. Risks are analysed **before** implementing, and the changes are made in every portal that needs them.

For multi-portal feature design (role matrix, surface map, component split) also follow `docs/skills/cross-portal-product-design/SKILL.md`. This skill is the per-PR gate.

## Workflow

1. **Trace the domain path first.** `rg` the endpoint / service / model. Find every caller: three portals' routes and components, cron jobs (`session-day-end`, `invoice-month-end`, `email-jobs`), notification services (`backend/app/services/*notif*`, `email_service.py`, `appointment_notification_service.py`), exports and PDFs.
2. **Fill the checklist below** in the PR description (draft PR body or plan file) before writing code. Every row gets a decision; write **N/A + reason**, never blank.
3. **Implement the matching change in every affected portal** in the same PR, unless the owner splits it. If you defer a portal, say so under Risks.
4. **Test per role** (who can, who cannot) and re-check the table before marking the PR ready.

## PR description template (copy)

```markdown
## Cross-portal impact and risk

| Area | Affected? | Change made / why N/A | Risk if wrong |
|------|-----------|------------------------|---------------|
| Backend API / services / cron | | | |
| Database / migration | | | |
| Parent / client portal (`/parent/...`, `components/client-portal/`) | | | |
| Therapist portal (`/therapist/...`, `components/therapist/`, `cases/`, `daily-logs/`) | | | |
| Admin / CM / finance / HR (`/admin/...`, `admin-portal/`, `hr-portal/`) | | | |
| Notifications (in-app, email, WhatsApp, deep links in `shared/notificationLinks.js`) | | | |
| Billing / invoices / payouts (`.cursor/rules/insighte-billing.mdc`) | | | |
| Permissions / IDOR (case_assignments scope, parent own cases, modules) | | | |
| Mobile / PWA (bottom nav `layouts/PortalShell.jsx`, safe areas, 375/390px, three `manifest-*.webmanifest`, stale-app/update banner) | | | |
| Reports / exports / PDFs | | | |
| Copy (banned strings: "Invalid Form", "Submission Failed", "Missing Data") | | | |

### Risks and mitigations
- Data: (writes, backfills, double billing, lost text on failed submit)
- Access: (who could now see or do something new)
- Rollout: (runs on deploy? migration? cache/PWA reload needed? cron at month end?)
- Rollback: (is it safe to revert? does a migration need a downgrade?)

### Tests per role
- Parent: can / cannot ...
- Therapist: can / cannot ...
- Admin/CM: can / cannot ...
```

## Red flags (stop and rethink)

- Fix lands in one portal while the same API or component is used by another.
- Backend rule changed but one of the three booking/editing UIs still enforces the old rule client-side.
- New field returned by an API that parents or therapists can call (leak risk).
- A failure path that leaves partial state (e.g. empty slot created before booking fails).
- Notification sent per item in a loop (flood) or a deep link pointing to the wrong portal.
- Anything touching money or month-end without a test of the totals.
