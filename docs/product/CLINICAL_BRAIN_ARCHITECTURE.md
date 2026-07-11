# Clinical Brain Architecture

**Status:** ACTIVE — backend and evidence architecture for session logs and downstream intelligence.

## Design goal

> One session-log application service, one submission transaction, one confirmed evidence model, multiple derived views.

## Application service (thin entry point)

[`SessionLogApplicationService`](../../backend/app/services/session_log_application_service.py) coordinates existing domain services — **not** a god object or nine-service orchestrator.

| Operation | Responsibility |
|-----------|----------------|
| `prepare_draft()` | Repo context, optional voice extraction → draft shell |
| `save_draft()` | Persist `structured_session_json` only |
| `submit_log()` | Single DB transaction: log lifecycle + snapshot + relational evidence + derived prose |
| `resubmit_log()` | Same as submit for rejected logs |

Delegates to: `log_service`, `structured_session_log_service`, `clinical_evidence_service`, `voice_session_log_service`, `session_service`.

Extract sub-services only when logic duplicates across two+ call sites.

## Domain persistence

| Concept | Table / column |
|---------|----------------|
| Session | `sessions` |
| Source capture | `session_audio_recordings` |
| Draft / snapshot | `daily_logs.structured_session_json` |
| Confirmed goal evidence | `session_goal_entries` |
| Confirmed strategy use | `strategy_use_events` |
| Clinical suggestions | `goal_repository_items`, `strategy_repository_items`, `clinical_review_queue_items` |
| Time edit (last) | `sessions.actual_times_*`, `actual_times_edit_reason` |
| Time audit trail (Phase 3) | `session_time_audit_events` |

Do **not** store the entire clinical record only as JSON. JSON holds draft + submitted snapshot; relational rows hold confirmed evidence for reports and trends.

## SessionEvidenceProjection

Stable read contract for **both** legacy and engine report compilers:

[`session_evidence_projection.py`](../../backend/app/schemas/session_evidence_projection.py)

Built by `build_session_evidence_projection(db, log)` from relational rows + structured snapshot.

**Rule:** No new session-log feature writes directly to legacy `monthly_reports`-specific structures.

## SessionPreviewService

Derives therapist, CM, and parent-safe views from one record — never manually maintained separately.

## Voice pipeline (pre-submit)

```
POST /daily-logs/voice → session_audio_recordings
  → transcription → extraction_json
  → (poll) VoiceSessionLogExtraction.to_structured_session_evidence()
  → (submit) SessionLogApplicationService.submit_log()
```

Backend gated by `ENABLE_VOICE_SESSION_LOG`; frontend always shows manual path in same editor.

## Clinical brain layers (token economy)

| Layer | Use |
|-------|-----|
| 1 — SQL / rules | Validation, scoring, status gates, submit eligibility |
| 2 — Relational joins | History, lineage, goal/strategy mapping |
| 3 — Vector / keyword | Goal/strategy candidate search (keyword fallback today) |
| 4 — LLM | Transcription, extraction, narrative drafting — on explicit actions only |

## Review queues

**Canonical:** `clinical_review_queue_items` via `clinical_review_queue_service`.

**Duplicate (deprecated):** Admin tab via `clinical_brain_review_service` — migrate reads to unified queue (Phase 3).

## Reports convergence (deferred full migration)

Target flow:

```
SessionEvidenceProjection → monthly aggregation → AI narrative draft → therapist edit → CM approval → parent release
```

Legacy `monthly_reports` writes remain until engine adoption; both paths read projection first.

## Compatibility adapters

| Legacy | Adapter behaviour |
|--------|-------------------|
| `POST /therapist/session-logs` | Normalise → `submit_log()` with structured or prose→structured wrap |
| `PUT /session-evidence` | Convert to `resubmit_log()` with evidence→structured mapping |
| Prose-only historical logs | `legacyLogToStructuredSession` on frontend for edit |

Log adapter invocations for 30-day usage tracking before removal.

## Deletion gates

See [canonical-manifest.yml](./canonical-manifest.yml) — remove code/routes only when all applicable gates pass (zero imports, 30-day zero traffic, backfill verified, etc.).
