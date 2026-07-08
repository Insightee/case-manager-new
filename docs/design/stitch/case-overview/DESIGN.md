# Case Overview — Forest Light (Stitch)

**Project:** Modern Therapist Case Dashboard  
**Stitch project ID:** `2951427195113771286`

## Canonical screens

| Screen | Stitch screen ID | Implementation |
|--------|------------------|----------------|
| Overview — Desktop (Profile & Goals) | `85b3dfc86c594ba89de9c7586711c8ee` | `TherapistCaseOverviewDashboard.jsx` + `case-overview-v2.css` |
| Overview — Mobile (Card layout) | `c27371d3fec9474bbb68b59ed32b888a` | Same component (mobile-first) |

Reference HTML (local):

- `overview_case_workspace_desktop_updated_profile_goals/code.html`
- `overview_case_workspace_mobile_card_layout/code.html`

## Design system

Use **Forest Light** tokens from `frontend/src/styles/forest-light-theme.css`.

| Token | Value | Usage |
|-------|-------|--------|
| `surface` | `#f9f9f9` | Page background (via shell) |
| `surface-container-lowest` | `#ffffff` | Cards |
| `surface-container-low` | `#f3f3f4` | Inset rows (pending, goals, team) |
| `outline-variant` | `#c2c8c3` | Card borders |
| `secondary` | `#416656` | Section icons |
| `secondary-container` | `#c3ecd7` | Status pill, interest chips |
| `primary-fixed` | `#d3e7dd` | Avatar background |
| `primary-container` | `#0e1f19` | Primary buttons |
| `error` / `error-container` | `#ba1a1a` / `#ffdad6` | Urgent pending (session log) |

Typography (see `docs/design/FOREST_LIGHT_TYPOGRAPHY.md`):

- **Headlines:** Manrope (`--font-headline`) — client name, page titles
- **Body / values:** Inter (`--font-body`) — KV values, summaries, list text, buttons
- **Section eyebrows only:** JetBrains Mono (`--font-mono`) — `cov-card__title` uppercase labels; not body copy

## Layout

### Mobile (default)

Single column. Case identity (name, status, case code) lives in `CaseProfileShell` / `ClinicalCaseHeader` above tabs — do not duplicate a second name header inside overview.

Section order inside overview:

1. Profile snapshot (KV rows: age, client since, therapist started, setting)
2. Overview summary
3. Pending work
4. Strengths & interests (one combined card)
5. Support context
6. Concerns / support needs
7. Current goals
8. Care team
9. Missing information

### Desktop (≥900px)

Two columns:

- **Main (~68%):** snapshot, summary, goals, strengths | interests (2-col), support context, support needs
- **Rail (~32%, sticky):** pending work, care team, missing information

## Section patterns (match Stitch)

- **Card:** white, `1px` `outline-variant` border, `16px` radius (mobile) / `16px+` padding desktop
- **Section head:** Material icon + uppercase mono label
- **Pending row:** soft inset box; urgent = error-container tint; action = underlined mono link (not pill button)
- **Goals:** inset row + vertical black bar (no progress % unless real data exists)
- **Care team:** role left, name right, inset row
- **Missing info:** `error_outline` icon + muted text

## Forbidden on this surface

Do **not** use on Case Overview:

- `ClinicalCard`, `ClinicalMetricCard`, `ClinicalProgressBar`, `ClinicalStatusBadge`, `ClinicalGuidanceCard`
- Purple clinical tokens (`--clinical-purple`, `#5b21b6`)
- Metric grids, fake progress percentages, dashboard stat chips
- `clinical-components.css` layout primitives inside `.cov-page`

Use:

- `cov-*` classes in `case-overview-v2.css`
- `CaseOverviewSummaryCard.jsx` for editable summary
- `composeCaseOverview.js` for read-only data (no new schema)

## Data

Read-only composition only — see mapping block in `frontend/src/lib/caseOverviewCompose.js`.

## Verification

- [ ] Cards use Forest borders/chips, not purple clinical cards
- [ ] Pending work uses Stitch row + underline actions
- [ ] Status is `secondary-container` pill, not blue `ClinicalStatusBadge`
- [ ] Mobile section order matches spec above
- [ ] Desktop has sticky right rail
- [ ] `npm run build` passes
