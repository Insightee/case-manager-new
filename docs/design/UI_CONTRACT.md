# Clinical UI Contract (canonical)

**Status:** Canonical product design contract. If a visual, interaction, or layout rule is not here, do not invent a parallel spec — extend this document first.

**Product feel:** InsighteCase is a calm, precise, approachable clinical workspace. Hierarchy, readability, navigation, and task completion come first. Visual consistency supports that work; it does not replace it.

**Do not** treat this file as permission to restyle the application. Implementation happens in later phases, surface by surface, using [SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md) and [UX_BACKLOG.md](./UX_BACKLOG.md).

---

## How to use this document

| Layer | What it governs | Change it when |
|-------|-----------------|----------------|
| **1. Product principles** | Why the UI behaves as it does | Clinical doctrine or accessibility policy changes |
| **2. Shared foundations** | Colour, type, space, controls, feedback, a11y | Tokens or interaction language change |
| **3. Portal patterns** | Therapist, client/parent, admin shells | Navigation or portal task model changes |
| **4. Screen contracts** | Canonical components, APIs, required actions, states | A screen, endpoint, or clinical workflow changes |

Companion files (not competing specs):

| File | Role |
|------|------|
| [FOREST_LIGHT_TYPOGRAPHY.md](./FOREST_LIGHT_TYPOGRAPHY.md) | Type roles for Forest Light. Defers colour and layout to this contract. |
| [SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md) | Legacy / migration planned / migrated register for real routes. |
| [UX_BACKLOG.md](./UX_BACKLOG.md) | Phased implementation backlog with acceptance criteria. |
| [../skills/cross-portal-product-design/SKILL.md](../skills/cross-portal-product-design/SKILL.md) | Role-matrix workflow when a feature spans portals. |
| [../../frontend/docs/admin-mobile-ux.md](../../frontend/docs/admin-mobile-ux.md) | Admin ≤900px layout patterns. Visual tokens defer here. |
| `frontend/src/lib/clinicalUiContract.js` | Runtime labels and section keys for IEP / goal modal. Must stay aligned with Layer 4. |

