# Voice Session Log V2 — Stitch Screen Reference

Project: **Insighte Therapist Portal: Voice-First Session Log** (`15253599852022851971`)

Stitch MCP is configured in [`.cursor/mcp.json`](../../../../.cursor/mcp.json). Reload Cursor MCP if the `stitch` server does not appear in the tool list.

Download with Stitch MCP (`get_screen`) or:

```bash
export STITCH_API_KEY="your-key"
curl -sS -X POST "https://stitch.googleapis.com/mcp" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $STITCH_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_screen","arguments":{"projectId":"15253599852022851971","screenId":"<id>"}}}'
```

Then download `htmlCode.downloadUrl` and `screenshot.downloadUrl` with the same API key header.

| Screen | ID | Folder | UI target |
|--------|-----|--------|-----------|
| Session Log - Updated Review Flow (Mobile) | `2d8e1fd2587546439da751f88e808a40` | `session-log-updated-review-mobile/` | `VoiceStoryDraftScreen` (mobile accordions) |
| Session Log - Updated AI Interpretation (Desktop) | `cebb02c6f469401dbe2235abab889f49` | `session-log-updated-ai-interpretation-desktop/` | Primary interpretation reference |
| Session Log - AI Interpretation (Desktop) | `9907bb6abe80423da1a6513d55ef9a50` | `session-log-ai-interpretation-desktop/` | Clinical Brain panel reference |
| Session Log - AI Interpretation (Mobile) | `9f96d411b2c6410b927acee7bb9f6f8f` | `session-log-ai-interpretation-mobile/` | Mobile interpretation layout |
| Session Log - Parent Preview (Mobile) | `bbc4dfd8108d40d695a4c85793bed355` | `session-log-parent-preview-mobile/` | `VoiceSessionPreviewScreen` |
| Session Log - Voice Processing (Desktop) | `7dd2aefcac0745f386016c8a8b7197aa` | `session-log-voice-processing-desktop/` | `VoiceProcessingScreen` |
| Session Log - Parent Preview (Desktop) | `7899a73214b3425faf79bcb6af2bfd33` | `session-log-parent-preview-desktop/` | Preview desktop layout |
| Session Log - Voice Processing (Mobile) | `b7bab49d9a58431690efec807a2fb9c2` | `session-log-voice-processing-mobile/` | Processing mobile layout |
| Design System | `asset-stub-assets_0c0b7dc099f24654b7747522757b1117` | — | See `DESIGN.md` (tokens from user export) |

## Implementation files (canonical — do not copy Stitch HTML)

| File | Role |
|------|------|
| `frontend/src/components/daily-logs/voice/VoiceSessionLogFlow.jsx` | State machine orchestrator |
| `frontend/src/components/daily-logs/voice/VoiceStoryDraftScreen.jsx` | Interpretation-ready review |
| `frontend/src/components/daily-logs/voice/VoiceSessionPreviewScreen.jsx` | Family preview |
| `frontend/src/components/daily-logs/voice/VoiceProcessingScreen.jsx` | Honest processing stages |
| `frontend/src/components/daily-logs/voice/voice-session-log-stitch.css` | Forest Light `vsl-stitch` tokens |
| `backend/app/api/v1/session_voice.py` | Upload / status / retry |
| `backend/app/services/voice_session_log_service.py` | Pipeline orchestration |
| `backend/app/schemas/voice_session_log.py` | Extraction schema |

See [DESIGN.md](./DESIGN.md) for Forest Light tokens. Visual references only — no fictional brands, sidebars, or mock personas in production UI.
