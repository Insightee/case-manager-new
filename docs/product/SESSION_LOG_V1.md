# Session Log V1 — Voice-First Clinical Confirmation

**Status:** ACTIVE — canonical therapist session-log specification.

## Editor

**Canonical UI:** [`VoiceSessionLogFlow`](../../frontend/src/components/daily-logs/voice/VoiceSessionLogFlow.jsx) on all therapist routes (`/therapist/logs`, case detail logs tab, edit/resubmit).

**Deprecated:** `SubmitSessionLogForm` and `clinical/session-log/*` tree — zero active imports; retained one release for reference.

## Source-of-truth hierarchy

### Before submission (draft)

| Layer | Canonical? | Notes |
|-------|------------|-------|
| `structured_session_json` | **Yes** | Editable draft on `daily_logs` |
| `session_audio_recordings` | Supporting | Audio, transcript, extraction — not clinical truth |
| Therapist-edited source note | In JSON (`todays_story`) | May differ from transcript |
| Prose columns | **No** | Do not edit independently during draft |

### After submission

| Layer | Canonical? | Notes |
|-------|------------|-------|
| `daily_logs` lifecycle | **Yes** | approval_status, submitted_at, attendance |
| `session_goal_entries` | **Yes** | Only `confirmed` / `edited_and_confirmed` goals |
| `strategy_use_events` | **Yes** | Only strategies **used today** and confirmed |
| `structured_session_json` | **Yes** | Submitted snapshot |
| Prose columns | Projection | Derived via `to_daily_log_fields()` |

### Reporting

| Layer | Canonical? |
|-------|------------|
| Relational evidence + metadata | **Yes** |
| `SessionEvidenceProjection` | **Yes** — stable read contract |
| Prose fields | Compatibility fallback |

### Audit

Audio/transcript/source note = supporting source, not clinical truth.

## Goal match states (IEP goals)

| State | Code alias (legacy) | Creates `session_goal_entry`? |
|-------|---------------------|-------------------------------|
| `suggested` | `pending` | No |
| `confirmed` | `confirmed` | **Yes** |
| `rejected` | `rejected` | No |
| `edited_and_confirmed` | `changed` | **Yes** |

Submit rejected if any IEP-matched goal (`match_type` ≠ `new_observation`) remains `suggested`/`pending`.

## Emerging goal states

| State | Meaning |
|-------|---------|
| `suggested` | AI pattern, not on active IEP |
| `dismissed_by_therapist` | Therapist dismissed |
| `accepted_for_review` | Therapist chose to send |
| `pending_cm_review` | In CM queue |
| `approved_case_goal` | CM approved → case plan |
| `merged_with_existing_goal` | CM linked to existing |
| `kept_as_observation` | Documented only |
| `rejected_by_cm` | CM declined |

Emerging observations **never** auto-create active IEP goals or `session_goal_entries`.

## Strategy categories

| Category | Creates `strategy_use_event`? |
|----------|-------------------------------|
| **Used today** (evidenced + confirmed) | **Yes** |
| **Active case strategy** (plan context) | No |
| **Recommended** (next session suggestion) | No |
| **Emerging/custom** (not in org repo) | Yes if confirmed used; may also create CM candidate |

## Insight and note types

| Type | Editable | Parent-facing | Persisted as truth? |
|------|----------|---------------|---------------------|
| Session story | Yes | Excerpt | Yes on submit |
| Therapist reflection | Yes, private | Never | Yes (`therapist_reflection`) |
| System therapist insights | Read-only | Never | **No** — derived at render |
| CM review signals | System/rules | CM only | Queue items |

## Backend write path

All submission via [`SessionLogApplicationService`](../../backend/app/services/session_log_application_service.py):

- `prepare_draft()` — load context + optional extraction
- `save_draft()` — JSON only, no relational evidence
- `submit_log()` — single transaction: lifecycle + snapshot + relational + prose
- `resubmit_log()` — rejected logs

**Deprecated routes:**

- `POST /api/v1/therapist/session-logs` — compatibility adapter → `submit_log()`
- `PUT /api/v1/daily-logs/{id}/session-evidence` — converts to resubmit; no new consumers

## Session context (header)

Client, case, therapist, date, scheduled vs actual times, environment, service type, edited-time reason, duration.

## Source capture

Audio (7-day retention), transcript, therapist-edited note, re-record, processing/retry, extraction version.

## Canonical information captured

Session story, goals + evidence, strategies used, child response, participation/support where evidenced, strengths, challenges, recommended next steps (non-binding), emerging suggestions, therapist reflection.
