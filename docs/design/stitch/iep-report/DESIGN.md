---
name: Forest Light IEP Report
colors:
  surface: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  on-surface: '#1a1c1c'
  on-surface-variant: '#424845'
  outline: '#737875'
  outline-variant: '#c2c8c3'
  lush-forest: '#2d5a47'
  lush-mint: '#c3ecd7'
  secondary-container: '#c3ecd7'
parent: observation-report/forest_light_high_contrast/DESIGN.md
---

# IEP Report — Forest Light design tokens

IEP reuses the **Forest Light High Contrast** palette from the observation report module. Do not invent a separate color system.

**Global CSS:** `frontend/src/index.css` imports `forest-light-iep.css`  
**Route shell:** `IepReportRoute.jsx` wraps views in `.iep-workspace.forest-light`  
**Shared utilities:** `.clinical-shadow`, `.sticky-footer`, `.forest-gradient` (from observation theme)

## Typography & spacing

- Section labels: `text-sm font-bold uppercase font-mono text-outline`
- Cards: `rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-6 clinical-shadow`
- Touch targets: `min-h-[44px]` on all primary actions
- Mobile-first: single column builder; evidence rail `hidden lg:block`

## Measurement UI

Use `MeasurementCriteriaSelect` with enums from `clinicalMeasurementCriteria.js` — never 0–4 sliders in IEP or session logs when reports engine is active.
