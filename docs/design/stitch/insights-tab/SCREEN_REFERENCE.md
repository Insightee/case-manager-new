# Insights Tab — Stitch Screen Reference

Project: **strategies insights tab -case** (`13923449322222839045`)

| Screen | ID | UI target |
|--------|-----|-----------|
| Insights - Mobile Therapist Workspace with Prompting | `2f7f755161ed4e38beb5de0e900af9cd` | Mobile stacked section order |
| Insights - Therapist Support Workspace with Prompting | `4dd625bee21c41e48c5733a2c6ed5445` | Desktop grid layout |

Local mirrors (already downloaded, no `curl` needed):
- `~/Downloads/final strategaies/insights_mobile_therapist_workspace_with_prompting/code.html` + `screen.png`
- `~/Downloads/final strategaies/insights_therapist_support_workspace_with_prompting/code.html` + `screen.png`
- `~/Downloads/final strategaies/forest_light_high_contrast/DESIGN.md` (token reference)

Implementation uses Forest Light tokens (`frontend/src/styles/forest-light-theme.css`) and a new `ci-*` class
prefix (`frontend/src/styles/case-insights-v2.css`) — not raw Stitch Tailwind HTML, consistent with
`docs/design/stitch/goals-strategies-engine/SCREEN_REFERENCE.md` and `.cursor/rules/05-forest-therapist-ui.mdc`.

## Section order (desktop and mobile)

1. Child Snapshot
2. IEP Goal Progress (with nested Strategy Response accordion per goal)
3. Next Session Focus
4. Collaborative Inputs
5. Session Log Insights & Evidence
6. Suggested Goals & Strategies
7. Bottom Actions (sticky footer on mobile, inline row on desktop)

See `DESIGN.md` in this folder for status vocabulary, banned words, and the insight object shape.
