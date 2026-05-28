# Admin portal — mobile UX (≤900px)

Staff portal pages share one mobile layout system. Desktop (≥901px) keeps existing tables and full tab bars.

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

## Colors (align with InsightCase)

- Active pill: `#0d9488` / gradient `#0f766e` → `#0d9488`
- Muted text: `#64748b`
- Borders: `#e2e8f0`
- Surface: `#fff` on `#f8fafc` page bg

## CSS entry

All mobile rules live in [`admin-portal-mobile.css`](../src/components/admin-portal/admin-portal-mobile.css), scoped with `.app-shell--admin` where needed so login `portal-tabs` grid is unaffected.
