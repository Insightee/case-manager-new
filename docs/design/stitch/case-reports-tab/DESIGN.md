# Case Reports Tab — Forest Light (Stitch)

**Project:** Therapy Map & Clinical Planner  
**Stitch project ID:** `2676660861211267049`

## Canonical screens

| Screen | Stitch screen ID | Implementation |
|--------|------------------|----------------|
| Client Case View (desktop) | `bd07d0c97e8b49d395f3a889a8e3d865` | `CaseReportsTab.jsx` + `case-reports-tab.css` |
| Mobile View | `a922c4b5331f4abd8f1939209a89c6b5` | Same component |
| Empty State | `af17897a468c45959e93200572371709` | Empty branch in `CaseReportsTab` |
| Overdue Alert | `9a660372c04f4f28aa14e12e5fc56824` | Attention card + timeline chip tones |

Reference assets: `reports-*/code.html` and `screen.png` in this folder.

## Design system

Use **Forest Light** tokens from `frontend/src/styles/forest-light-theme.css`.

| Token | Usage |
|-------|--------|
| `surface-container-lowest` | Cards, filter bar |
| `outline-variant` | Card borders |
| `primary-container` | Primary CTA, timeline nodes |
| `secondary` / `secondary-container` | Upcoming / active chips |
| `error` / `error-container` | Overdue attention, left accent |

Typography: Manrope headlines, Inter body, JetBrains Mono uppercase labels (see `FOREST_LIGHT_TYPOGRAPHY.md`).

## Section order (do not reorder)

1. **Header** — title "Reports", subtitle, **+ Add / Create Report** dropdown
2. **Needs Your Attention** — compact cards (max 5 visible)
3. **Current Report Lifecycle** — 5 status cards (Observation, IEP, Monthly, Progress, CM Notes)
4. **Filters** — search, month, year, type, status (no case filter)
5. **Report History** — month-grouped vertical timeline

### Mobile

1. Header (compact + floating New Draft optional)
2. Needs Attention (vertical stack)
3. **Working Progress** hero when active monthly draft exists
4. Lifecycle strip (horizontal scroll)
5. Filters (bottom sheet)
6. Report History timeline

## Forbidden on this surface

- Multi-case dashboard metric cards
- "All Cases" filter
- `TherapistReportsHomeView` embedded in case tab
- `ClinicalMetricCard`, caseload pipeline UI
- Inline report editors or creation forms
- "Import Archive" (Stitch mock only — not implemented)

## API

`GET /api/v1/cases/{case_id}/reports/summary` — single source for tab data. CTAs use `target_url` from response.
