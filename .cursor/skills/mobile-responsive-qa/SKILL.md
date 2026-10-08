---
name: mobile-responsive-qa
description: Mobile and PWA layout rules plus a viewport QA pass for the InsighteCase parent, therapist and admin portals. Use for any UI change, sheet, modal, form, sticky footer, bottom-nav or table work, and whenever a bug mentions iPhone, Android, "button hidden", "can't scroll", overlapping layers or the home-screen app.
license: CC0-1.0 base (awesome-cursor-skills `responsive-testing`); see ../THIRD_PARTY_NOTICES.md
---

# Mobile Responsive QA (InsighteCase)

Most therapists and parents use the installed PWA on a phone. Treat 375px and 390px as the primary design widths.

## Layout rules

**Safe areas and the bottom nav**
- `index.html` sets `viewport-fit=cover`, so content can sit under the notch and home indicator. Pad fixed/sticky edges with `env(safe-area-inset-*)`.
- The fixed bottom nav (`.app-mobile-tabs--bottom`, items in `layouts/PortalShell.jsx` `THERAPIST_MOBILE_NAV` / `PARENT_MOBILE_NAV` / `ADMIN_CM_MOBILE_NAV`) covers the bottom of the page. Use the existing token `--portal-bottom-nav-offset` (76px + bottom safe area) for page bottom padding and for anything sticky above the nav. Never hard-code 60/76px.
- Primary actions in a sheet or long form go in a sticky footer inside the sheet, padded by `max(16px, env(safe-area-inset-bottom))`, so they are never under the nav or home indicator.

**Height**
- Use `100dvh` (with a `100vh` fallback line before it) for full-height sheets and workspaces. `100vh` on iOS Safari includes the URL bar and hides footers. Scroll inside the sheet body (`overflow-y: auto; overscroll-behavior: contain`), not the page.
- Account for the on-screen keyboard: focused inputs must scroll into view; do not pin a footer that the keyboard covers on Android.

**Layers (z-index)** - current stack, reuse it, do not invent `9999`:
`.app-mobile-topbar` 35 · bottom nav 40 · `.portal-mobile-fab` 45 · account menu 130 · popovers/comboboxes 200-250 · modals/drawers 400-1200.
- Sheets and modals must sit above the bottom nav and FAB, render at the shell level (React portal) so a parent's `overflow`/`transform` cannot clip them, lock body scroll while open, and restore focus on close.
- Only one modal layer at a time. A nested picker opens inside the sheet's stacking context, not under it.

**Touch and content**
- Interactive targets at least **44x44px** (UI contract standard), 8px apart.
- Inputs at least 16px font so iOS does not zoom on focus.
- No horizontal page scroll at 320-390px. Tables switch to cards on mobile (see `tables-and-reports`); admin breakpoint is 900px (`frontend/docs/admin-mobile-ux.md`).
- Do not rely on hover. Every authorised destination stays reachable on mobile (nav, Menu or More sheet).

**PWA**
- Three manifests (`frontend/public/manifest-{admin,parent,therapist}.webmanifest`). Changes to install, start URL or update/stale banners must work in each portal on iOS (Safari, Add to Home Screen) and Android (Chrome install).
- After a deploy the installed app may serve a cached bundle; update prompts must give accurate, platform-specific steps.

## QA pass (after any UI change)

1. Run backend + `npm run dev` (`.cursor/environment.json`), sign in with seeded demo accounts for each affected role.
2. Check each changed screen at **375x667** (iPhone SE), **390x844** (iPhone 12-15), **412x915** (Android), **768** and **1280**. Use the browser tool or Playwright (`page.setViewportSize`, or `devices['iPhone 13']`).
3. At each size, open every sheet/modal you touched and scroll to its bottom. Check: primary button visible and tappable above the nav; nothing overlaps; no horizontal scroll; keyboard does not hide the focused field; console has no errors; failed requests show a real message.
4. Report in the PR:

```
Mobile QA:
  375 parent  /parent/book      PASS
  390 therapist slot sheet      FAIL - Save under bottom nav -> fixed with --portal-bottom-nav-offset
  1280 admin schedule modal     PASS
```

Attach screenshots when the tool allows. If you could not run the browser, say so; do not mark PASS.

---
Based on spencerpauly/awesome-cursor-skills `resources/responsive-testing` (commit 99cd26557884), CC0-1.0. Rewritten for this repo: added safe-area, bottom-nav, dvh, z-index, touch target and PWA rules and the 390px iPhone width.
