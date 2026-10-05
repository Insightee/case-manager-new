# Clinical UI Contract (mandatory)

**Problem:** Agents invent layouts or mix legacy purple `clinical-ui` with Forest Light Stitch surfaces.

**Rule:** If a screen is not in this contract, do not ship it. Extend the contract first.

## Design systems (do not mix)

| System | Scope | Tokens / CSS | Components |
|--------|--------|--------------|------------|
| **Forest Light** | Therapist portal revamp (dashboard, my cases, case profile tabs, documents drive, case overview) | `forest-light-theme.css`, `docs/design/FOREST_LIGHT_TYPOGRAPHY.md`, surface `*-v2.css` | `cov-*`, `mc-*`, `td-*`, Material Symbols |
| **Parent Forest Light** | Client / parent portal (`/parent/*`) | `parent-portal-theme.css` on `.app-shell--parent`, `docs/design/stitch/parent-portal/DESIGN.md` | Existing `parent-*` / `Client*` components — no `ClinicalCard` |
| **Admin Forest Light** | Staff `/admin/*`, `/adminlogin` | `admin-forest-theme.css` on `.app-shell--admin.forest-light`, `admin-portal.css`, `docs/design/stitch/admin-portal/DESIGN.md` | `AdminDataList` / `AdminTaskCard` / `StatusBadge`; Stitch project `319822486393192441` |
| **Legacy clinical** | Admin clinical dashboards, older purple surfaces | `clinical-theme.css`, `clinical-components.css` | `ClinicalCard`, `ClinicalMetricCard`, `ClinicalStatusBadge` |

**Admin refresh rule:** Primary chrome on `/admin` uses forest green (`#166534`), not indigo gradients. Legacy purple `ClinicalCard` may remain on deep clinical tools until migrated; new dashboard/reports chrome follows `admin-forest-theme.css`.

**Conflict rule:** Forest surfaces must **not** import or render legacy `ClinicalCard` / metric grids on **new** overview surfaces (therapist case overview, parent home, admin leadership home). If a Stitch mock exists, implement with Forest tokens and the screen’s `cov-*` / `td-*` / `mc-*` prefix — not purple clinical cards.

**Parent portal rule:** Shell class `app-shell--parent forest-light`. Primary UI colour is forest green (`#166534`), not indigo/purple dashboard gradients. Stitch project `5257107495041753907` is the visual reference for home, session updates, and reports; see `docs/design/stitch/parent-portal/DESIGN.md`. Therapist reuse of `parent-support.css` keeps legacy accent until that surface migrates separately.

**PWA stale recovery (all portals):** After deploys, home-screen apps may run an old JS bundle. Use `PwaStaleRecoveryListener` (global), `PwaStaleRecoveryHelp` on portal logins and `PortalShell`, and `refreshApp()` from `pwaUpdate.js`. Copy must guide **Get latest**, **Open in browser**, and **Re-add shortcut** — never “Invalid Form” or blame the user. Admin dashboard load failures in standalone should offer the same panel (`AdminDashboardPage`).

## Shared surfaces (one implementation each)

| Surface | Canonical component | Used by |
|---------|---------------------|---------|
| Goal / strategy create | `StudentGoalCreateModal.jsx` | IEP builder, observation builder, session log |
| Report builder header + footer | `ClinicalBuilderShell.jsx` | IEP, observation |
| Section numbering + cards | `clinical-report-ui.css` + `IEP_BUILDER_SECTIONS` | IEP |
| Observation blocks | `ObservationStitchBlocks.jsx` | Observation only |
| **Case overview (therapist)** | `TherapistCaseOverviewDashboard.jsx` + `case-overview-v2.css` | Case profile → Overview tab |
| **Case reports tab (therapist)** | `CaseReportsTab.jsx` + `case-reports-tab.css` | Case profile → Reports tab (default section) |

## Case overview (Forest Light — mandatory)

Stitch project `2951427195113771286`. Full spec: `docs/design/stitch/case-overview/DESIGN.md`.

1. Scope: `.cov-page.forest-light` inside `CaseProfileShell`
2. Data: `caseOverviewCompose.js` only — no overview DB schema
3. Summary: `CaseOverviewSummaryCard.jsx` — not `ClinicalCard`
4. Status: `cov-status-pill` (secondary-container) — not `ClinicalStatusBadge`
5. Pending work: inset rows + underline actions — not metric chips
6. No fake progress % on goals unless backed by real session evidence counts

## Case reports tab (Forest Light — mandatory)

Stitch project `2676660861211267049`. Full spec: `docs/design/stitch/case-reports-tab/DESIGN.md`.

1. Scope: `.crt-page.forest-light` inside `CaseReportsHub` (`section=dashboard`)
2. Data: `GET /cases/{id}/reports/summary` only — no caseload pipeline on this tab
3. CTAs: `target_url` from API → existing report editors (no inline forms)
4. No metric dashboard cards, no "All Cases" filter
5. Status: `ReportStatusChip` (`crt-chip`) — not legacy `ClinicalStatusBadge` on this surface

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
| Case reports tab | `GET /cases/{id}/reports/summary` |

## Verification before merge

- [ ] Goal modal matches PNG (two-column, tabs, preview rail)
- [ ] IEP builder shows 7 numbered sections
- [ ] No `window.prompt`; no decorative buttons
- [ ] `npm run build` passes
