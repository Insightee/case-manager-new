> **STATUS: SUPERSEDED** — retained only for historical and migration context. Do not use this document for new implementation.

# Voice-first session log — Stitch screen reference

Design source: user-provided Stitch HTML mockups (Forest Light / Manrope tokens).

| App step | Mobile mockup | Desktop mockup |
| -------- | ------------- | -------------- |
| Ready to record | `session_log_ready_to_record/code.html` | `session_log_ready_to_record_desktop/code.html` |
| Recording | `session_log_recording_state/code.html` | `session_log_recording_state_desktop/code.html` |
| Processing | `session_log_processing_state/code.html` | `session_log_processing_state_desktop/code.html` |
| Draft / goals | `session_log_draft_review_goals/code.html` + `session_log_expandable_goal_selection/code.html` | Responsive breakpoints in `voice-session-log-stitch.css` |
| Preview / submit | Family preview bullets + sticky footer | Clinical vs parent tabs in `VoiceSessionPreviewScreen.jsx` |

## Frontend implementation

- Orchestrator: `frontend/src/components/daily-logs/voice/VoiceSessionLogFlow.jsx`
- Styles: `frontend/src/components/daily-logs/voice/voice-session-log-stitch.css`
- Canonical state: `frontend/src/lib/structuredSessionEvidence.js`

## Production safety

Voice flow is gated by `VITE_ENABLE_VOICE_SESSION_LOG=true` and `VITE_GOALS_STRATEGIES_ENGINE_V2=true`. When off, `SubmitSessionLogForm` renders unchanged.
