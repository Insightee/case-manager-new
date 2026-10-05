# Admin portal — Forest Light (operations)

**Status:** Visual refresh shipped in code (`admin-forest-theme.css`); Stitch reference project for iteration.  
**Implementation:** `.app-shell--admin.forest-light` · shared `admin-portal.css` + `admin-dashboard.css` + `admin-reports.css`.

## Stitch project

| Field | Value |
|--------|--------|
| Project ID | `319822486393192441` |
| Title | InsighteCase Admin Portal — Forest Light |
| Design system | `assets/d3e91569df33441fbf4421b9d1c8044a` (Forest Light Operations — generated with reports screen) |

## Stitch screens

| Screen | Stitch screen ID | Route · component |
|--------|------------------|-------------------|
| Clinical reports workspace | `aa5fe4ed10794951a5022aaa6333d7b7` | `/admin/reports` · `AdminReportsPage.jsx` |
| Leadership home | _(generate next)_ | `/admin` · `AdminDashboardPage.jsx` |

Mobile card lists remain a **code** concern (`AdminDataList` / `AdminTaskCard` at ≤900px).

## Visual rules (aligned with parent Forest Light)

| Token | Value |
|-------|--------|
| Page background | `#F7F8F5` |
| Surface | `#FFFFFF` |
| Border | `#DDE4DE` |
| Primary / active | `#166534` · hover `#14532D` |
| Soft fill | `#EAF3EC` |
| Text | `#17211B` · muted `#526057` |

**Do not use:** indigo/purple gradients (`#6366f1`, `#4f46e5`) on primary actions, eyebrows, or active tabs in new work.

**Typography:** Manrope 600–700 for headings and panel titles; Inter for body and table cells. KPI values use `tabular-nums`.

**Tables (`AdminDataList`):** Sticky header row, uppercase muted column labels, 12px cell padding, hover row `#F9FBF9`, wrapped in rounded border — no default zebra soup.

**Buttons:** Min height 44px on mobile; primary solid forest green (no gradient shadow); secondary white + border; ghost soft green fill.

**Motion:** No row lift/transform on hover for KPI or queue lists — border/background only (`table-ui-fix` density rule).

## Mobile (≤900px)

- Desktop table hidden; `admin-data-list__mobile` task cards (`admin-task-card`)
- Full-width button groups in card footers
- Admin tab bar scroll (`admin-portal-mobile.css`) uses forest active underline via `admin-forest-theme.css`

## PWA

See parent doc § PWA — admin login `/adminlogin`, manifest `manifest-admin.webmanifest`, `PwaStaleRecoveryHelp` on dashboard load errors.

## Acceptance

- [x] Admin shell has `forest-light` class
- [x] Primary buttons and active tabs forest green
- [x] Tables: sticky headers + theme borders in admin shell
- [ ] Stitch screens generated for dashboard + reports (reference)
- [ ] CI visual spot-check on `/admin` and `/admin/reports`
