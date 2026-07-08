# Case Overview — Stitch Screen Reference

Project: **Modern Therapist Case Dashboard** (`2951427195113771286`)

## Screens

| Screen | ID | UI target |
|--------|-----|-----------|
| Overview — Case Workspace (Desktop) — Updated Profile & Goals | `85b3dfc86c594ba89de9c7586711c8ee` | `TherapistCaseOverviewDashboard.jsx` (desktop two-column) |
| Overview — Case Workspace (Mobile) — Card Layout | `c27371d3fec9474bbb68b59ed32b888a` | Same component (mobile stack) |

## Implementation files

| File | Role |
|------|------|
| `frontend/src/components/clinical/therapist/TherapistCaseOverviewDashboard.jsx` | Layout + sections |
| `frontend/src/components/clinical/therapist/CaseOverviewSummaryCard.jsx` | Forest summary editor |
| `frontend/src/lib/caseOverviewCompose.js` | Data composition (existing APIs) |
| `frontend/src/styles/case-overview-v2.css` | Forest Light styles (`cov-*`) |
| `frontend/src/styles/forest-light-theme.css` | Shared design tokens |

## Parent shell

Rendered inside `CaseProfileShell` with `forest-light` class. Tabs: Overview, Reports, Goals, Logs, Insights, Documents.

## Design doc

See [DESIGN.md](./DESIGN.md) for tokens, layout, and forbidden patterns.
