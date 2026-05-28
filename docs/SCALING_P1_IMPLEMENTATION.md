# Scaling P1 Implementation

## Scope
- Keep single FastAPI + React/Vite architecture.
- Preserve current APIs, permissions, and workflows.
- Reduce API chatter and improve resilience for unstable mobile connectivity.

## Phase Gate Rules
- One phase at a time.
- Exit criteria per phase:
  - build passes,
  - targeted tests pass,
  - existing workflows manually verified,
  - API compatibility preserved.

## API Budget (P1)
| Module | Read strategy | Write strategy | Refresh policy |
|---|---|---|---|
| App usage | Local counters + queued chunks | Batched `/auth/activity/batch` | logout/pagehide/boot retry/15m |
| Schedules | SWR cache (today + next 7d) | Mutations invalidate keys | login/day-change/mutation/manual refresh |
| Reports/IEP | Local draft first | Debounced server save | explicit final approve/publish |
| Session logs | Local draft + pending replay | Submit/fix with retry-safe queue | replay on app boot/online |
| Notifications | Indexed reads + filtered views | mark-read writes | avoid broad polling loops |

## No Silent Data Loss Guarantees
- Preserve local drafts.
- Preserve unsynced usage chunks.
- Preserve unsynced upload queue.
- Preserve pending scheduling/session-log actions.
- Retry on boot/foreground and surface `Retry pending`.

## Signed Upload Pathway
- Backend-authorized signed URL only.
- Short-lived tokenized upload intent.
- Mandatory finalize call for metadata registration.
- Fallback to backend proxy upload remains available.

## Lightweight Observability
- Frontend: request counters, failures, slow requests, cache hit/miss counters.
- Backend: request id middleware logs method/path/status/duration and slow endpoints.
- Sync reliability logs: usage batch retries, autosave failures, upload finalize failures.

## Verification Matrix
- Therapist: Open Slots, Book Recurring, Leave mark, Session logs, Reports.
- Admin: dashboards, support, reports, usage summary.
- Parent: reports and schedule remain unaffected.
- Security: attachment scope checks and ownership validations.
