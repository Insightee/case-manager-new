# Observation Report — Stitch Screen Reference

**Design tokens:** [`DESIGN.md`](DESIGN.md) (Forest Light High Contrast)

**Global CSS:** `frontend/src/index.css` imports `forest-light-observation.css`  
**Tailwind tokens:** `frontend/src/styles/forest-light-theme.css` (`@theme`)  
**Section components:** `frontend/src/components/reports-engine/observation/stitch/ObservationStitchBlocks.jsx`  
**Route shell:** `ObservationReportRoute.jsx` wraps all views in `.observation-workspace.forest-light`

---

## Non-negotiable implementation rule

When building or changing observation UI:

1. Open the matching `code.html` in this folder **first**.
2. Copy **Tailwind `className` strings verbatim** from `code.html` into React — do not invent new CSS namespaces (`ob-*`, `fl-ob-*`, etc.).
3. Use `@theme` colors from `forest-light-theme.css` (`bg-surface-container-lowest`, `text-lush-forest`, …).
4. Use utility classes from `forest-light-observation.css` only for: `.clinical-shadow`, `.ai-suggestion`, `.sticky-footer`, `.forest-gradient`, `.live-sync-dot`.
5. **Keep** InsighteCase app chrome: `CaseProfileShell` tabs, case header, portal routing.
6. **Replace only** the inner workspace (builder blocks, goals, strategies, evidence, preview document).

### Visual verification checklist (before merge)

- [ ] Hard refresh local (`Cmd+Shift+R`) on landing + builder URLs
- [ ] DevTools → computed styles on a card: `background-color: rgb(255,255,255)`, `border-radius` present
- [ ] Landing actions show as **separate** buttons (not concatenated text)
- [ ] Compare builder to `observation_report_comprehensive_clinical_workspace/screen.png`
- [ ] Compare preview to `observation_report_official_print_view_manan_sarda/screen.png`
- [ ] `npm run build` && `grep lush-forest frontend/dist/assets/*.css` returns matches

If the result does not visually match the PNG, stop and realign — do not ship an improvised layout.

---

## Screen → React map

| Screen folder | PNG | React target |
|---------------|-----|--------------|
| `observation_report_comprehensive_clinical_workspace/` | `screen.png` | `ObservationBuilderPage` + `ObservationStitchBlocks` |
| `observation_report_mobile_workspace/` | `screen.png` | Tailwind responsive classes (`md:`, `lg:`) on same components |
| `observation_report_mobile_ira_k./` | `screen.png` | `StitchWorkspaceSubhead` |
| `observation_report_clinical_insights_visualization/` | `screen.png` | `StitchEvidenceInsights` |
| `observation_report_official_print_view_manan_sarda/` | `screen.png` | `ObservationPreviewPage` |
| `observation_report_mobile_print_view_manan_sarda/` | `screen.png` | Preview responsive + print |

**Landing (status + start):** Forest Light card + progress bar. Component: `ObservationLandingPage`.

---

## Route map

| URL | Component |
|-----|-----------|
| `?tab=reports&section=observation` | `ObservationLandingPage` |
| `?tab=reports&section=observation&view=builder` | `ObservationBuilderPage` |
| `?tab=reports&section=observation&view=preview` | `ObservationPreviewPage` |

---

## API map

| UI region | Endpoint |
|-----------|----------|
| Landing status | `GET /cases/{id}/reports/observation/summary` |
| Start new | `POST /cases/{id}/reports/observation/start` |
| Builder load | `GET /cases/{id}/reports/observation` |
| Section autosave | `PATCH /reports/{id}/sections/{key}` |
| Submit | `POST /reports/{id}/submit` |
| Preview | `GET /reports/{id}/preview` |
| Session insights + AI chip suggestions | `POST /reports/{id}/observation/generate-insights` → `suggested_tiles` |
| Goal candidates | `GET /reports/{id}/observation/candidates` → `goals`, `suggested_goals` |
| Strategy candidates + AI matches | `GET .../candidates`, `GET .../strategy-matches?q=` |
| Evidence drive | Links to `?tab=documents`; stats from `GET /reports/{id}/evidence-summary` |

---

## Block checklist (builder)

Match comprehensive workspace HTML section order:

1. Child snapshot + case summary (`StitchChildSnapshot`)
2. 2×2 attribute tiles (`StitchChipPanel` × 4)
3. Evidence & AI Insights + Evidence Drive (`StitchEvidenceInsights`)
4. Environments Workspace (`StitchEnvironmentsSection`)
5. Suggested Goals (`StitchGoalsSection`)
6. Strategies Workspace (`StitchStrategiesSection`)
7. Stakeholder Inputs (`StitchStakeholderInputs`)
8. Right rail: InsighteAI Assistant (`StitchBuilderRail`) — **collapsed by default**; toggle via header button in `StitchWorkspaceSubhead`. When open, rail is sticky with scrollable “Still needed” list; when closed, builder uses full hub width (`ob-builder-layout--expanded`). Reuse this pattern for monthly/progress builders.
9. Sticky footer (`StitchBuilderFooter`)

App-specific extensions (same card Tailwind pattern): Clinical Domains, Clinical Summary & IEP Recommendations.
