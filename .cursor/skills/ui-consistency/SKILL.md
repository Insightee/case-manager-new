---
name: ui-consistency
description: Keeps InsighteCase UI on one design direction. Use before creating or restyling any screen, component, sheet, button, colour or font in the parent, therapist or admin portals, and when reviewing UI PRs. Enforces the UI contract, Forest Light tokens, reuse of existing components, and no mixing of indigo and green or old and new patterns on a surface.
---

# UI Consistency (InsighteCase)

Agents have repeatedly mixed design systems (indigo chrome with green Forest cards, purple "clinical" cards inside Forest pages). This skill stops that.

## Source of truth (read before any UI work)

1. `docs/design/UI_CONTRACT.md` - the mandatory contract. If a screen or pattern is not in it, do not invent one; propose the contract change in the PR first.
2. `docs/design/FOREST_LIGHT_TYPOGRAPHY.md` - type roles (Manrope headlines, Inter body, JetBrains Mono eyebrows only).
3. `frontend/src/styles/forest-light-theme.css` - Forest Light tokens (`--color-*`, `--font-*`). Use variables, never raw hex.
4. `frontend/docs/admin-mobile-ux.md` - admin <=900px components and patterns.
5. Pending: branch `cursor/design-contract-unification-8aae` proposes Forest Light as the product-wide foundation, with a surface migration register (`SURFACE_MIGRATION.md`). It is **not merged**. Until it is, follow main's contract; once merged, it wins and its register decides each surface's system.

## Rules

- **One system per surface.** Each page/surface is either Forest Light or legacy operational (indigo `--primary: #4f46e5` in `index.css`, admin teal pills). Never both on the same surface, and do not mix them within one portal flow (e.g. a Forest sheet launched from an indigo page needs the owner's call, noted in the PR).
- **No global restyles.** Do not change `index.css` root tokens or apply Forest Light app-wide in a feature PR. Migrate one surface per PR, scoped under its wrapper class (`.forest-light`, `.cov-page`, `.crt-page`, ...).
- **Reuse before you build.** Search first: `rg -l "<ComponentName>|<class-prefix>" frontend/src`. Prefer existing shared components (`components/shared/`: `StatusBadge`, `QueryState`, `ErrorBanner`, `PageSkeleton`, `SectionHeader`, `CaseCombobox`; admin `components/admin-portal/ui/`: `AdminDataList`, `AdminEmptyState`, `AdminMobilePillTabs`, `AdminStickyFilterRow`) and the canonical components named in the contract (`StudentGoalCreateModal`, `ClinicalBuilderShell`, `TherapistCaseOverviewDashboard`, `CaseReportsTab`).
- **No new colours, shadows, radii or fonts.** If a token is missing, add it to the theme file in the same PR and explain why.
- **Same element, same look across portals.** A status chip, primary button or empty state for the same concept looks and reads the same in parent, therapist and admin, unless the contract says otherwise.
- **No decorative or dead UI.** No button without a working API (contract: "no API = no button"), no `window.prompt`, no fake progress numbers.
- **Copy:** supportive guidance that names the real problem and next step. Banned: "Invalid Form", "Submission Failed", "Missing Data", "Invalid credentials" as the message. Say "client" or the child's name, not "patient".
- **Accessibility:** 44px targets, visible labels or `aria-label`, dialogs with `role="dialog"`, focus trap and focus return (contract Layer 1).

## PR checklist (paste into the PR)

```
UI consistency:
- [ ] Surface system: Forest Light / legacy (name the wrapper class)
- [ ] No mixed indigo + green or legacy clinical cards on this surface
- [ ] Reused components: ...   New components: ... (why existing ones did not fit)
- [ ] Only theme variables; no raw hex / new fonts
- [ ] Same pattern applied in every portal that shows this element
- [ ] `npm run build` and `npm run lint` pass; mobile QA done (`mobile-responsive-qa`)
```
