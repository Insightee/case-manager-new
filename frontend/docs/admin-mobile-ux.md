# Admin portal — mobile UX (≤900px)

**Canonical visual and interaction contract:** [docs/design/UI_CONTRACT.md](../../docs/design/UI_CONTRACT.md). This file is the **admin ≤900px layout pattern** (tabs, filters, card lists). It is not a second product palette.

Forest Light is the future product-wide foundation. Admin teal pills (`#0d9488`) remain valid **only while this chrome is unmigrated**. Do not globally replace admin CSS when therapist surfaces migrate. See [docs/design/SURFACE_MIGRATION.md](../../docs/design/SURFACE_MIGRATION.md).

Admin portal pages share one mobile layout system. Desktop (≥901px) keeps existing tables and full tab bars.

## Breakpoint

- **Mobile / tablet:** `max-width: 900px`
- **Desktop:** `min-width: 901px`

## Components

| Component | Use |
|-----------|-----|
| `PortalTabBar` | Desktop section tabs |
| `AdminMobilePillTabs` | Mobile primary pills + **More** overflow menu |
| `AdminStickyFilterRow` | Inline sticky filters (month, status, search) |
| `AdminCollapsibleFilters` | Complex filter grids (reports, pipeline) |
| `AdminDataList` | Table desktop + card list mobile |
| `AdminTaskCard` | Mobile row cards with actions above fold |
| `AdminEmptyState` | Empty states; use `hints` + `action` for guidance |

## Navigation

- **Primary pills:** scroll horizontally, 44px min height, active = teal fill (`#0d9488`)
- **Overflow:** secondary modules in **More ▾** sheet (e.g. Products & rules, Packages on finance)
- Tab **ids and URL params are unchanged** — only labels shorten on mobile
- **IEP management standard (all admin/staff roles):**
  - Mobile sections use `AdminMobilePillTabs` with role/function labels:
    - `IEP status` (`dashboard`)
    - `Planner` (`plans`)
    - `Uploader` (`upload`)
  - Keep `Cases` as a single compact ghost button, right-aligned below pills.
  - Do not render desktop `PortalTabBar` on mobile.

## Page header

- Hide `admin-page-header__sub` and long leads on mobile
- Title: `1.25rem`, tight margin
- Hub pages own a single header; child tabs use `embedded` to skip duplicate titles

## Filters

- Prefer `AdminStickyFilterRow` when ≤3 controls fit inline
- Use `AdminCollapsibleFilters` when many fields or export toolbars
- Sticky under tabs with safe-area-aware background
- **IEP dashboard filters:** always use `AdminCollapsibleFilters` + visible search in bar; keep advanced filters (service, therapist, session range, include closed) inside panel to maximize case list space.

## Empty states

```jsx
<AdminEmptyState
  title="No session entries for May 2026"
  hints={['Change the month filter', 'Approve daily logs to generate rows']}
  action={<Link to="/admin/logs">View session logs →</Link>}
/>
```

## Tables on mobile

Default: `AdminDataList` cards. Card priority: identity → status → why this row is here → primary action.

**Comparison exception** (invoice lines, finance margin, attendance matrices): horizontal scroll with a sticky identity column **and** a selected-row summary. Not the default for cases/people lists. See [UI_CONTRACT.md](../../docs/design/UI_CONTRACT.md) Layer 2.

Short admin tasks use **sheets**. Do not put IEP/observation builders in a sheet.

## Colors (legacy admin mobile — unmigrated)

These hexes describe **current** admin mobile chrome. Product primary after admin migration is Forest green in the UI contract, not teal.

- Active pill (current): `#0d9488` / gradient `#0f766e` → `#0d9488`
- Muted text (current): `#64748b`
- Borders (current): `#e2e8f0`
- Surface (current): `#fff` on `#f8fafc` page bg

Do not add new decorative gradients. New admin work should follow Layer 2 of the UI contract once that surface’s migration packet is open.

## CSS entry

All mobile rules live in [`admin-portal-mobile.css`](../src/components/admin-portal/admin-portal-mobile.css), scoped with `.app-shell--admin` where needed so login `portal-tabs` grid is unaffected.
