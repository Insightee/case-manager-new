---
name: cross-portal-product-design
description: Ensures InsighteCase features are designed and implemented across all user roles (admin, case manager, therapist, parent, finance, HR) with a single capability matrix—not admin-first patches. Use when building or changing meetings, calendar, scheduling, booking, notifications, RBAC-gated features, or any workflow that touches multiple portals.
---

# Cross-Portal Product Design (InsighteCase)

## When to use

Before designing or implementing any feature that appears in more than one portal, or when fixing "it only works for case managers."

## Non-negotiable rule

**One domain decision, many portal shells.** Never ship admin UI into therapist/parent routes without a portal-specific wrapper.

Banned patterns:
- Admin page component reused with growing `if (portal === …)` branches
- CM-only controls visible to therapists/parents
- Backend API unified but only admin home/dashboard wired
- Mobile nav missing routes that desktop sidebar has

## Mandatory workflow

### 1. Write the role matrix first (before code)

For the feature, fill the table in [docs/product/MEETINGS_ROLE_MATRIX.md](../product/MEETINGS_ROLE_MATRIX.md) (meetings) or create `docs/product/<feature>_ROLE_MATRIX.md`.

Also document:
- **Scope rule** (case_assignments, own records, team, global)
- **Mobile-first constraints** (thumb zone, ≤3 taps to primary action)
- **Connection before correction** copy (no "Invalid Form" / "Submission Failed")

### 2. Map surfaces (all must be listed)

| Surface | File/route pattern |
|---------|-------------------|
| Admin hub | `/admin/...` |
| CM home | `/admin/cm` |
| Therapist | `/therapist/...` |
| Parent | `/parent/...` |
| Mobile bottom nav | `PortalShell.jsx` `*_MOBILE_NAV` |
| Dashboard widget | `*DashboardPage.jsx`, `Upcoming*Panel` |
| Case detail tab | `AdminCase*Panel.jsx` |
| Notifications deep link | `notificationLinks.js` |
| API + RBAC | `backend/app/api/v1/` + permissions helpers |

If any row is N/A, write **N/A + reason** — never leave blank.

### 3. Architecture split

```
components/<domain>/
  <Domain>HubPage.jsx       # thin router by portal
  <Domain>CalendarView.jsx  # shared
  <Domain>ListView.jsx      # shared
  <Domain>AdminToolbar.jsx  # admin/CM only
  <Domain>AvailabilityPanel.jsx  # role-gated
```

Backend: one service (`*_service.py`), thin routes, scope via existing permission helpers.

### 4. Implementation checklist (copy per PR)

```
Cross-portal checklist:
- [ ] Role matrix doc updated
- [ ] All portals in matrix have route + nav entry (desktop + mobile)
- [ ] Dashboard/home widget if user needs discoverability
- [ ] RBAC tests per role that can/cannot act
- [ ] Deep links use portal-correct paths (not hardcoded /admin)
- [ ] No admin-only CSS classes on therapist/parent pages without wrapper
- [ ] Parent read-only paths cannot mutate via API (test 403)
```

### 5. Meetings & calendar reference

Two event types — do not merge UX without explicit decision:

| Type | Booking | Availability owner | Primary UI |
|------|---------|---------------------|------------|
| Therapy session | Parent + therapist slots | Therapist (`/therapist/slots`) | `/parent/book`, `/therapist/slots` |
| CM meeting | CM/admin/therapist request | Case manager (`/users/{id}/availability`) | `/admin/meetings`, `/therapist/meetings`, `/parent/meetings` |

Unified feed: `GET /api/v1/calendar/events` — filter by `event_type`.

Slot API for CM meetings: `GET /api/v1/calendar/availability` with intersected `user_ids` (CM + invited attendees). Do **not** use `/api/v1/booking/slots` for CM meetings.

Availability rule: once a user saves availability (`StaffBookingPolicy` exists), weekdays without rules are **closed**, not default 10–19.

### 6. Verification

```bash
./scripts/agent-pytest.sh app/tests/test_phase3_availability.py -k "configured or closed"
./scripts/agent-pytest.sh app/tests/test_admin_portal.py -k "meeting"
```

Manual: sign in as casemanager, therapist, parent — same meeting visible with correct actions; therapist book modal shows only CM-configured slots.
