# Voice Session Log — Deprecation & Scrap-Later Tracker

Companion to the Voice-First Session Log V1 rollout. **Canonical docs:** [docs/product/SESSION_LOG_V1.md](./product/SESSION_LOG_V1.md), [canonical-manifest.yml](./product/canonical-manifest.yml).

As of Voice-First V1 the confirm-and-edit flow (`VoiceSessionLogFlow`) is the **only** session-log editor
on therapist routes (logs page, case detail, edit/resubmit). "Type instead"
opens the same structured draft — there is no separate typed form anymore.

Flags: the frontend flag gate is removed (`isVoiceSessionLogActive()` always
returns true); `enable_voice_session_log` (backend) still gates the
upload/transcription pipeline — when off, the flow degrades to manual entry in
the structured draft.

## 0. Deprecated in Voice-First V1 (files retained one release, no longer imported by therapist routes)

| Item | Location | Replacement |
|---|---|---|
| `SubmitSessionLogForm` + its evidence-panel tree | `frontend/src/components/daily-logs/SubmitSessionLogForm.jsx` | `VoiceSessionLogFlow` structured draft (voice or manual entry) |
| `SessionLogGoalTracker.jsx` | `frontend/src/components/daily-logs/` | Goal confirm/reject cards in the draft screen |
| `SessionLogAiAssist.jsx` | `frontend/src/components/clinical/session-log/` | Full extraction pipeline |
| `voiceExtractionMapperLegacy.js` | `frontend/src/lib/` | `voiceExtractionMapper.js` structured-session mapping |

Admin/CM read-only surfaces are unaffected. Edit/resubmit of legacy prose-only
logs opens the structured draft via `legacyLogToStructuredSession` (prose lands
in story/summaries; no fabricated evidence).

## 1. Likely redundant once voice is stable (remove only after pilot data)

| Item | Location | Why redundant | Removal condition |
|---|---|---|---|
| Legacy `FIELDS` textarea array (7 mandatory prose boxes) | `frontend/src/components/daily-logs/SubmitSessionLogForm.jsx` | Extraction prefills the same DailyLog fields; review screen replaces manual prose entry | Voice+v2 adoption >80% of new logs for a full month |
| `SessionLogGoalTracker.jsx` (legacy `STRUCTURED_SESSION_EVIDENCE` tracker) | `frontend/src/components/daily-logs/` | Superseded by v2 evidence panel, which the voice flow prefills | v2 engine flag default-on everywhere |
| `SessionLogAiAssist.jsx` ("improve my note" helper) | `frontend/src/components/clinical/session-log/` | Superseded by full extraction pipeline | Voice flow GA |
| Manual parent-note-from-scratch writing as the default path | `SubmitSessionLogForm.jsx` parent notes field | `parent_note_draft` from extraction prefills it (editable, "don't share" clears) | Parent-note edit rate from pilot metrics is acceptable |
| Schema-v1 evidence **write** path | `backend/app/services/clinical_evidence_service.py` (`_payload_is_v2` branch) | All new saves are v2; v1 remains read-only for history | No v1 writes observed for 90 days |
| Duplicate summary fields (`session_notes` vs `activities_done` overlap) | `backend/app/models/daily_log.py` | Extraction populates a single canonical summary; report compilers read both today | Report compilers updated to a single source field |
| Repeated manual domain/environment selection in the log form | v2 evidence panel | Inherited from goal card + session context | Voice flow GA |

## 2. Keep as fallback / secondary actions (do not remove)

- Manual entry — "Type instead" opens the same structured draft with an empty session (story + manual goal add).
- Manual goal selection and manual strategy selection/search.
- Manual edits to every generated section (extraction output is always editable).
- Manual parent note; evidence upload; internal note.
- Forgot-session workflow, time correction, duplicate-session prevention.
- Incident reporting (voice never auto-creates incidents; keyword rules only prompt).
- Historical log display and audit history.

## 3. Must never be removed

- Attendance/session timer as the source of truth for session duration
  (`backend/app/services/session_service.py`, `log_service.py`). Recording timer
  measures audio length only.
- 24h edit window, approval status, and visibility rules on `DailyLog`.
- `activities_done` population — hard requirement in `log_service.create_daily_log`
  and consumed by `report_compile_service`.
- Goal/strategy candidate review lifecycle (`goal_repository_service`) — voice
  candidates enter the same CM queue; nothing auto-enters the org pool.
- Parent visibility controls and internal/parent note separation.
- IEP goal card IDs, strategy IDs, session/case relationships, audit events.
- Approved report immutability and monthly/progress report field dependencies.

## 4. Schema notes

- V1 adds exactly one table: `session_audio_recordings`
  (migration `v0i1c2e3a4b5`). `DailyLog` is untouched.
- No destructive schema changes in V1. Deprecated fields are marked with code
  comments only; drops require a separate reviewed migration after pilot.
- Raw audio retention: `voice_audio_retention_days` (default 30; 0 = keep).
  Transcript + approved log are the durable record.

## 5. Decision log

| Date | Decision |
|---|---|
| 2026-07-11 | V1 scoped: voice = prefill layer; interpretation engine + report integration cut (already exist); pgvector deferred; FastAPI BackgroundTasks instead of new queue infra. |
