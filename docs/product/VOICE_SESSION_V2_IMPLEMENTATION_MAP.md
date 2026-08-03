# Voice Session Log V2 — Implementation Map

_Audit before Phase 1 coding. Stitch references: [`docs/design/stitch/voice-session-log-v2/`](../../design/stitch/voice-session-log-v2/SCREEN_REFERENCE.md)._

## 1. Reuse (do not duplicate)

| Area | Files |
|------|-------|
| Voice UI shell | `VoiceSessionLogFlow.jsx`, `Voice*Screen.jsx`, `voice-session-log-stitch.css` |
| Recording | `useVoiceRecorder.js`, `voiceLogApi.js`, `voiceLogStore.js` |
| Structured draft | `structuredSessionEvidence.js`, `voiceExtractionMapper.js` |
| Submit adapter | `useSessionLogSubmit.js`, `SessionLogApplicationService` |
| Backend pipeline | `session_voice.py`, `voice_session_log_service.py`, `voice_transcription_service.py`, `session_log_extraction_service.py` |
| Schemas | `voice_session_log.py`, `structured_session_evidence.py` |
| Storage | `session_audio_recordings` table, `STORAGE_PROVIDER` |
| Parent read | `parentSessionLogDisplay.js`, `SessionLogReadOnly.jsx` |
| Design tokens | `forest-light-theme.css`, `docs/design/DESIGN.md` |

## 2. Modify (V2 alignment)

| File | Change |
|------|--------|
| `VoiceStoryDraftScreen.jsx` | Mobile accordions, review summary, match labels (no %), simplified challenges |
| `VoiceProcessingScreen.jsx` | Three honest stages, indeterminate progress, background continue |
| `VoiceSessionPreviewScreen.jsx` | Parent-safe sections from confirmed evidence only |
| `voice_session_log.py` | Extend schema: `session_insights`, `family_summary`, `therapist_review_metadata`, match labels |
| `session_log_extraction_service.py` | Clinical Language Engine prompt v2 |
| `voice_session_log_service.py` | Pipeline phases, insight aggregation hook |
| `config.py` / `feature_flags.py` | `ENABLE_VOICE_SESSION_V2`, clinical brain insight flags |
| `docs/design/DESIGN.md` | Canonical V2 direction |
| `VoiceFlowFooter.jsx` | **Done:** Preview + Submit only; draft saves on Preview |

## 3. New files (phased)

| Phase | Files |
|-------|-------|
| 2 | `clinical_language_engine_service.py`, `session_context_builder.py` |
| 4 | `session_clinical_insight_service.py`, `session_longitudinal_aggregator.py` |
| 6 | `session_analytics_event_service.py`, repository interfaces (`GoalRepository`, `StrategyRepository`) |
| Tests | `test_voice_session_v2_*.py`, E2E smoke updates |

## 4. Database migrations (additive)

- Extend `session_audio_recordings.extraction_json` schema (no column change if JSON-only).
- Optional: `session_analytics_events` table (Phase 6) — reuse `clinical_evidence_events` where possible first.
- Optional: `session_insight_feedback` for therapist AI feedback (Phase 4).
- **No** parallel session-log table.

## 5. API changes

| Endpoint | Change |
|----------|--------|
| `GET /session-voice/recordings/{id}` | Return V2 extraction shape + review counts |
| `POST /daily-logs` | Already accepts `structured_session_json` via SLA |
| New `GET /cases/{id}/sessions/{id}/clinical-insight` | Phase 4 — deterministic + cautious AI insight |
| New `POST /session-voice/recordings/{id}/insight-feedback` | Phase 4 |

## 6. Deprecate (after stability)

- `SubmitSessionLogForm.jsx` (already `@deprecated`)
- `voiceExtractionMapperLegacy.js`
- Duplicate save-draft UI (removed from top bar)
- Fake processing copy / match percentages in UI

## 7. Risks & rollback

| Risk | Mitigation |
|------|------------|
| Schema drift | Feature flag `ENABLE_VOICE_SESSION_V2`; adapter maps to existing `structured_session_json` |
| AI overreach | Layer 1 rules + banned words; insights from confirmed evidence only |
| Token cost | Compact context; explicit Send/Generate only |
| Rollback | Disable flag → existing V1 voice flow + legacy read adapter |

## 8. Architecture conflicts

- **None blocking:** V2 extends current canonical path (voice → structured JSON → SLA → DailyLog).
- **Insights tab Ask** is separate case-level feature; session Clinical Brain panel is session-scoped aggregation.
- Do not merge Stitch mock sidebar / fictional personas into `PortalShell`.

## Phase order

1. Design alignment + footer/topbar + processing honesty *(partial — footer done)*
2. Clinical Language Engine + V2 extraction schema
3. Review workflow (accordions, review summary, challenges simplification)
4. Clinical Brain insight rules + longitudinal aggregation
5. Family preview + submission gates
6. Analytics events + legacy deprecation
