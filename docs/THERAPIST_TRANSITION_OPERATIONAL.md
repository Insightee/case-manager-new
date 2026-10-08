# Therapist handover — operational access (cross-portal)

During a **SCHEDULED** or **ACTIVE** therapist transition, structural case changes stay locked (billing, reassignment, day type, second transition, pause/close requests, hard delete). **Operational** work continues for the outgoing and incoming therapists within scoped booking windows.

## Booking windows (all APIs)

| Role | May book session dates |
|------|-------------------------|
| Outgoing therapist | Through the **last** handover day (inclusive) |
| Incoming therapist | From the **first** handover day onward |
| Anyone else | Blocked |

Enforced on:

- `POST /api/v1/scheduling/slots/{id}/book` and cancel (cancel always allowed for slot owner)
- `POST /api/v1/slots/{id}/book` (admin schedule modal)
- `POST /api/v1/booking/appointments` (parent)
- `POST /api/v1/scheduling/assign-recurring` (date range check)

`GET /api/v1/booking/availability` accepts optional `case_id` to hide slots outside the handover window.

Active transition payload (`GET …/transitions/active`) includes `booking_policy` and flags for outgoing bookings after the last handover day (CM visibility; not auto-cancelled).

## Portals

| Portal | Primary surfaces | UX |
|--------|------------------|-----|
| Therapist | `SlotEditSheet`, case cards (“Under transition”), session logs | Handover banner + server error normalization |
| Parent | `ParentBookSessionForm` | Handover hint; availability filtered by `case_id` |
| Admin / CM | `AdminCaseDetailPage`, `AdminScheduleSessionModal`, pipeline “In transition” | Updated alert copy; schedule modal uses same availability rules |

Shared copy: `frontend/src/lib/therapistTransitionBooking.js`.

## Payouts

Dual active assignments during handover no longer emit `ASSIGNMENT_OVERLAP` when they match the open transition pair; pay follows the delivering therapist on the session.
