---
title: "ADR-0001: Support hub access scopes (HR desk, Finance desk, clinical full)"
status: "Accepted"
date: "2026-05-30"
authors: "Engineering / Product"
tags: ["architecture", "rbac", "support", "hr", "finance"]
supersedes: ""
superseded_by: ""
---

# ADR-0001: Support hub access scopes (HR desk, Finance desk, clinical full)

## Status

**Accepted**

## Context

The admin **Support & incidents** hub (`/admin/support`) must serve different staff roles without exposing parent/therapist portals to org-wide queues. Ticket escalation is defined in `ticket_escalation_service.ESCALATION_MATRIX` (e.g. therapist-topic → Case Manager L1 → HR L2). Finance is L1 for `BILLING_PAYMENT` topics.

Prior implementations either hid HR/Finance tabs (missing module features) or showed misleading “own items only” banners while product expectation is **desk queues** aligned to escalation parties.

**Constraints:**

- Parents and therapists keep `/parent/support` and `/therapist/support`.
- Module features `tickets` / `incidents` on `hr_ops` and `billing` org modules gate nav via `effective_features_for_user`.
- Clinical incident **management** (status, assign, escalate) stays on `incident.read_sensitive`.
- Single source of truth: `backend/app/services/support_access_service.py`.

## Decision

Introduce explicit **support scopes** returned by `GET /api/v1/admin/support/capabilities`:

| Scope | Roles | Ticket queue | Incident list | Incident manage UI |
|-------|-------|--------------|---------------|-------------------|
| `full` | Super admin, clinical managers (`incident.read_sensitive` + `incidents` feature) | Module/case-scoped org queue | Case-scoped org queue | Yes |
| `hr_desk` | HR (`ticket.manage` + hr_ops features) | Therapist-topic + HR-category tickets | Org incidents (read); desk read via `can_access_incident_on_desk` | No (read-only detail) |
| `finance_desk` | Finance (`ticket.manage` + billing features) | Billing-topic/category + self-raised | Self-raised / desk read path | No |
| `own` | Other staff with `ticket.manage` only | `raised_by_user_id = me` | Reporter-only | No |
| `none` | Therapist, parent on admin routes | — | — | — |

**Ticket desk filters** live in `ticket_escalation_service.ticket_visible_to_hr_desk` and `ticket_visible_to_finance_desk`, applied in `ticket_list_service` and `support_history_service`.

**HR dashboard** lands on `/admin` (not `/admin/people`). **HR reports** export via `/api/v1/admin/hr-reports/{report_key}` (`hr_report.export` permission).

## Consequences

### Positive

- **POS-001**: HR and Finance see escalation-aligned queues without `incident.read_sensitive`.
- **POS-002**: Capabilities API prevents frontend tab drift (`AdminSupportHubPage` loads server flags).
- **POS-003**: Therapist → HR ticket flow is test-covered (create, list, close).
- **POS-004**: Handover documentation can reference one scope table and one service file.

### Negative

- **NEG-001**: HR incident desk is **read-only** for status/assign; clinical owners still need `incident.read_sensitive` for mutations.
- **NEG-002**: Three scope types increase branching in list/history services (must stay centralized).
- **NEG-003**: Finance desk does not yet auto-assign tickets to Finance users on create (assignment still via `assign_ticket` on create).

## Alternatives Considered

### Org-wide queue for all `ticket.manage`

- **ALT-001**: **Description**: Any staff with `ticket.manage` sees all tickets/incidents.
- **ALT-002**: **Rejection Reason**: Violates privacy and escalation ownership; Finance would see clinical tickets unrelated to billing.

### Own-scope only for HR and Finance

- **ALT-003**: **Description**: Only tickets/incidents the user raised.
- **ALT-004**: **Rejection Reason**: Contradicts escalation matrix; HR cannot act as L2 for therapist tickets.

### Grant HR `incident.read_sensitive`

- **ALT-005**: **Description**: HR gets full clinical incident management.
- **ALT-006**: **Rejection Reason**: Blurs HR ops vs clinical safeguarding workflows; broader PHI surface than required for desk triage.

## Implementation Notes

- **IMP-001**: After deploy, re-seed demo: `python3 -m app.seed.demo_seed` from `backend/` so HR/Finance `org_capability_grants` include `hr_ops` / `billing`.
- **IMP-002**: Verify with `hr@demo.com` / `finance@demo.com` / `therapist@demo.com` / `demo123` — Support hub tabs, therapist ticket visible to correct desk.
- **IMP-003**: Run `python3 -m pytest app/tests/test_support_access.py app/tests/test_hr_reports.py -q`.

## References

- **REF-001**: [docs/HANDOVER_SUPPORT_HR.md](../HANDOVER_SUPPORT_HR.md)
- **REF-002**: [docs/RBAC_SCOPE.md](../RBAC_SCOPE.md)
- **REF-003**: `backend/app/services/ticket_escalation_service.py` — `ESCALATION_MATRIX`