**Conflict rule:** When documents disagree, this contract wins for UI/UX. Clinical, API, permission, data, and workflow constraints in AGENTS.md and backend docs stay in force. See [Conflict resolution](#conflict-resolution).

---

## Design systems in the repo today

Forest Light is the **future product-wide foundation**. Other palettes remain valid only on surfaces labelled **Legacy** or **Migration planned**. A future green foundation must not trigger a global stylesheet replacement.

| System | Where it actually lives | Status | Do not |
|--------|-------------------------|--------|--------|
| **Forest Light — product foundation (proposed)** | This contract, Layer 2 | Proposed. Contrast verification required before any CSS change. | Apply globally in one PR |
| **Forest Light v1 (shipped)** | `frontend/src/styles/forest-light-theme.css`, `forest-light-iep.css`, `forest-light-observation.css`, `clinical-report-ui.css` | Migrated visual language for IEP and observation builders only. Primary is near-black (`#000` / `#0b1c16`), not the proposed green. | Mix with indigo therapist chrome |
| **Operational indigo** | `frontend/src/index.css` `--primary: #4f46e5`, `.admin-btn`, `.ic-btn`, parent portal CSS | Legacy default for most therapist, parent, and admin chrome | Call this Forest Light |
| **Admin teal pills** | `frontend/docs/admin-mobile-ux.md`, `admin-portal-mobile.css` `#0d9488` | Legacy admin mobile tabs only | Use as the product primary |
| **Login aqua** | `.login-submit` `#2db7a7` → `#1f9f91` | Legacy public auth | Use inside portals |
| **Named but missing “legacy clinical”** | Contract previously cited `clinical-theme.css`, `ClinicalCard`, `ClinicalMetricCard` | Those files **do not exist**. `ClinicalPrimaryButton` / `ClinicalStatusBadge` still emit unstyled `clinical-btn-*` classes. | Reinvent a purple system |

**Stitch references** (project IDs and paths below) remain authoritative for those screens until a replacement reference is recorded in Layer 4. The files under `docs/design/stitch/` are **not in the repository**. Absence of the file does not retire the requirement.

---

## Layer 1 — Product principles

Every portal follows these five principles. Portal shells, permissions, and task structures stay separate; the principles do not.

### Accessible

- Target **WCAG 2.2 Level AA** for contrast, keyboard, name/role/value, and focus visibility.
- Every control has a visible text label or an accessible name (`aria-label` / `aria-labelledby`).
- Keyboard users can reach every authorised action. Focus order follows reading order.
- Dialogs are modal to assistive technology (`role="dialog"`, labelled title, focus trap, return focus on close).
- Honour `prefers-reduced-motion`. Do not add animation that competes with clinical reading.
- Touch targets are at least **44×44 CSS pixels** on viewports ≤900px. Icon-only controls still expose a 44px hit area.

### Neuro-affirmative

- Never frame a child as a deficit. Diagnostic-first architecture is forbidden.
- Schema and UI copy use: `strengths`, `support_needs`, `environment_factors`, `participation_patterns`, `strategies`, `progress_signals`, `challenges`.
- Hierarchy is Child → Environment → Support — not Diagnosis → Problem → Fix.
- UI copy says **client** or the child’s name, not “patient”, in therapist and parent surfaces.
- Free text enriches structured fields; it does not replace chips, sliders, or goal/strategy links.

### Case-centric

- `Case` is the operational source of truth. Sessions, logs, reports, invoices, payouts, and incidents link to cases.
- Therapist access is scoped to assigned cases (`case_assignments` history), not `case.therapist_id` alone.
- Case context (header, back link, active tab) stays visible while the user works inside a case.
- Deep links land on the correct portal path and tab. Do not hardcode `/admin` into therapist or parent links.

### Task-focused

- Design for field work. Timing caps: session log entry under 5 minutes; new observation under 15; monthly report verification under 10.
- One primary action per view. Secondary actions are visually quieter.
- Progressive disclosure: show the current step. Profiles, timelines, and history sit behind a deliberate click.
- Primary actions (Save, Complete, Submit, voice note, evidence upload) sit in a sticky footer or bottom sheet on mobile — thumb zone, not the top-right of a tall form.
- Do not hide authorised destinations from mobile navigation. Overflow belongs in a labelled drawer or More sheet, never in an unreachable menu.

### Supportive (connection before correction)

Banned UI strings: `Invalid Form`, `Submission Failed`, `Missing Data`, and `Invalid Login` / `Invalid credentials` as the user-facing message.

Required alternatives:

- “Looks like we still need a few details before we can save this.”
- “Would you like to continue from where you left off?”
- “Let's add one more observation.”
- Login mismatch: “This account signs in through a different portal. Use the therapist, parent, or admin sign-in that matches your role.”

**Optimistic UI (clarified, not removed):**

| Interaction | Client behaviour | When the user sees success |
|-------------|------------------|----------------------------|
| Filters, chips, tabs, navigation, draft field edits, expand/collapse | Update local state immediately | Immediately, then reconcile |
| Draft save | Show **Saving…** on the control; keep the form editable | **Saved** only after HTTP success |
| Clinical submit (session log submit, report submit for CM review, goal/strategy add that writes the plan) | Immediate press feedback; disable duplicate submit; **do not** mark complete | Status changes after server success |
| Approvals (log approve, report publish, leave decision) | Immediate press feedback only | Outcome after server success |
| Financial outcomes (invoice submit, payout send, payment mark) | Immediate press feedback only | Amounts and status after server success |

Preserve input after errors. Never clear a form because the server rejected it.

AI does not create clinical truth. Allowed: on-demand draft, summary, library match, pattern detection. Forbidden: setting report status to Complete, diagnosing, or overriding therapist input. Do not call LLM endpoints from `onChange`, `onScroll`, page load, or active typing.

---

## Layer 2 — Shared foundations

These tokens are the **proposed** Forest Light product foundation. They require contrast verification (WCAG 2.2 AA) before implementation. Until a surface is migrated, keep its current tokens.

### Colour (proposed — verify before implementation)

Green is for **primary actions and selection only**. Success, warning, error, and information use separate semantic colours plus text or an icon. Colour is never the only indicator.

| Role | Hex | Intended use |
|------|-----|--------------|
| Primary action | `#166534` | Primary buttons, key links on white, active nav indicator |
| Hover / pressed | `#14532D` | Primary hover, active press |
| Selected surface | `#EAF3EC` | Selected rows, active chips, highlighted nav item background |
| Page background | `#F7F8F5` | Portal canvas |
| Surface | `#FFFFFF` | Cards, dialogs, tables, inputs |
| Main text | `#17211B` | Headings and body |
| Secondary text | `#526057` | Meta, captions, placeholders (verify vs 4.5:1 on page and surface) |
| Border | `#DDE4DE` | Dividers, input borders, table lines |

**Contrast verification gate (must pass before CSS lands):**

| Pair | Minimum | Notes |
|------|---------|-------|
| `#166534` on `#FFFFFF` | 4.5:1 (text/UI) | Primary button is white label on `#166534` — also ≥4.5:1 |
| `#14532D` on `#FFFFFF` | 4.5:1 | Hover/pressed |
| `#17211B` on `#FFFFFF` and on `#F7F8F5` | 4.5:1 | Body text |
| `#17211B` on `#EAF3EC` | 4.5:1 | Text on selected surface |
| `#526057` on `#FFFFFF` and on `#F7F8F5` | 4.5:1 | If it fails, darken secondary text; do not keep the hex |
| `#166534` on `#EAF3EC` | 3:1 non-text / 4.5:1 if used as text | Selected chip with green label |
| `#DDE4DE` vs adjacent surface | 3:1 if the border is the only focus/affordances cue | Prefer focus ring over relying on the border |

**Semantic colours (keep distinct from primary green):**

| Meaning | Current shipped reference (do not collapse into primary) | Future Forest mapping |
|---------|----------------------------------------------------------|------------------------|
| Success | `#059669` / `#1f7b57` text on `#d8f4eb` | Separate green-teal, never the same hex as primary action |
| Warning | `#b45309` on `#fef3c7` | Unchanged role |
| Error | Forest v1 `#ba1a1a` / `#93000a` on `#ffdad6` | Keep red; do not use primary green |
| Information | `#1d4ed8` on `#dbeafe` | Blue; not indigo-as-brand |

**Shipped palettes that remain on unmigrated surfaces**

| Token | Value | Surfaces |
|-------|-------|----------|
| `--primary` (global) | `#4f46e5` | Most chrome |
| `--color-primary` (Forest v1 `@theme`) | `#000000` | Tailwind Forest utilities |
| `--color-lush-forest` | `#0b1c16` | IEP/observation primary buttons |
| `--color-secondary` (Forest v1) | `#416656` + container `#c3ecd7` | Forest selection/pills |
| Admin pill | `#0d9488` / `#0f766e` | Admin mobile tabs |
| Login submit | `#2db7a7` | Public login |
| Parent hero | `#6366f1` → `#7c3aed` | Parent dashboard |

Do not load a new global `:root` palette in a migration PR. Scope new tokens to a surface class (for example `.forest-light` or `.app-shell--therapist` once that portal migrates).

### Typography

Canonical type roles: [FOREST_LIGHT_TYPOGRAPHY.md](./FOREST_LIGHT_TYPOGRAPHY.md).

| Role | Family | Use |
|------|--------|-----|
| Headline | Manrope 600–700 | Page titles, client name, dashboard title |
| Body | Inter 400–500 | All readable content: names, dates, values, buttons, helper text |
| Label / eyebrow | JetBrains Mono 500 | **Existing approved eyebrows only** (section titles such as `PROFILE SNAPSHOT`, small uppercase action links already using mono) |

Rules:

1. Default to Inter.
2. Do not expand uppercase monospace styling to new surfaces, table headers, goal titles, KV values, or care-team names.
3. Never use `ui-monospace`, Courier, or system monospace. Existing `.cr-section__label { font-family: ui-monospace }` is a defect to fix on that surface’s migration.
4. Therapist page titles use Manrope only after that surface migrates; until then, do not mix fonts inside one card.

### Spacing, radius, elevation, width

| Token | Value |
|-------|-------|
| Spacing scale | 4, 8, 12, 16, 24, 32, 48px |
| Control height / touch target | 44px generally (≤900px always; ≥901px compact admin rows may use 40px height **with** a 44px hit area if the control is icon-only) |
| Control radius | ~8px |
| Surface radius | ~12px |
| Elevation | 1px border `#DDE4DE` (or current `--line` on legacy). Shadow only for modal overlay, max ~`0 8px 24px` at 12% opacity. |
| Content width | Forms and reading columns max ~720px; operational tables use the full workbench width; dashboards max ~1200px inner content. |

Banned chrome: decorative gradients, glassmorphism (`backdrop-filter` on nav/cards), stacked ambient blobs, hover shadows on KPI tiles, oversized dashboard cards (KPI numerals >1.5rem), unnecessary badges, looping animation.

### Icons

- Use **Material Symbols** consistently on migrated Forest surfaces (already used in observation stitch blocks).
- One icon set per portal chrome. Do not mix Material Symbols with ad-hoc PNG glyphs on the same toolbar.
- Icon-only buttons require an accessible name and a 44px target.

### Controls — buttons

One visual language per migrated surface. Until a shared `Button` primitive exists, new work on a migrating surface must still match these variants.

| Variant | Use | Appearance (proposed) | Label |
|---------|-----|----------------------|-------|
| **Primary** | The one forward action | Fill `#166534`, text `#FFFFFF`, 44px height, 8px radius | Verb + object when needed: “Save draft”, “Submit for review” |
| **Secondary** | Alternative safe action | White surface, `#DDE4DE` border, `#17211B` text | “Preview”, “Cancel” |
| **Tertiary** | Low-emphasis / inline | No fill, no heavy border, `#166534` or `#17211B` text | “Change case”, “View details” |
| **Destructive** | Irreversible or harmful | Error fill or error outline + text; never primary green | “Delete”, “Reject”, “Cancel session” |

Placement:

- One primary per view or sheet.
- On mobile, primary sits in the sticky footer / bottom sheet, full-width or right-aligned in a 44px bar, padded with `env(safe-area-inset-bottom)`.
- Destructive is never adjacent to primary without a separator or confirmation step.
- Header and footer must not duplicate the same primary on small screens. Desktop may keep a header action; mobile keeps the thumb-zone footer.

Interaction states (all variants):

| State | Behaviour |
|-------|-----------|
| Default | Contrast-verified colours |
| Hover | `#14532D` for primary; border darken for secondary |
| Focus | Visible 2px ring, offset 2px, never `outline: none` without a replacement. One ring token per migrated surface. |
| Selected | `#EAF3EC` background for toggles/chips/nav |
| Disabled | Opacity 0.5, `aria-disabled` or `disabled`, cursor not-allowed. Do not use `pointer-events: none` alone — the control must still explain why. |
| Loading | Disable the control, set `aria-busy="true"`, visible **Saving…** / **Submitting…**. Block double submit. |
| Error | Keep values; announce the guidance message; move focus to the first field that needs attention when the submit failed |

Do not introduce a fifth unnamed button colour. Parent/therapist screens must not keep using `.admin-btn` after they migrate.

### Forms and feedback

| State | Required UI |
|-------|-------------|
| Empty | Title + two concrete next steps (`AdminEmptyState` pattern: `hints` + `action`). No blank tables. |
| Loading (page) | Skeleton or labelled “Loading…” in the main region; do not replace the whole shell. |
| Saving | Control label **Saving…**; do not toast “Saved” yet |
| Saved | Control returns to default; optional inline “Saved just now” that is not a success-banner for clinical completion |
| Validation | Connection-before-correction copy; list the missing structured fields |
| Retry | After network failure, keep the form and offer **Try again** |
| Confirmation | For submit / approve / pay: explicit confirm in a dialog or review step; result only after server success |

`window.prompt` is forbidden. Use a labelled dialog or sheet.

### Navigation (shared)

- Desktop: persistent sidebar of authorised destinations. Active item uses selected surface + 3px primary bar or equivalent, not colour alone.
- Mobile ≤900px: bottom tabs for the portal’s top tasks (3–4 items) plus a drawer that lists **every remaining authorised destination**, including profile and notifications.
- Overflow is a labelled **Menu** / **More** control that opens that drawer. A Menu button that is unreachable in code is a defect (see backlog).
- Tab **ids and URL params stay stable** when labels shorten on mobile.
- Back navigation inside a case returns to the case list or the previous case tab, not the portal home, unless the user came from home.
- Deep links use portal-correct paths (`notificationLinks.js` pattern).

### Mobile and responsive

Breakpoint used across admin and portal shell: **900px** (`frontend/docs/admin-mobile-ux.md`, `PortalShell`).

| Pattern | ≤900px | ≥901px |
|---------|--------|--------|
| Data tables | Card list (`AdminDataList` / equivalent). No horizontal-only tables as the only view. | Dense tables allowed |
| Multi-column builders | Single column; preview rails become a collapsed section, not `display: none` with no access | Two column when the contract requires a rail |
| Filters | Sticky compact row or collapsible panel | Inline |
| Dialogs | Bottom sheet, `max-height: 100dvh`, sticky 44px actions, `safe-area-inset-bottom` | Centered modal, max-width ~560–720px, `max-height: 90vh` |
| Page padding | Account for bottom nav **once**. `--portal-bottom-nav-offset` must match the real tab bar. | Sidebar width `--spacing-sidebar` (280px Forest v1) |
| Keyboard | Sticky actions sit above the visual viewport; do not cover focused inputs | Unchanged |

Safe-area: apply `env(safe-area-inset-*)` on the shell **or** the body, not both. Sticky clinical footers use `bottom: var(--portal-bottom-nav-offset)`, never `bottom: 0` under a fixed tab bar.

### Accessibility (checklist for every migrated surface)

- [ ] Keyboard: tab, shift-tab, enter/space on buttons, escape closes dialogs
- [ ] `:focus-visible` ring 2px, not removed by `outline: none`
- [ ] Labels: every input, select, checkbox, icon button
- [ ] Dialogs: `role="dialog"`, `aria-modal="true"`, labelled title, focus trap
- [ ] Contrast verified for proposed tokens on that surface
- [ ] Status is not colour-only (text or icon)
- [ ] `prefers-reduced-motion` respected
- [ ] Skip link to `#main-content` remains (already in `PortalShell` and `LoginPage`)

---

## Layer 3 — Portal patterns

Share foundations and suitable components. Keep **separate portal shells**, RBAC, and task structures. Never ship an admin page into therapist/parent routes without a portal-specific wrapper ([cross-portal-product-design](../skills/cross-portal-product-design/SKILL.md)).

### Therapist

**Job:** today’s work, assigned cases, session documentation, unfinished tasks.

| Priority | Desktop | Mobile |
|----------|---------|--------|
| Session documentation | `/therapist/logs` | Bottom tab **Today** |
| Assigned cases | `/therapist/cases` | Bottom tab **Cases** |
| Unfinished reports | `/therapist/reports` | Bottom tab **Reports** |
| Today / home | `/therapist` | Bottom tab **Home** |
| Invoices, support, meetings, leave, scheduling | Sidebar | Drawer (must remain reachable) |
| Profile, notifications | Sidebar footer / header bell | Drawer footer |

Support mobile use without hiding necessary clinical information: case overview, goals, environment, and session evidence stay available; they may move into tabs, not disappear.

Case context lives at `/therapist/cases/:caseId` with `?tab=`. Back control returns to My Cases.

### Client / parent

**Job:** next steps, appointments, understandable updates, communication.

| Priority | Desktop | Mobile |
|----------|---------|--------|
| Next steps / home | `/parent` | Bottom tab **Home** |
| Session updates | `/parent/session-logs` | Bottom tab **Sessions** |
| Reports | `/parent/reports` | Bottom tab **Reports** |
| Billing | `/parent/billing` | Bottom tab **Billing** |
| Book, profile, support, meetings | Sidebar | Drawer |
| Case hub | `/parent/cases/:caseId` (not in global nav) | Reached from home / notifications |

Copy is plain language. Progressive disclosure: do not dump IEP internals on the home card. Parent routes are read-oriented except booking, profile, and support writes allowed by API.

### Admin (including CM, finance, HR, SPOT)

**Job:** queues, search, filters, comparisons, operational actions.

Preserve useful **desktop table density** and the existing mobile patterns in [admin-mobile-ux.md](../../frontend/docs/admin-mobile-ux.md):

- `PortalTabBar` desktop; `AdminMobilePillTabs` mobile
- `AdminStickyFilterRow` / `AdminCollapsibleFilters`
- `AdminDataList` + `AdminTaskCard`
- `AdminEmptyState` with hints + action

Admin teal pills stay until that chrome migrates. Do not restyle all admin tables in the therapist phase.

Case managers review exceptions, not data entry. Queue trigger vectors in AGENTS.md stay unchanged.

### Login (public)

Role-aware entry remains: `/login` selector plus `/therapistlogin`, `/clientlogin` (`/clinetlogin` alias), `/adminlogin`, `/devlogin`. Keep three visible portals. Visual migration of login is **phase 2/3**, not a blocker for therapist clinical surfaces.

---

## Layer 4 — Screen contracts

If a screen is not in this layer, do not ship a new layout for it. Add the screen here first.

### Canonical components (one implementation each)

| Surface | Canonical component | Used by | Implementation status |
|---------|---------------------|---------|------------------------|
| Goal / strategy create | `StudentGoalCreateModal.jsx` | IEP builder, observation builder, session log | Exists. Tabs in JS: Templates, Custom. AI tab required below — missing in runtime. |
| Report builder header + footer | `ClinicalBuilderShell.jsx` | IEP, observation | Exists. Header **and** footer both expose Save / Preview / Submit — mobile should keep footer only. |
| Section numbering + cards | `clinical-report-ui.css` + `IEP_BUILDER_SECTIONS` | IEP | Exists |
| Observation blocks | `ObservationStitchBlocks.jsx` | Observation only | Exists |
| Case overview (therapist) | Target: Forest overview on `/therapist/cases/:caseId?tab=overview` | Case profile | **Not implemented.** No `TherapistCaseOverviewDashboard.jsx`, `case-overview-v2.css`, `cov-*`, or `CaseProfileShell`. Live UI is inline in `CaseDetailPage.jsx`. |
| Case reports tab (therapist) | Target: reports section on the case profile | Case profile | **Not implemented.** No `CaseReportsTab.jsx`. Reports live at `/therapist/reports` and clinical builders under `/therapist/reports/cases/:caseId/{observation\|iep}`. |

Do not import or render unstyled `ClinicalCard` / `ClinicalMetricCard` (they do not exist). Forest surfaces must not use `ClinicalStatusBadge` once a Forest status chip exists. Until then, do not add new `ClinicalStatusBadge` call sites.

### Create Student Goal modal (non-negotiable)

Match Stitch `docs/design/stitch/iep-report/` (authoritative until a replacement is listed here) and these behaviours:

1. **Tabs:** Templates · Custom goal · AI Assisted
2. **Templates:** search repository, domain chips, Goals/Strategies toggle, Add/Select per row
3. **Custom:** domain grid, IEP-language goal statement, supports field
4. **AI:** on-demand generate → list drafts → Add (never on page load or `onChange`)
5. **Right rail:** Goal preview — statement summary, active strategies, clinical environment. On ≤768px the rail becomes a collapsible **Preview** section in the sheet — it must remain reachable.
6. **Pre-selected goal:** when adding a strategy, all adds link to that goal

Runtime `GOAL_MODAL_TABS` currently omits AI Assisted. That is a gap, not a retirement of the tab.

### IEP builder sections (order fixed)

Runtime source of truth for **keys and visible titles**: `IEP_BUILDER_SECTIONS` in `frontend/src/lib/clinicalUiContract.js`.

| # | Key | Visible title (authoritative) | Retired display aliases (do not use in UI) |
|---|-----|-------------------------------|--------------------------------------------|
| 01 | `child_context` | Client profile & core administration | Patient profile |
| 02 | `clinical_insights` | Clinical insights from observations | Clinical insights |
| 03 | `priority_domains` | Domains | Present levels |
| 04 | `strategies_accommodations` | Learning environments & supports | Environments |
| 05 | `goals_plan` | Active & proposed goals | Goals |
| 06 | `talent_development` | Strengths & growth opportunities | Talent development (key retained) |
| 07 | `review_parent_plan` | Service & implementation plan | Service plan |

Footer actions: Save draft · Preview · **Submit for CM review** wired to `POST /reports/{id}/submit`.

On viewports ≤900px, those three actions exist once, in the sticky footer, above the portal bottom nav.

### Observation builder

Stitch path `docs/design/stitch/observation-report/observation_report_comprehensive_clinical_workspace/` remains the reference until replaced here. Implemented approximation: `ObservationStitchBlocks.jsx` + `forest-light-observation.css`.

Parent `variant="parent"` is preview/read. Do not expose builder write controls to parents.

### Deferred (no API = no button)

Share, Export PDF, Duplicate plan — no decorative control.

`DEFERRED_ACTIONS` in JS currently contains only `duplicate`. `ClinicalBuilderShell` still accepts `onDownloadPdf` and IEP admin still exposes **Share with family** in places. Those controls stay illegal until an API is documented in the map below.

### Fabricated progress and disconnected buttons

- No fake progress % on goals unless backed by real session evidence counts.
- No button that does not call a documented endpoint or in-app navigation target.
- No `window.prompt`.

### API map (frontend must use these)

| UI | Endpoint |
|----|----------|
| Template search | `GET /cases/{id}/clinical/repository-search?q=&kind=goals\|strategies&domain=` |
| AI drafts | `POST /reports/{id}/clinical/generate-goal-strategy-drafts` |
| Add IEP goal | `POST /reports/{id}/iep/goals` |
| Link strategy | `POST /reports/{id}/iep/goals/{gid}/strategies` |
| Submit | `POST /reports/{id}/submit` |
| Case reports summary | `GET /cases/{id}/reports/summary` |

Do not add UI that writes clinical truth through a different path. RBAC and case scope still come from the backend; hiding a button is not a security control.

### Stitch project references (authoritative until replaced)

| Screen | Stitch project | Spec path (missing from repo) | Replacement listed? |
|--------|----------------|-------------------------------|---------------------|
| Case overview | `2951427195113771286` | `docs/design/stitch/case-overview/DESIGN.md` | No — remains authoritative |
| Case reports tab | `2676660861211267049` | `docs/design/stitch/case-reports-tab/DESIGN.md` | No — remains authoritative |
| IEP / goal modal | — | `docs/design/stitch/iep-report/` + PNGs | No — remains authoritative |
| Observation | — | `docs/design/stitch/observation-report/observation_report_comprehensive_clinical_workspace/` | No — remains authoritative |

When replacing a reference, add a row here with the new file path and date. Do not delete the Stitch ID.

### Required states per clinical screen

Every builder and case-profile tab documents:

- Empty, loading, saving, saved, error/retry, read-only/preview, forbidden (no permission)

Submit for review never sets status to Complete from the client.

---

## Conflict resolution

Each row is a real contradiction found in docs and code. Requirements are not deleted; they are assigned an owner document.

| ID | Conflict | Evidence | Resolution | Authoritative |
|----|----------|----------|------------|---------------|
| C-01 | Forest Light is “therapist revamp only” vs this work making it product-wide | Previous UI_CONTRACT system table vs founder direction | Forest Light is the future product-wide foundation. Portals migrate in phases. Unmigrated surfaces keep current tokens. | This contract, Layer 2–3; [SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md) |
| C-02 | Five primaries: Forest black, indigo `#4f46e5`, admin teal `#0d9488`, login aqua `#2db7a7`, lush-forest `#0b1c16` | `forest-light-theme.css`, `index.css`, `admin-portal-mobile.css`, login, `clinical-report-ui.css` | Proposed primary is `#166534` after contrast check. Other hexes are legacy until the surface migrates. No global `:root` swap. | This contract, Layer 2 |
| C-03 | Forest `@theme` `--color-primary` vs vanilla `--primary` loaded app-wide | `main.jsx` imports both; most CSS uses `--primary` | New tokens scoped to migrated surfaces. Do not silently remap `--primary` for admin/parent in the therapist phase. | This contract, Layer 2; migration PRs |
| C-04 | Contract mandates `cov-*` case overview and `crt-*` reports tab | Files do not exist; `CaseDetailPage.jsx` is operational indigo | Label **migration planned**. Stitch specs stay authoritative. Do not invent a third overview widget. | Layer 4 + SURFACE_MIGRATION |
| C-05 | Legacy “purple clinical” system named (`clinical-theme.css`, `ClinicalCard`) | Files missing; buttons still emit `clinical-btn-*` | Do not rebuild a purple system. Treat leftover components as debt to restyle or remove on migration. | This contract, Design systems table |
| C-06 | Admin mobile guidance treats `#0d9488` as “InsighteCase colour” | `frontend/docs/admin-mobile-ux.md` | Teal remains valid for **unmigrated admin mobile pills**. Product primary is Forest green once admin migrates. | This contract; admin-mobile-ux (patterns only) |
| C-07 | IEP section titles: “Patient profile / Present levels / Talent development” vs JS titles | Previous UI_CONTRACT vs `clinicalUiContract.js` | JS titles are the UI copy (neuro-affirmative). Seven-section **order and keys** stay fixed. | Layer 4; `clinicalUiContract.js` |
| C-08 | Goal modal requires AI Assisted tab; runtime has two tabs | UI_CONTRACT vs `GOAL_MODAL_TABS` | Requirement stands. Implementation is backlog, not a doc deletion. AI remains on-demand. | Layer 4 |
| C-09 | Deferred: no Share / PDF / Duplicate; shell still has Download PDF and Share | `DEFERRED_ACTIONS`, `ClinicalBuilderShell.jsx`, `IepBuilderPage.jsx` | No API = no button. PDF/Share stay deferred until an endpoint is added to the API map. | Layer 4 API map |
| C-10 | Optimistic UI “always update local state immediately” vs clinical/finance confirmation | AGENTS.md Connection Before Correction | Immediate interaction feedback always. Clinical submit, approvals, and financial outcomes confirm only after server success. | Layer 1; AGENTS.md (clarified) |
| C-11 | Stitch DESIGN.md paths cited but missing | `docs/design/stitch/` absent | References stay authoritative. Record the gap; do not treat missing files as cancelled design. | Layer 4 Stitch table |
| C-12 | Typography: JetBrains Mono only for eyebrows vs `.cr-section__label` system monospace | FOREST_LIGHT_TYPOGRAPHY.md vs `clinical-report-ui.css` | Type doc stands. System monospace is a bug for the IEP migration. Do not expand mono usage. | FOREST_LIGHT_TYPOGRAPHY.md + Layer 2 |
| C-13 | “Patient” in old IEP labels vs neuro-affirmative “client” | Previous contract vs AGENTS.md | UI says client / child’s name. Key `child_context` unchanged. | Layer 1 and 4 |
| C-14 | Thumb-zone + timing caps vs oversized KPI cards, gradients, glass nav | AGENTS.md §5 vs `index.css` / parent hero / therapist tiles | Principles win. Decorative chrome is banned on migrated surfaces. | Layer 1–2 |
| C-15 | Goal modal two-column rail vs CSS hiding the rail below 768px | UI_CONTRACT vs `clinical-report-ui.css` | Rail content must remain reachable as a collapsible preview on small screens. | Layer 2 mobile + Layer 4 modal |
| C-16 | `window.prompt` forbidden vs still used | Previous verification list vs People, payouts, HR cases, observation | Ban stands. Replace in those surfaces’ migrations. | Layer 2 forms; UX_BACKLOG |
| C-17 | Cross-portal: no admin CSS on therapist/parent vs `admin-btn` used there | Skill vs `TherapistDashboardPage.jsx`, parent pages | Skill stands. Stop using `.admin-btn` when those portals migrate. | Layer 3; skill |
| C-18 | Duplicate Save/Submit in builder header and footer | `ClinicalBuilderShell.jsx` vs thumb-zone rule | One primary on mobile (footer). Header actions desktop-only. | Layer 2 buttons + Layer 4 shell |
| C-19 | Bottom nav offset 76px vs 72px vs parent 54px glass bar | `index.css` media queries | One `--portal-bottom-nav-offset` derived from the real bar; sticky footers sit above it. | Layer 2 mobile |
| C-20 | Finance docs say “use Forest Light standards” while finance UI is still operational indigo/teal | `docs/initiatives/finance-dashboard.md` | Finance follows this contract and migrates in **admin phase**, not by a one-off palette. | This contract; SURFACE_MIGRATION |
| C-21 | Handover route map incomplete vs `AppRoutes.jsx` | `docs/handover/08_FRONTEND.md` | Router is source of truth for the migration register. Handover should point here rather than drift. | SURFACE_MIGRATION; AppRoutes.jsx |
| C-22 | Login “Invalid credentials” / “Invalid Login. Use the correct portal.” | `portalLogin.js` vs banned strings | Replace with supportive portal-guidance copy. Do not weaken auth. | Layer 1 |
| C-23 | Admin density vs “calm workspace” | AGENT_WORKFLOW “data-rich admin” vs this direction | Admin stays dense on desktop (tables, queues). Calm means quieter colour, spacing, and type — not fewer columns. | Layer 3 admin |
| C-24 | Forest v1 black buttons vs proposed green primary | `#0b1c16` `.cr-btn--primary` vs `#166534` | IEP/observation stay Forest v1 until that screen’s migration explicitly remaps tokens. | SURFACE_MIGRATION |
| C-25 | Parent indigo glass bottom nav vs therapist forest-green tabs | `PortalShell` `--app` class | Intentional portal shells. After migration, both use Forest foundations with portal-specific nav content — not one shared purple bar. | Layer 3 |

---

## Verification before merge (documentation)

- [x] Four layers present; no second competing visual spec
- [x] Conflicts recorded with owners; requirements not silently dropped
- [x] API map, IEP seven sections, goal/strategy rules, deferred features, and no-fake-progress rules preserved
- [x] Optimistic UI clarified for clinical/finance confirmation
- [x] Stitch references retained
- [x] Proposed palette marked as requiring contrast verification
- [ ] Application CSS unchanged in this documentation phase

## Verification before merge (future implementation PRs)

- [ ] Surface appears in SURFACE_MIGRATION with status, routes, components, states, acceptance, rollback
- [ ] Goal modal still matches the six rules above
- [ ] IEP builder shows seven numbered sections in the listed order
- [ ] No `window.prompt`; no decorative buttons; no API-less Share/PDF/Duplicate
- [ ] Contrast verification recorded for any new token use
- [ ] `npm run build` passes
