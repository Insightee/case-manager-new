# InsighteCase Design System — Session Log & Clinical Workspace

**Status:** ACTIVE — extends [UI_CONTRACT.md](./UI_CONTRACT.md) for session logs and confirm-and-edit clinical surfaces.

## Principles

- Calm, trustworthy clinical workspace
- Forest-green primary system (`forest-light` theme)
- Warm neutral surfaces; strong spacing and typography
- **One primary action per stage**
- Minimal visual noise — section separators and narrative surfaces, not floating card walls
- Mobile-first responsive; desktop adds optional sticky context panel (same workflow)
- Neuro-affirming, parent-friendly language in previews
- Accessible: 44px touch targets, WCAG contrast on Forest Light tokens

## State colours

| Colour | Use |
|--------|-----|
| Green | Confirmed, active, helpful |
| Amber | Pending review, suggested, needs attention |
| Red | Errors and destructive actions only |

Do not use red for pending clinical decisions.

## Session log — five screens (canonical)

One flow for mobile and desktop. Reference implementation: `frontend/src/components/daily-logs/voice/`.

### Screen 1 — Ready

- Compact client/session header (case code, date, therapist, environment)
- Scheduled time; actual time if clocked
- Inline or modal time edit with reason
- **Primary:** Start voice note
- **Secondary:** Type instead
- Cancel mistaken session

### Screen 2 — Recording

- Large recording state + timer
- Prominent cue pill (recording prompts)
- Pause / finish
- Re-record only after stopping
- **No clinical fields while recording**

### Screen 3 — Processing

- Transcript / extraction in progress
- Clear retry and error states
- Therapist may leave and return
- No fake progress implying certainty

### Screen 4 — Draft review (mobile order)

1. Editable session story ("What happened today?")
2. Goals identified + evidence under each matched goal
3. Emerging goal suggestions (dismiss / send for CM review)
4. Strategies used today
5. Child response + challenges / strengths
6. System-generated therapist insights (read-only, collapsible)
7. Therapist reflection (private, editable)

**Do not** recreate old mandatory measurement chip walls.

Use chips for short controlled decisions; narrative blocks for story and reflection.

### Screen 5 — Preview

- Toggle: **Parent update** | **CM clinical record**
- Sticky footer: Save draft | Preview | Submit

## Persistent actions

- Save draft — optimistic local + API when session exists
- Preview — requires minimum story or confirmed goal
- Submit — blocked until AI-matched goals resolved

## CSS

- Voice flow: `voice-session-log-stitch.css` under `.vsl-stitch`
- Forest tokens: `forest-light-theme.css`
- Typography: [FOREST_LIGHT_TYPOGRAPHY.md](./FOREST_LIGHT_TYPOGRAPHY.md)

## Banned patterns

- Deep nested tabs for session log
- Left-side section navigation for therapist log
- Blank walls of chips
- Multiple competing primary buttons
- Technical AI jargon in therapist copy
- Recreating `SubmitSessionLogForm` under the recorder
- Legacy purple `clinical-ui` on therapist session surfaces

## Related

- [SESSION_LOG_V1.md](../product/SESSION_LOG_V1.md)
- [docs/design/stitch/voice-session-log/](../design/stitch/voice-session-log/) — stitch reference (superseded screen ref in legacy/)
