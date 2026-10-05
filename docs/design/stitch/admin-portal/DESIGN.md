# Admin portal — mobile & PWA notes

**Status:** Operational admin uses legacy clinical surfaces + `admin-*` components (not full Forest Light migration).  
**Scope:** Staff on phones/tablets (case managers, finance, HR) who install **InsighteCase Admin** to the home screen.

## PWA

| Item | Value |
|------|--------|
| Manifest | `/manifest-admin.webmanifest` |
| App name | InsighteCase Admin |
| Config | `frontend/src/lib/portalPwa.js` → `PORTAL_PWA.admin` |
| Sign-in | `/adminlogin` · `LoginPage` with `portalType="admin"` |

## After deploy — stale shortcut UX

Same pattern as parent/therapist (`docs/design/stitch/parent-portal/DESIGN.md` § PWA):

1. **Get latest** — service worker refresh via `refreshApp()`  
2. **Open in browser** — copy URL; sign in outside the home-screen shell  
3. **Re-add shortcut** — `PortalInstallSheets` instructions  

Surfaces:

- `LoginPage` (admin login) — `PwaStaleRecoveryHelp`
- `PortalShell` (`portal="admin"`) — yellow banner when chunk load hint is set
- `AdminDashboardPage` — recovery panel when dashboard API fails in standalone / stale hint

## Mobile admin UX (existing patterns)

- Lists: `AdminDataList` + card stack ≤900px (`frontend/docs/admin-mobile-ux.md`)
- Dashboard: `AdminLeadershipOverview`, KPI grid, role queues — keep data density; no decorative row motion
- Install control: top bar + sidebar `PortalInstallButton`

## Future (not in scope)

- Forest Light admin home migration (separate Stitch project when contracted)
- Unified leadership + CM home visual parity with therapist `cov-*` surfaces
