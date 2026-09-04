# CM Meetings — Role Capability Matrix

Source of truth for meetings/calendar behavior across portals. Update this doc when changing booking, notes, or calendar UX.

## Event types (do not conflate)

| Type | Data | Booking | Availability |
|------|------|---------|--------------|
| **Therapy session** | `TherapySession` / slots | Parent books therapist slots | Therapist `/users/{id}/availability` (syncs to `/therapist/slots` template) |
| **CM meeting** | `CaseManagerMeeting` | CM, admin, or therapist requests | Staff `/users/{id}/availability` |

Unified calendar feed: `GET /api/v1/calendar/events` (`event_type`: `cm_meeting`, `therapy_session`, …).

## Capability matrix

| Capability | Super Admin / Admin | Case Manager | Therapist | Parent |
|------------|---------------------|--------------|-----------|--------|
| View scoped meetings | Yes (team/global) | Yes (caseload) | Yes (assigned cases) | Yes (child) |
| Calendar week/month | Yes | Yes | Yes | List-first (calendar deferred) |
| Book CM meeting | Yes | Yes | Yes (request for own cases) | No |
| Set staff availability (meetings + sessions) | Own + override | Own | Own (`/therapist/meetings?availability=1`) | No |
| Google Calendar sync (availability) | Own | Own | Optional (same panel) | No |
| CM shared minutes / complete | Yes | Yes | No | No |
| Therapist private notes | No | No | Yes (own meetings) | No |
| Reschedule / cancel | Yes | Yes | Yes (participant) | No (contact CM) |
| Export CSV/Excel | Yes | Yes | Yes (scoped list) | No |
| Staff filter / admin queue | Yes | No | No | No |
| Home upcoming widget | Admin dashboard | CM home | Therapist dashboard | Deferred |

## Notes visibility (API)

| Field | CM / Admin | Therapist | Parent |
|-------|------------|-----------|--------|
| `notes_summary`, `notes_outcome`, actions | Yes | Hidden | Hidden (share deferred) |
| `therapist_notes` | Hidden | Yes (own) | Hidden |
| Legacy `notes_concerns`, `notes_follow_up`, `notes_action` | Yes | Hidden | Hidden (parent share deferred) |

## Surfaces

| Portal | Route | Component |
|--------|-------|-----------|
| Admin / CM | `/admin/meetings` | `CaseManagerMeetingsPage` |
| Therapist | `/therapist/meetings` | `CaseManagerMeetingsPage` (`portal="therapist"`) |
| Parent | `/parent/meetings` | `CaseManagerMeetingsPage` (`portal="parent"`) |

## Slot booking rules

1. Frontend: `BookMeetingModal` calls `GET /api/v1/calendar/availability` with intersected attendee IDs.
2. Therapist path: CM + booking therapist + parent (only if client invited).
3. Backend: `create_meeting` / `reschedule` reject times not in `free_slots` for attendees.
4. Configured availability: weekdays without saved rules are **closed** (not default open).
5. **One rule**: `StaffAvailabilityRule` is canonical; saves sync to `TherapistScheduleTemplate` and session materialization reads staff rules when a booking policy exists.
6. **Weekends**: off by default org-wide (`SCHEDULING_WEEKENDS_ENABLED=false`); when true, default templates include Sat/Sun until staff saves narrower hours.

## Deferred (next pass)

- Parent `share_with_parent` on shared minutes
- Parent calendar tab + dashboard upcoming panel
- Mobile nav Meetings for parent / therapist / CM bottom bars
- Move `CaseManagerMeetingsPage` out of `admin-portal/` into shared `components/meetings/`

## Agent skill

See [docs/skills/cross-portal-product-design/SKILL.md](../skills/cross-portal-product-design/SKILL.md) for the cross-portal implementation checklist.
