# Clinical UI Contract (mandatory)

**Problem:** Agents invent layouts instead of shipping the Stitch / Forest Light mockups.

**Rule:** If a screen is not in this contract, do not ship it. Extend the contract first.

## Shared surfaces (one implementation each)

| Surface | Canonical component | Used by |
|---------|---------------------|---------|
| Goal / strategy create | `StudentGoalCreateModal.jsx` | IEP builder, observation builder, session log |
| Report builder header + footer | `ClinicalBuilderShell.jsx` | IEP, observation |
| Section numbering + cards | `clinical-report-ui.css` + `IEP_BUILDER_SECTIONS` | IEP |
| Observation blocks | `ObservationStitchBlocks.jsx` | Observation only |

## Create Student Goal modal (non-negotiable)

Match `docs/design/stitch/iep-report/` and attached PNGs:

1. **Tabs:** Templates · Custom goal · AI Assisted
2. **Templates:** search repository, domain chips, Goals/Strategies toggle, Add/Select per row
3. **Custom:** domain grid, IEP-language goal statement, supports field
4. **AI:** on-demand generate → list drafts → Add (never on page load)
5. **Right rail:** Goal preview — statement summary, active strategies, clinical environment
6. **Pre-selected goal:** when adding strategy, all adds link to that goal

## IEP builder sections (order fixed)

01 Patient profile · 02 Clinical insights · 03 Present levels · 04 Environments · 05 Goals · 06 Talent development · 07 Service plan

Footer: Save draft · Preview · **Submit for CM review** (wired to `POST /reports/{id}/submit`)

## Deferred (no API = no button)

Share, Export PDF, Duplicate plan

## API map (frontend must use these)

| UI | Endpoint |
|----|----------|
| Template search | `GET /cases/{id}/clinical/repository-search?q=&kind=goals\|strategies&domain=` |
| AI drafts | `POST /reports/{id}/clinical/generate-goal-strategy-drafts` |
| Add IEP goal | `POST /reports/{id}/iep/goals` |
| Link strategy | `POST /reports/{id}/iep/goals/{gid}/strategies` |
| Submit | `POST /reports/{id}/submit` |

## Verification before merge

- [ ] Goal modal matches PNG (two-column, tabs, preview rail)
- [ ] IEP builder shows 7 numbered sections
- [ ] No `window.prompt`; no decorative buttons
- [ ] `npm run build` passes
