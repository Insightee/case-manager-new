# IEP Report — Stitch Screen Reference

**Design tokens:** [`DESIGN.md`](DESIGN.md) (Forest Light — shared with observation)

**Global CSS:** `frontend/src/index.css` imports `forest-light-iep.css`  
**Route shell:** `IepReportRoute.jsx` wraps all views in `.iep-workspace.forest-light`

---

## Non-negotiable implementation rule

When building or changing IEP UI:

1. Match observation report Forest Light patterns (`ObservationLandingPage`, `ObservationBuilderPage`).
2. Use `@theme` colors (`bg-surface-container-lowest`, `text-lush-forest`, …).
3. **Keep** InsighteCase app chrome: `CaseProfileShell` tabs, case header, portal routing.
4. **Wire API before showing controls** — no decorative Share/Export/Duplicate until endpoints exist.
5. Use unified `MeasurementCriteriaSelect` for goal criteria (not legacy sliders).

### Visual verification checklist (before merge)

- [ ] Hard refresh landing + builder URLs (`?tab=reports&section=iep`)
- [ ] Landing shows separate action buttons (Start / Import / Continue)
- [ ] Builder shows 5 numbered sections + goal cards with criteria selects
- [ ] Preview toggles clinical vs parent-safe modes
- [ ] Pending-changes panel uses inline return note (no `window.prompt`)
- [ ] `npm run build` passes

---

## Screen → React map

| Screen | React target |
|--------|--------------|
| Landing (status + start) | `IepLandingPage` |
| Builder (5 sections + goals) | `IepBuilderPage` + `IepGoalCard` / `IepStrategyLinker` |
| Goal create modal | `CreateGoalModal` (`reportType="iep"`) — Templates / Custom / AI tabs |
| Preview (clinical + parent) | `IepPreviewPage` |
| Admin pending queue | `IepPendingChangesPanel` (CM variant) |

---

## Route map

| URL | Component |
|-----|-----------|
| `?tab=reports&section=iep` | `IepLandingPage` |
| `?tab=reports&section=iep&view=builder` | `IepBuilderPage` |
| `?tab=reports&section=iep&view=preview` | `IepPreviewPage` |
| Admin: `?tab=iep` on case detail | `IepReportRoute` `variant="admin"` |

---

## API map

| UI region | Endpoint |
|-----------|----------|
| Landing status | `GET /cases/{id}/reports/iep/summary` |
| Start new | `POST /cases/{id}/reports/iep/start` |
| Import from observation | `POST /reports/{id}/iep/generate-draft` |
| Builder load | `GET /cases/{id}/reports/iep` |
| Section autosave | `PATCH /reports/{id}/sections/{key}` |
| Goals CRUD | `POST/PATCH/DELETE /reports/{id}/iep/goals` |
| Strategy link | `POST /reports/{id}/iep/goals/{gid}/strategies` |
| Pending changes | `GET /reports/{id}/iep/pending-changes` |
| Approve / return | `POST .../approve-changes`, `POST .../return-changes` |
| Mark achieved | `POST .../iep/goals/{gid}/mark-achieved` |
| Submit | `POST /reports/{id}/submit` |
| Preview | `GET /reports/{id}/preview?mode=clinical|parent` |
| AI suggestions | `POST /reports/{id}/iep/generate-suggestions` (gated) |
| Parent input | `POST /parent/cases/{id}/iep-inputs` |

---

## Button inventory (wired only)

| Screen | Control | API |
|--------|---------|-----|
| Landing | Start IEP | `POST .../start` |
| Landing | Import from observation | `POST .../generate-draft` |
| Builder | Add goal | `POST .../iep/goals` |
| Builder | Save draft | `PATCH sections` |
| Builder | Submit | `POST .../submit` |
| Builder | Preview | navigate preview |
| Pending (CM) | Approve / Return | approve-changes / return-changes |
| Parent portal | Share your input | `POST .../iep-inputs` |

**Deferred (no API):** Share link, Export PDF, Duplicate plan
