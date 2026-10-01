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
| **3. Portal patterns** | Therapist, client/parent, admin shells, reusable page types | Navigation, portal task model, or page-type patterns change |
| **4. Screen contracts** | Canonical components, APIs, required actions, states | A screen, endpoint, or clinical workflow changes |

Companion files (not competing specs):

| File | Role |
|------|------|
| [FOREST_LIGHT_TYPOGRAPHY.md](./FOREST_LIGHT_TYPOGRAPHY.md) | Type roles and scale for Forest Light. Defers colour and layout here. |
| [SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md) | Legacy / migration planned / migrated register for real routes. |
| [UX_BACKLOG.md](./UX_BACKLOG.md) | Phased implementation backlog with acceptance criteria. |
| [../skills/cross-portal-product-design/SKILL.md](../skills/cross-portal-product-design/SKILL.md) | Role-matrix workflow when a feature spans portals. |
| [../../frontend/docs/admin-mobile-ux.md](../../frontend/docs/admin-mobile-ux.md) | Admin ≤900px layout patterns. Visual tokens defer here. |
| `frontend/src/lib/clinicalUiContract.js` | Runtime labels and section keys for IEP / goal modal. Must stay aligned with Layer 4. |

**Conflict rule:** When documents disagree, this contract wins for UI/UX. Clinical, API, permission, data, and workflow constraints in AGENTS.md and backend docs stay in force. See [Conflict resolution](#conflict-resolution).

**Historical vs acceptance:** Layer 4 Stitch rows are **historical design references**. They are preserved. They are **not** acceptance specifications until recovered or replaced. See [Design references](#design-references-historical-vs-acceptance).

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

---

## Design references (historical vs acceptance)

| Class | What it is | Can a PR claim visual compliance? |
|-------|------------|-----------------------------------|
| **Acceptance specification** | This contract’s behavioural rules, API map, page patterns, tokens, and any **available** visual artefact in the repo (shipped Forest v1 CSS, `clinicalUiContract.js`, attached PNGs that exist) | Yes, against those rules and files |
| **Historical design reference** | Stitch project IDs and `docs/design/stitch/**` paths | **No.** Preserve the citation. Do not pass “matches Stitch” until the file is recovered or a replacement is listed here |

Missing Stitch paths remain in Layer 4. Absence does not cancel the product intent. It **blocks visual-match acceptance**.

**Recovery or replacement (required before visual-match claims):**

1. Restore the `DESIGN.md` / PNGs into `docs/design/stitch/…`, or
2. Add a replacement row in Layer 4 with path, date, and what it supersedes (for example annotated screenshots of shipped Forest v1 IEP/observation, or a new spec section in this file).

Until then, implementation PRs accept against **behavioural** Layer 4 rules (section order, tabs, APIs, states) and Forest Light foundations — not against an unseen mock.

---

## Layer 1 — Product principles

Every portal follows these five principles. Portal shells, permissions, and task structures stay separate; the principles do not.

### Accessible

- Target **WCAG 2.2 Level AA** for contrast, keyboard, name/role/value, focus, resize, and reflow.
- Every control has a visible text label or an accessible name (`aria-label` / `aria-labelledby`).
- Keyboard users can reach every authorised action. Focus order follows reading order.
- Dialogs and sheets are modal to assistive technology (`role="dialog"`, labelled title, focus trap, return focus on close). Full-screen workspaces use a labelled document/main, not a fake dialog.
- Honour `prefers-reduced-motion`. Do not add animation that competes with clinical reading.
- **44×44 CSS pixels is the product standard** for interactive targets (see Layer 2). Compact desktop visuals are allowed only when the hit area remains 44px.
- **Zoom and reflow:** content remains usable at 200% zoom (WCAG 1.4.4). Reading and form layouts reflow at 320px CSS width without requiring two-axis scrolling except for justified comparison tables (WCAG 1.4.10).

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

- Prioritise the user’s current job (today’s work, next appointment, the queue in front of them). Secondary history sits behind a click.
- One primary action per view. Secondary actions are visually quieter.
- Progressive disclosure: show the current step.
- Primary actions sit in the thumb zone on mobile (sticky footer of a sheet or workspace), not only the top-right of a tall form.
- Do not hide authorised destinations from mobile navigation. Overflow is the labelled header **Menu** (☰) that already exists on therapist/parent, or a More sheet on admin pills — never an unreachable control.

**Usability targets (not truncation rules):** Session documentation, observation, and monthly verification should stay short enough for field work. Treat the historical 5 / 15 / 10 minute figures in AGENTS.md as **targets to measure**, not as a reason to hide clinical fields. Record a baseline (median time-to-complete, or a scripted walkthrough duration) **before** claiming an improvement. See [Usability targets](#usability-targets-and-baselines).

### Supportive (connection before correction)

Banned UI strings: `Invalid Form`, `Submission Failed`, `Missing Data`, `Invalid Login`, and `Invalid credentials` as the user-facing message.

Required pattern: guidance that names the **actual** problem and the next step. Do not reuse one sentence for every failure.

Login copy must match the failure class the client already distinguishes in `formatLoginErrorMessage` (`frontend/src/lib/portalLogin.js`):

| Failure | How it is known | User-facing guidance (required direction) |
|---------|-----------------|-------------------------------------------|
| Credentials do not match | API / mapped `invalid credentials` | “That email and password did not match. Try again, or reset your password.” |
| Wrong portal | Role does not match this sign-in page | “This account signs in through a different portal. Use the therapist, parent, or admin sign-in that matches your role.” |
| Network / timeout | Client timeout or fetch failure | “We couldn't reach InsighteCase. Check your connection and try again.” |
| Account disabled / invite required | API detail when present | Say that; offer support or invite help — not the portal-mismatch line |
| Other | Unmapped `detail` | Keep a generic “Sign-in didn't complete. Try again.” — never the mismatch sentence |

Other supportive lines still apply where they fit: “Looks like we still need a few details before we can save this.” / “Would you like to continue from where you left off?” / “Let's add one more observation.”

**Immediate feedback vs confirmed outcomes**

| Interaction | Client behaviour | When the user sees success |
|-------------|------------------|----------------------------|
| Filters, chips, tabs, navigation, draft field edits, expand/collapse | Update local state immediately | Immediately, then reconcile |
| Draft save | Show **Saving…**; keep the form editable; apply [draft integrity](#draft-integrity) | **Saved** only when the saved revision matches current content |
| Clinical or financial **commit** | Immediate press feedback; disable duplicate submit | Status changes after server success |

AI does not create clinical truth. Allowed: on-demand draft, summary, library match, pattern detection. Forbidden: setting report status to Complete, diagnosing, or overriding therapist input. Do not call LLM endpoints from `onChange`, `onScroll`, page load, or active typing.

---

## Layer 2 — Shared foundations

These tokens are the **proposed** Forest Light product foundation. They require contrast verification (WCAG 2.2 AA) before implementation. Until a surface is migrated, keep its current tokens.

### Colour (proposed — verify before implementation)

Green is for **primary actions and selection only**. Success, warning, error, and information use separate semantic colours plus text or an icon. Colour is never the only indicator.

| Role | Hex | Intended use |
|------|-----|--------------|
| Primary action | `#166534` | Primary buttons, key links on white |
| Hover / pressed | `#14532D` | Primary hover, active press |
| Selected surface | `#EAF3EC` | Selected rows, active chips, highlighted nav item background |
| Page background | `#F7F8F5` | Portal canvas |
| Surface | `#FFFFFF` | Cards, dialogs, tables, inputs |
| Main text | `#17211B` | Headings and body |
| Secondary text | `#526057` | Meta, captions, placeholders (verify vs 4.5:1 on page and surface) |

**Borders are three tokens, not one:**

| Token | Proposed starting hex | Role | Contrast rule |
|-------|----------------------|------|----------------|
| Decorative border | `#DDE4DE` | Card edges, section dividers, table grid that is not the only affordance | No 3:1 requirement |
| Control border | Proposed `#8A968D` (verify) | Default (unfocused) input, select, textarea, secondary button outline | **≥3:1** against the surface behind the control in the **default** state |
| Focus ring | Proposed `#166534` (verify vs white and `#F7F8F5`) | `:focus-visible` 2px offset 2px | **≥3:1** against adjacent background. Never `outline: none` without this ring |

Do not use decorative `#DDE4DE` as the only cue that a field is editable. Verify **default** control borders, not only focused controls.

**Contrast verification gate (must pass before CSS lands):**

| Pair | Minimum | Notes |
|------|---------|-------|
| `#166534` on `#FFFFFF` | 4.5:1 (text/UI) | Primary button is white label on `#166534` — also ≥4.5:1 |
| `#14532D` on `#FFFFFF` | 4.5:1 | Hover/pressed |
| `#17211B` on `#FFFFFF` and on `#F7F8F5` | 4.5:1 | Body text |
| `#17211B` on `#EAF3EC` | 4.5:1 | Text on selected surface |
| `#526057` on `#FFFFFF` and on `#F7F8F5` | 4.5:1 | If it fails, darken secondary text; do not keep the hex |
| `#166534` on `#EAF3EC` | 3:1 non-text / 4.5:1 if used as text | Selected chip with green label |
| Control border vs surface (unfocused) | 3:1 | Default inputs and secondary buttons |
| Focus ring vs adjacent background | 3:1 | Keyboard and tap focus |

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

**Type scale (product standard — use instead of one-off numeral caps):**

| Step | Size | Line height | Use |
|------|------|-------------|-----|
| Display | 1.75rem (28px) | 1.2 | Rare. Client name in a case header only |
| Title | 1.375rem (22px) | 1.3 | Page titles, dashboard heading |
| Metric | 1.25rem (20px) | 1.3 | Dashboard / queue counts (not 30px KPI numerals) |
| Body | 1rem (16px) | 1.5 | Reading, form values, table cells |
| Secondary | 0.875rem (14px) | 1.4 | Meta, captions, helper |
| Eyebrow | 0.75rem (12px) | 1.3 | Approved mono section labels only |

Do not introduce a larger step to make a dashboard “feel important.” Hierarchy comes from Title vs Body vs Secondary, weight, and spacing — not a third colour or a huge number.

Other type rules:

1. Default to Inter.
2. Do not expand uppercase monospace styling to new surfaces, table headers, goal titles, KV values, or care-team names.
3. Never use `ui-monospace`, Courier, or system monospace. Existing `.cr-section__label { font-family: ui-monospace }` is a defect to fix on that surface’s migration.
4. Therapist page titles use Manrope only after that surface migrates; until then, do not mix fonts inside one card.

### Spacing, radius, elevation, width

| Token | Value |
|-------|-------|
| Spacing scale | 4, 8, 12, 16, 24, 32, 48px |
| Control height / touch target | **44px product standard** at all breakpoints for buttons, tabs, nav items, and icon controls. ≥901px admin **row** actions may look 40px tall only if the hit area is still 44px |
| Control radius | ~8px |
| Surface radius | ~12px |
| Elevation | Decorative 1px border on cards. Shadow only for overlay (sheet/modal), max ~`0 8px 24px` at 12% opacity |
| Content width | Forms and reading columns max ~720px; operational tables use the full workbench; dashboards max ~1200px inner content |

Banned chrome: decorative gradients, glassmorphism (`backdrop-filter` on nav/cards), stacked ambient blobs, hover shadows on KPI tiles, unnecessary badges, looping animation.

### Icons

- Use **Material Symbols** consistently on migrated Forest surfaces (already used in observation stitch blocks).
- One icon set per portal chrome. Do not mix Material Symbols with ad-hoc PNG glyphs on the same toolbar.
- Icon-only buttons require an accessible name and a 44px target.

### Controls — buttons

One visual language per migrated surface. Until a shared `Button` primitive exists, new work on a migrating surface must still match these variants.

| Variant | Use | Appearance (proposed) | Label |
|---------|-----|----------------------|-------|
| **Primary** | The one forward action | Fill `#166534`, text `#FFFFFF`, 44px height, 8px radius | Verb + object when needed: “Save draft”, “Submit for review” |
| **Secondary** | Alternative safe action | White surface, **control** border, `#17211B` text | “Preview”, “Cancel” |
| **Tertiary** | Low-emphasis / inline | No fill, no heavy border, `#166534` or `#17211B` text | “Change case”, “View details” |
| **Destructive** | Irreversible or harmful | Error fill or error outline + text; never primary green | “Delete”, “Reject”, “Cancel session” |

Placement:

- One primary per view or sheet.
- On mobile, primary sits in the sticky footer of the sheet or workspace, padded with `env(safe-area-inset-bottom)`, and above the portal bottom nav when that nav is visible.
- Destructive is never adjacent to primary without a separator. Confirmation follows the [consequence policy](#consequence-based-confirmation).
- Header and footer must not duplicate the same primary on small screens. Desktop may keep a header action; mobile keeps the thumb-zone footer.

Interaction states (all variants):

| State | Behaviour |
|-------|-----------|
| Default | Contrast-verified fill/text; secondary uses **control border**, not decorative border |
| Hover | `#14532D` for primary; control-border darken for secondary |
| Focus | Focus-ring token, 2px, offset 2px |
| Selected | `#EAF3EC` background for toggles/chips/nav |
| Disabled | Opacity 0.5, `aria-disabled` or `disabled`, cursor not-allowed. Do not use `pointer-events: none` alone — the control must still explain why. |
| Loading | Disable the control, set `aria-busy="true"`, visible **Saving…** / **Submitting…**. Block double submit. |
| Error | Keep values; announce the guidance message; move focus to the first field that needs attention when the submit failed |

Do not introduce a fifth unnamed button colour. Parent/therapist screens must not keep using `.admin-btn` after they migrate.

### Consequence-based confirmation

Do not add a second “Are you sure?” after the user has already completed a review step. `window.confirm` / `window.prompt` remain forbidden; when a confirm **is** required, use a labelled dialog or sheet.

| Consequence | Confirm UI? | Examples |
|-------------|-------------|----------|
| Reversible, local, or draft | No | Save draft, filters, chips, expand, preview, print locally |
| Already reviewed in this flow | No extra dialog | Invoice preview drawer → Submit; IEP Preview → Submit for CM review; session log review screen → Submit log |
| Irreversible or hard to undo, and there was **no** review step | Yes — labelled dialog naming the outcome | Delete profile, deactivate user, cancel invite, remove invoice line |
| Affects another person’s clinical record or money, and there was **no** review step | Yes | Approve log from a list row; send payout; mark invoice paid if that screen is a single button |
| Destructive session/case change | Yes | Cancel session (stops timer, no log); close case |

A preview, composer breakdown, or “review sessions” step **is** the confirmation. Adding `window.confirm` on top is a defect.

### Draft integrity

Applies to session logs, IEP/observation drafts, goal modal, invoices in compose, and other multi-field editors.

| Rule | Behaviour |
|------|-----------|
| Local draft is current | Keystrokes update local state immediately. An in-flight save must not replace newer local edits with an older server payload. |
| Saved = this revision | **Saved** only if the last successful response’s revision (`updated_at` / etag / save id) corresponds to the content now on screen (hash or equivalent). If the user typed after save started, status stays **Unsaved** (or **Saving…** then **Unsaved**). |
| Failure preserves input | Network or validation failure does not clear fields. Offer **Try again**. |
| Navigate away | If dirty, ask whether to stay or leave. Offer save when a draft endpoint exists. Do not silently discard. |
| Session expiry (401) | Keep the form. Prompt to sign in again. Retry the save without requiring re-entry of fields. Persist to `sessionStorage` keyed by report/log id when the editor is long (IEP, observation, session log). |
| Upload recovery | Failed evidence upload keeps the chosen file and offers retry. Do not drop the rest of the form. |
| Conflicting edits | If the server’s `updated_at` is newer than the base revision this client loaded, show a conflict: keep local text visible; do not overwrite therapist/parent input with the remote copy without an explicit choice. |

### Forms and feedback

| State | Required UI |
|-------|-------------|
| Empty | Title + two concrete next steps (`AdminEmptyState` pattern: `hints` + `action`). No blank tables. |
| Loading (page) | Skeleton or labelled “Loading…” in the main region; do not replace the whole shell. |
| Saving | Control label **Saving…**; do not toast “Saved” yet |
| Saved | Only when draft integrity says the on-screen revision matches; optional “Saved just now” that is not clinical completion |
| Validation | Connection-before-correction copy; list the missing structured fields |
| Retry | After network failure, keep the form and offer **Try again** |

### Capabilities (no unsupported capability)

Do not ship a control that **looks** like it performs a capability the product does not support. Local, meaningful actions are allowed.

| Capability | Allowed? | Evidence in repo |
|------------|----------|------------------|
| Preview | Yes | In-app preview routes |
| Save draft | Yes | `POST /reports/{id}/save-draft` |
| Submit for CM review | Yes | `POST /reports/{id}/submit` |
| Download IEP PDF | Yes, when the user may call it | `GET /api/v1/reports/{id}/iep/pdf` via `apiDownload` |
| Share IEP with family | Yes, when the user may call it | `POST /api/v1/reports/{id}/share-with-parent` — still **admin/CM permission**, not a therapist-wide control |
| Print observation | Yes as **local print** | `window.print()` on observation preview — label it Print, not Export/Share |
| Duplicate plan | **No** | `DEFERRED_ACTIONS` includes `duplicate`; no endpoint |
| Fabricated progress % | **No** | Unless backed by real session evidence counts |
| Native `prompt` / `confirm` | **No** | Use labelled dialogs per consequence policy |

Hiding a button is not a security control. RBAC still comes from the backend.

### Navigation (shared)

- Desktop: persistent sidebar of authorised destinations. Active item uses selected surface + a 3px primary **bar or equivalent**, not colour alone.
- Mobile ≤900px: 3–4 bottom tabs for the portal’s top tasks. Overflow is the **header Menu (☰)** (`PortalShell` `app-mobile-topbar__menu`) which already opens for therapist and parent. Admin overflow is that drawer and/or `AdminMobilePillTabs` More.
- Tab **ids and URL params stay stable** when labels shorten on mobile.
- Back navigation inside a case returns to the case list or the previous case tab, not the portal home, unless the user came from home.
- Deep links use portal-correct paths (`notificationLinks.js` pattern).
- **Active state:** `NavLink` `end: true` on Home/Dashboard so a nested case route does not mark Home active. Selected = `#EAF3EC` + text colour + 3px indicator.

Each mobile item must document destination, purpose, active rule, and overflow access — see Layer 3 tables.

### Mobile patterns by task complexity

Breakpoint: **900px** (`frontend/docs/admin-mobile-ux.md`, `PortalShell`).

| Task complexity | Pattern | Use for | Do not use for |
|-----------------|---------|---------|----------------|
| **Short selection** | Bottom **sheet** (~40–70% of `100dvh`), sticky 44px actions, `safe-area-inset-bottom` | Status change, slot pick, confirm destructive (when required), filter chips, “more” actions | IEP/observation/session-log writing |
| **Medium form** | Sheet up to ~90dvh **or** full-screen if more than about four fields plus keyboard | Goal/strategy add, book/reschedule, leave request, people invite | Multi-section clinical plans |
| **Long editor** | **Full-screen workspace** inside the portal shell: section list, sticky workspace footer, preview rail collapsed (not removed) | IEP builder, observation builder, session log entry, invoice compose | Tiny pickers |
| **Browse list** | Cards (`AdminDataList` / equivalent). See table priorities below | Cases, logs, tickets, people | — |
| **Compare numbers** | Justified **comparison table** exception | Invoice line comparison, finance margin by case, attendance matrices | Default case/people lists |

**Table information priorities (cards, default):**

1. Identity (child / case code / person)
2. Status (text + chip)
3. The reason this row is in the list (due date, queue reason, amount)
4. Primary action

Secondary columns move into the card body or a details disclosure.

**Justified comparison-table exceptions:** the user’s job is comparing aligned columns (amounts, dates across people, margin %). Then:

- Horizontal scroll is allowed
- First identity column stays sticky
- A card or summary of the **focused/selected row** remains available
- Zoom/reflow: at 320px, the identity + primary metric still read without two-axis scroll; the full grid may scroll horizontally

| Chrome | ≤900px | ≥901px |
|--------|--------|--------|
| Filters | Sticky compact row or collapsible panel | Inline |
| Page padding | Account for bottom nav **once**. `--portal-bottom-nav-offset` must match the real tab bar | Sidebar width `--spacing-sidebar` (280px Forest v1) |
| Keyboard | Sticky actions sit above the visual viewport | Unchanged |

Safe-area: apply `env(safe-area-inset-*)` on the shell **or** the body, not both. Workspace footers use `bottom: var(--portal-bottom-nav-offset)`, never `bottom: 0` under a fixed tab bar.

### Accessibility (checklist for every migrated surface)

- [ ] Keyboard: tab, shift-tab, enter/space on buttons, escape closes dialogs/sheets
- [ ] `:focus-visible` uses the **focus ring** token; default inputs use the **control border** token
- [ ] Labels: every input, select, checkbox, icon button
- [ ] Dialogs/sheets: `role="dialog"`, `aria-modal="true"`, labelled title, focus trap
- [ ] Contrast verified for text, **unfocused** control borders, and focus rings
- [ ] Status is not colour-only (text or icon)
- [ ] `prefers-reduced-motion` respected
- [ ] Skip link to `#main-content` remains
- [ ] 200% zoom: no clipped primary actions
- [ ] 320px reflow: lists and editors read in one column (comparison tables excepted as above)
- [ ] 44px target on primary actions and nav items

### Usability targets and baselines

Do not claim a screen is “faster” or “calmer” without a recorded baseline.

| Target | Historical figure (AGENTS.md) | How to use it |
|--------|-------------------------------|---------------|
| Session log entry | < 5 minutes | Measure median time, or a scripted walkthrough, on `/therapist/logs` **before** restyle; compare after |
| New observation | < 15 minutes | Same on observation builder |
| Monthly report verification | < 10 minutes | Same on CM/admin report review |

Baselines live in the implementation PR (walkthrough notes or instrumentation). Missing baseline → no “improved speed” claim. Do not hide structured clinical fields to hit a number.

Task priority (what to put on a dashboard or first tab) beats a large metric tile.

---

## Layer 3 — Portal patterns

Share foundations and suitable components. Keep **separate portal shells**, RBAC, and task structures. Never ship an admin page into therapist/parent routes without a portal-specific wrapper ([cross-portal-product-design](../skills/cross-portal-product-design/SKILL.md)).

### Reusable page patterns

Every migrated screen maps to one pattern. Hierarchy: **title → context → primary work → secondary**. Density: therapist/parent comfortable; admin dense on desktop.

#### Task dashboard

| | |
|--|--|
| **Job** | What needs me now |
| **Hierarchy** | Greeting/context; unfinished tasks; today’s schedule; shortcuts |
| **Density** | Metric step for counts; Body for task rows. No Display-size KPIs |
| **Actions** | One primary (first unfinished task). Shortcuts are tertiary |
| **States** | Empty (no sessions today), loading, error/retry |
| **Responsive** | Single column ≤900px. Schedule is a list, not a multi-month grid |
| **Examples** | `/therapist`, `/parent`, `/admin/cm` |

#### Searchable list

| | |
|--|--|
| **Job** | Find and open a record |
| **Hierarchy** | Search/filters; results; row action |
| **Density** | Cards on mobile (table priorities). Tables ≥901px |
| **Actions** | Row opens detail. Bulk actions in a bar, not per-icon clutter |
| **States** | Empty, no matches, loading, error |
| **Responsive** | Sticky search. Filters collapse |
| **Examples** | `/therapist/cases`, `/admin/people`, `/admin/cases` |

#### Case detail

| | |
|--|--|
| **Job** | Work inside one case without losing context |
| **Hierarchy** | Identity header (name, code, status, change-case); tabs; tab body |
| **Density** | Overview is summary + pending work, not a second dashboard of fake % |
| **Actions** | Tab-specific. Back returns to the list |
| **States** | Forbidden, loading, empty tab |
| **Responsive** | Header stacks; tabs become pills or a compact select; no hidden authorised tabs |
| **Examples** | `/therapist/cases/:caseId`, `/admin/cases/:caseId`, `/parent/cases/:caseId` |

#### Clinical editor

| | |
|--|--|
| **Job** | Complete a structured plan or log |
| **Hierarchy** | Case context; section list; current section; workspace footer |
| **Density** | One section at a time on mobile. Desktop may show numbered section cards |
| **Actions** | Save draft; Preview; Submit for review (consequence policy: preview **is** review) |
| **States** | Draft integrity states + read-only/preview + forbidden |
| **Responsive** | Full-screen workspace, not a sheet. Rail becomes a disclosure |
| **Examples** | IEP builder, observation builder, session log form |

#### Operational queue

| | |
|--|--|
| **Job** | Process exceptions and comparisons |
| **Hierarchy** | Queue filters; count of needing action; rows |
| **Density** | Desktop tables OK. Mobile cards unless a comparison exception applies |
| **Actions** | Approve/reject per consequence policy; open record |
| **States** | Empty queue (success), loading, error |
| **Responsive** | `AdminDataList` default |
| **Examples** | `/admin/workbench`, `/admin/logs`, invoice/payout queues |

### Therapist navigation

**Job:** today’s work, assigned cases, session documentation, unfinished tasks.

**Home versus Today (resolved):** `/therapist` is the **Home** dashboard (schedule preview, logs due, critical cases). `/therapist/logs` is **Logs** (write session documentation). The current mobile label **Today** on `/therapist/logs` collides with Home’s “today’s work” copy. Target mobile labels: **Logs · Cases · Reports · Home**. Desktop keeps Dashboard / Session Logs.

Support mobile use without hiding necessary clinical information: case overview, goals, environment, and session evidence stay available; they may move into tabs, not disappear.

Case context lives at `/therapist/cases/:caseId` with `?tab=`. Back control returns to My Cases.

#### Therapist mobile items

Overflow for every non-tab item: header **Menu (☰)** → full `THERAPIST_NAV` plus profile and notifications (`PortalShell` drawer). Bottom-tab “Menu” control is unused while the header drawer is open — do not add a fifth tab; make ☰ discoverable.

| Item | Destination | Purpose | Active when | Overflow |
|------|-------------|---------|-------------|----------|
| **Logs** (today’s label **Today** → rename) | `/therapist/logs` | Document visits; 44px submit in workspace footer | Path is `/therapist/logs` | Tab |
| **Cases** | `/therapist/cases` | Open assigned cases | `/therapist/cases` without requiring a case id for exact list | Tab |
| **Reports** | `/therapist/reports` | Unfinished / monthly reports | `/therapist/reports` (not case-file builders unless that path prefixes — prefer `end` on the list) | Tab |
| **Home** | `/therapist` | Today’s overview and unfinished work | Exact `/therapist` (`end: true`) | Tab |
| Invoices | `/therapist/invoices` | Pay statements after case-by-case preview | Path match | ☰ |
| Support & Incidents | `/therapist/support` | Tickets, incidents, memos | Path match | ☰ |
| Meetings | `/therapist/meetings` | CM meetings | Path match | ☰ |
| Leave | `/therapist/leave` | Leave requests | Path match | ☰ |
| Scheduling | `/therapist/slots` | Availability / slots | Path match | ☰ |
| Profile | `/therapist/profile` | Own profile | Path match | ☰ footer |
| Notifications | `/therapist/notifications` | Alerts | Path match | ☰ footer + header bell |

### Client / parent navigation

**Job:** next steps, appointments, understandable updates, communication.

Copy is plain language. Progressive disclosure: do not dump IEP internals on the home card. Parent routes are read-oriented except booking, profile, and support writes allowed by API.

#### Booking versus Billing (evidence and assumption)

**Evidence (repo, not analytics):**

- Desktop `PARENT_NAV` places **Session schedule** (`/parent/book`) *before* Billing.
- Parent guide leads with book/reschedule/cancel and dashboard **next session** + Book a session.
- `ClientDashboardPage` primary next-session CTA goes to `/parent/book`. Billing appears as an **alert banner** only when invoices are overdue or awaiting payment.
- Current `PARENT_MOBILE_NAV` puts **Billing** on the tab bar and leaves Book in the drawer — opposite the desktop order.

**Decision for the contract:** keep four bottom tabs. Target: **Home · Sessions · Schedule · Reports**. **Billing** moves to ☰ plus Home alerts when amounts are due. Appointments are the standing weekly task; billing is episodic and already surfaced when it needs action.

**Assumption (needs user research or runtime usage):** we do not have parent tap-count analytics in this repo. If research shows billing is the more frequent mobile task, restore Billing as a tab and keep Schedule in ☰ — record that finding here before swapping. Do not swap on taste.

#### Parent mobile items

Overflow: header ☰ → full `PARENT_NAV` plus notifications.

| Item | Destination | Purpose | Active when | Overflow |
|------|-------------|---------|-------------|----------|
| **Home** | `/parent` | Next step, next appointment, alerts | Exact `/parent` (`end: true`) | Tab |
| **Sessions** | `/parent/session-logs` | Understandable visit updates | Path match | Tab |
| **Schedule** (target tab; currently drawer) | `/parent/book` | Book / reschedule / see appointments | Path match | Tab (target) / ☰ (current) |
| **Reports** | `/parent/reports` | Reports, IEP, documents | Path match | Tab |
| **Billing** (target ☰; currently tab) | `/parent/billing` | Statements and pay | Path match | ☰ (target) / tab (current) |
| Profile | `/parent/profile` | Family profile / address | Path match | ☰ |
| Support | `/parent/support` | Communication | Path match | ☰ |
| Meetings | `/parent/meetings` | CM meetings (read/join, not therapy book) | Path match | ☰ |
| Case hub | `/parent/cases/:caseId` | One child’s file | Path + tab | Not in global nav; Home/notifications |
| Notifications | `/parent/notifications` | Alerts | Path match | ☰ + bell |

### Admin (including CM, finance, HR, SPOT)

**Job:** queues, search, filters, comparisons, operational actions.

Preserve useful **desktop table density** and the existing mobile patterns in [admin-mobile-ux.md](../../frontend/docs/admin-mobile-ux.md):

- `PortalTabBar` desktop; `AdminMobilePillTabs` mobile
- `AdminStickyFilterRow` / `AdminCollapsibleFilters`
- `AdminDataList` + `AdminTaskCard`
- `AdminEmptyState` with hints + action

Admin teal pills stay until that chrome migrates. Do not restyle all admin tables in the therapist phase.

Case managers review exceptions, not data entry. Queue trigger vectors in AGENTS.md stay unchanged.

#### Admin mobile items (CM-focused)

Overflow: header ☰ lists remaining `caseManagerNav` destinations. Bottom tabs:

| Item | Destination | Purpose | Active when | Overflow |
|------|-------------|---------|-------------|----------|
| Dashboard | `/admin/cm` | CM home | `end: true` | Tab |
| Cases | `/admin/cases` | Caseload | Path match | Tab |
| Review | `/admin/workbench` | Exception queues | Path match | Tab |
| Session Logs, Reports, IEP, Meetings, Support, Attendance | respective `/admin/…` routes | Operational | Path match | ☰ |

Full admin (module admin / finance / HR): `buildMobileTabs` keeps up to three of home / cases / reports and sets `useMenu: true` → ☰ for the rest. Finance comparison screens may use the comparison-table exception.

SPOT-only: three tabs (Dashboard, Attendance, Leave), no drawer.

### Login (public)

Role-aware entry remains: `/login` selector plus `/therapistlogin`, `/clientlogin` (`/clinetlogin` alias), `/adminlogin`, `/devlogin`. Keep three visible portals. Visual migration of login is **phase 2/3**, not a blocker for therapist clinical surfaces. Copy follows the login failure table in Layer 1.

---

## Layer 4 — Screen contracts

If a screen is not in this layer, do not ship a new layout for it. Add the screen here first.

### Canonical components (one implementation each)

| Surface | Canonical component | Used by | Implementation status |
|---------|---------------------|---------|------------------------|
| Goal / strategy create | `StudentGoalCreateModal.jsx` | IEP builder, observation builder, session log | Exists. Tabs in JS: Templates, Custom. AI tab required below — missing in runtime. Medium-form **sheet** on mobile (not a tiny centered modal). |
| Report builder header + footer | `ClinicalBuilderShell.jsx` | IEP, observation | Exists. Long-editor workspace. Header **and** footer both expose Save / Preview / Submit — mobile should keep footer only. |
| Section numbering + cards | `clinical-report-ui.css` + `IEP_BUILDER_SECTIONS` | IEP | Exists |
| Observation blocks | `ObservationStitchBlocks.jsx` | Observation only | Exists |
| Case overview (therapist) | Target: Forest overview on `/therapist/cases/:caseId?tab=overview` | Case profile | **Not implemented.** No `TherapistCaseOverviewDashboard.jsx`, `case-overview-v2.css`, `cov-*`, or `CaseProfileShell`. Live UI is inline in `CaseDetailPage.jsx`. Visual-match to Stitch is **blocked** until recovery/replacement. |
| Case reports tab (therapist) | Target: reports section on the case profile | Case profile | **Not implemented.** No `CaseReportsTab.jsx`. Reports live at `/therapist/reports` and clinical builders under `/therapist/reports/cases/:caseId/{observation\|iep}`. Visual-match blocked until recovery/replacement. |

Do not import or render unstyled `ClinicalCard` / `ClinicalMetricCard` (they do not exist). Forest surfaces must not use `ClinicalStatusBadge` once a Forest status chip exists. Until then, do not add new `ClinicalStatusBadge` call sites.

### Create Student Goal modal (non-negotiable behaviour)

Behavioural acceptance (does **not** require Stitch files):

1. **Tabs:** Templates · Custom goal · AI Assisted
2. **Templates:** search repository, domain chips, Goals/Strategies toggle, Add/Select per row
3. **Custom:** domain grid, IEP-language goal statement, supports field
4. **AI:** on-demand generate → list drafts → Add (never on page load or `onChange`)
5. **Preview:** statement summary, active strategies, clinical environment. On ≤900px this is a disclosure inside the medium-form sheet — it must remain reachable.
6. **Pre-selected goal:** when adding a strategy, all adds link to that goal

Visual-match to `docs/design/stitch/iep-report/` is historical until that folder is recovered or replaced.

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

Pattern: **clinical editor** (full-screen workspace). Footer: Save draft · Preview · **Submit for CM review** (`POST /reports/{id}/submit`). Preview is the review step — no extra confirm dialog.

On viewports ≤900px, those three actions exist once, in the workspace footer, above the portal bottom nav.

PDF download and share-with-family are **supported capabilities** when the user is authorised (see API map). Duplicate is not.

### Observation builder

Pattern: **clinical editor**. Historical Stitch path remains cited below; shipped approximation is `ObservationStitchBlocks.jsx` + `forest-light-observation.css` (acceptance for Forest v1 behaviour). Visual-match to missing Stitch folder is blocked.

Parent `variant="parent"` is preview/read. Do not expose builder write controls to parents. Print is local print.

### Fabricated progress

- No fake progress % on goals unless backed by real session evidence counts.

### API map (frontend must use these)

| UI | Endpoint / local capability |
|----|------------------------------|
| Template search | `GET /cases/{id}/clinical/repository-search?q=&kind=goals\|strategies&domain=` |
| AI drafts | `POST /reports/{id}/clinical/generate-goal-strategy-drafts` |
| Add IEP goal | `POST /reports/{id}/iep/goals` |
| Link strategy | `POST /reports/{id}/iep/goals/{gid}/strategies` |
| Save draft | `POST /reports/{id}/save-draft` |
| Submit | `POST /reports/{id}/submit` |
| Share IEP with family | `POST /reports/{id}/share-with-parent` (authorised roles only) |
| Download IEP PDF | `GET /reports/{id}/iep/pdf` |
| Case reports summary | `GET /cases/{id}/reports/summary` |
| Print observation | Local `window.print()` — not a server export |
| Duplicate plan | **Unsupported** — no control |

Do not add UI that writes clinical truth through a different path. RBAC and case scope still come from the backend.

### Stitch project references (historical — not acceptance until recovered)

| Screen | Stitch project | Spec path (missing from repo) | Replacement listed? | Acceptance today |
|--------|----------------|-------------------------------|---------------------|------------------|
| Case overview | `2951427195113771286` | `docs/design/stitch/case-overview/DESIGN.md` | No | Behavioural case-detail + Forest foundations only |
| Case reports tab | `2676660861211267049` | `docs/design/stitch/case-reports-tab/DESIGN.md` | No | Keep reports at `/therapist/reports` until a tab is specified **and** a visual reference exists |
| IEP / goal modal | — | `docs/design/stitch/iep-report/` + PNGs | No | Behavioural six rules + `clinicalUiContract.js` |
| Observation | — | `docs/design/stitch/observation-report/observation_report_comprehensive_clinical_workspace/` | No | Shipped Forest v1 observation CSS/components |

When replacing a reference, add a row here with the new file path and date. Do not delete the Stitch ID.

### Required states per clinical screen

Every builder and case-profile tab documents:

- Empty, loading, saving, saved (revision-accurate), error/retry, dirty/navigate-away, conflict, read-only/preview, forbidden (no permission)

Submit for review never sets status to Complete from the client.

---

## Conflict resolution

Each row is a real contradiction found in docs and code. Requirements are not deleted; they are assigned an owner document.

| ID | Conflict | Evidence | Resolution | Authoritative |
|----|----------|----------|------------|---------------|
| C-01 | Forest Light is “therapist revamp only” vs this work making it product-wide | Previous UI_CONTRACT system table vs founder direction | Forest Light is the future product-wide foundation. Portals migrate in phases. Unmigrated surfaces keep current tokens. | This contract, Layer 2–3; [SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md) |
| C-02 | Five primaries: Forest black, indigo `#4f46e5`, admin teal `#0d9488`, login aqua `#2db7a7`, lush-forest `#0b1c16` | `forest-light-theme.css`, `index.css`, `admin-portal-mobile.css`, login, `clinical-report-ui.css` | Proposed primary is `#166534` after contrast check. Other hexes are legacy until the surface migrates. No global `:root` swap. | This contract, Layer 2 |
| C-03 | Forest `@theme` `--color-primary` vs vanilla `--primary` loaded app-wide | `main.jsx` imports both; most CSS uses `--primary` | New tokens scoped to migrated surfaces. Do not silently remap `--primary` for admin/parent in the therapist phase. | This contract, Layer 2; migration PRs |
| C-04 | Contract mandates `cov-*` case overview and `crt-*` reports tab | Files do not exist; `CaseDetailPage.jsx` is operational indigo | **Migration planned.** Stitch is historical; visual-match blocked until recovery. Do not invent a third overview widget. | Layer 4 + SURFACE_MIGRATION |
| C-05 | Legacy “purple clinical” system named (`clinical-theme.css`, `ClinicalCard`) | Files missing; buttons still emit `clinical-btn-*` | Do not rebuild a purple system. Treat leftover components as debt to restyle or remove on migration. | This contract, Design systems table |
| C-06 | Admin mobile guidance treats `#0d9488` as “InsighteCase colour” | `frontend/docs/admin-mobile-ux.md` | Teal remains valid for **unmigrated admin mobile pills**. Product primary is Forest green once admin migrates. | This contract; admin-mobile-ux (patterns only) |
| C-07 | IEP section titles: “Patient profile / Present levels / Talent development” vs JS titles | Previous UI_CONTRACT vs `clinicalUiContract.js` | JS titles are the UI copy (neuro-affirmative). Seven-section **order and keys** stay fixed. | Layer 4; `clinicalUiContract.js` |
| C-08 | Goal modal requires AI Assisted tab; runtime has two tabs | UI_CONTRACT vs `GOAL_MODAL_TABS` | Requirement stands. Implementation is backlog, not a doc deletion. AI remains on-demand. | Layer 4 |
| C-09 | “No API = no button” vs existing IEP PDF and share endpoints; observation print | `useIepReport.js` `iep/pdf`, `share-with-parent`; observation `window.print()` | **No unsupported capability.** PDF/share allowed when authorised. Print is local. Duplicate remains unsupported. | Layer 2 capabilities + Layer 4 API map |
| C-10 | Optimistic UI “always” vs clinical/finance confirmation | AGENTS.md | Immediate feedback for drafts/filters. Commits wait for the server. Confirmation is **consequence-based**, not blanket. | Layer 1–2 |
| C-11 | Stitch DESIGN.md paths cited but missing | `docs/design/stitch/` absent | Historical references kept. Visual compliance cannot be claimed until recovery or replacement. | Design references section |
| C-12 | Typography: JetBrains Mono only for eyebrows vs `.cr-section__label` system monospace | FOREST_LIGHT_TYPOGRAPHY.md vs `clinical-report-ui.css` | Type doc stands. System monospace is a bug for the IEP migration. Do not expand mono usage. | FOREST_LIGHT_TYPOGRAPHY.md + Layer 2 |
| C-13 | “Patient” in old IEP labels vs neuro-affirmative “client” | Previous contract vs AGENTS.md | UI says client / child’s name. Key `child_context` unchanged. | Layer 1 and 4 |
| C-14 | Timing caps / huge KPI tiles vs field work | AGENTS.md §5 vs `index.css` | Caps are **measurable targets** with baselines. Type scale replaces numeral caps. Decorative chrome still banned. | Layer 1–2 usability + type scale |
| C-15 | Goal modal two-column rail vs CSS hiding the rail below 768px | UI_CONTRACT vs `clinical-report-ui.css` | Medium-form sheet; preview is a disclosure, always reachable. | Layer 2 mobile + Layer 4 modal |
| C-16 | `window.prompt` / `window.confirm` vs labelled dialogs | People, payouts, HR, observation, DailyLogsPage | Ban stands. Use consequence policy. | Layer 2 |
| C-17 | Cross-portal: no admin CSS on therapist/parent vs `admin-btn` used there | Skill vs `TherapistDashboardPage.jsx`, parent pages | Skill stands. Stop using `.admin-btn` when those portals migrate. | Layer 3; skill |
| C-18 | Duplicate Save/Submit in builder header and footer | `ClinicalBuilderShell.jsx` vs thumb-zone rule | One primary on mobile (footer). Header actions desktop-only. | Layer 2 buttons + Layer 4 shell |
| C-19 | Bottom nav offset 76px vs 72px vs parent 54px glass bar | `index.css` media queries | One `--portal-bottom-nav-offset` derived from the real bar; workspace footers sit above it. | Layer 2 mobile |
| C-20 | Finance docs say “use Forest Light standards” while finance UI is still operational indigo/teal | `docs/initiatives/finance-dashboard.md` | Finance follows this contract and migrates in **admin phase**. | This contract; SURFACE_MIGRATION |
| C-21 | Handover route map incomplete vs `AppRoutes.jsx` | `docs/handover/08_FRONTEND.md` | Router is source of truth for the migration register. | SURFACE_MIGRATION; AppRoutes.jsx |
| C-22 | One login string for every failure | `portalLogin.js` maps credentials vs portal separately but UI still says “Invalid …” | Guidance **corresponds to the actual failure**. Do not use mismatch copy for bad passwords. | Layer 1 login table |
| C-23 | Admin density vs “calm workspace” | AGENT_WORKFLOW “data-rich admin” vs this direction | Admin stays dense on desktop. Calm means quieter colour, spacing, and type — not fewer columns. Comparison tables are a justified exception. | Layer 3 admin |
| C-24 | Forest v1 black buttons vs proposed green primary | `#0b1c16` `.cr-btn--primary` vs `#166534` | IEP/observation stay Forest v1 until that screen’s migration explicitly remaps tokens. | SURFACE_MIGRATION |
| C-25 | Parent indigo glass bottom nav vs therapist forest-green tabs | `PortalShell` `--app` class | Intentional portal shells. After migration, both use Forest foundations with portal-specific nav content. | Layer 3 |
| C-26 | Mobile **Today** = logs vs Home = today’s work | `THERAPIST_MOBILE_NAV` vs dashboard copy | Rename tab to **Logs**. Home remains `/therapist`. | Layer 3 therapist |
| C-27 | Parent Billing on tab bar vs Book in drawer | `PARENT_MOBILE_NAV` vs desktop nav + parent guide + home CTA | Target: Schedule on tabs; Billing in ☰ + Home alerts. Assumption marked pending research. | Layer 3 parent |
| C-28 | Single border hex for cards and inputs | Previous Layer 2 `#DDE4DE` for all | Decorative vs control vs focus tokens. Verify **default** controls. | Layer 2 colour |
| C-29 | All dialogs as bottom sheets vs long clinical editors | Previous mobile table | Sheets for short/medium tasks; full-screen workspaces for long editors. | Layer 2 task complexity |
| C-30 | Extra confirm after invoice/IEP preview | `window.confirm` in several flows vs preview drawers | Consequence policy: no duplicate confirm after a review step. | Layer 2 confirmation |

---

## Decisions needing runtime inspection or user research

| ID | Decision | What we used | What is still needed |
|----|----------|--------------|----------------------|
| R-01 | Parent **Schedule** vs **Billing** on the tab bar | Desktop nav order, parent guide, home CTA vs billing-as-alert | Parent usage analytics or research before reversing the target |
| R-02 | Therapist Home vs Logs labels | Dashboard copy and routes | Confirm with therapists that “Logs” is clearer than “Today” |
| R-03 | Control-border hex `#8A968D` | Proposed for 3:1 on white | Measure contrast on `#FFFFFF` and `#F7F8F5` before CSS |
| R-04 | Secondary text `#526057` | Proposed | AA contrast on page and surface |
| R-05 | Session-log / observation / report duration targets | Historical 5 / 15 / 10 min | Baseline measurement on current UI before claiming improvement |
| R-06 | Stitch visual intent for case overview / reports tab | Project IDs only | Recover files or replace with dated artefacts |
| R-07 | Draft conflict UX (keep local vs show both) | Principle: never silently overwrite therapist input | Confirm with a real concurrent-edit case if CM and therapist can both PATCH the same report |
| R-08 | Header ☰ discoverability | Code: therapist/parent already have `app-mobile-topbar__menu` | Watch whether users find invoices/support; do not add a fifth tab without evidence |

---

## Verification before merge (documentation)

- [x] Four layers present; no second competing visual spec
- [x] Historical Stitch citations preserved; visual-match blocked until recovery
- [x] Conflicts recorded with owners; requirements not silently dropped
- [x] API map includes save-draft, IEP PDF, share-with-parent; duplicate still unsupported
- [x] Confirmation is consequence-based; login copy is failure-specific
- [x] Proposed palette marked as requiring contrast verification including default control borders
- [ ] Application CSS unchanged in this documentation phase

## Verification before merge (future implementation PRs)

- [ ] Surface appears in SURFACE_MIGRATION with status, routes, components, states, acceptance, rollback
- [ ] Page maps to a Layer 3 pattern (dashboard, list, case detail, clinical editor, queue)
- [ ] Goal modal still matches the six behavioural rules
- [ ] IEP builder shows seven numbered sections in the listed order
- [ ] No `window.prompt` / `window.confirm`; no unsupported Duplicate; no extra confirm after preview
- [ ] Visual-match to Stitch claimed **only** if the artefact exists or a replacement is listed
- [ ] Contrast verification recorded for text, unfocused control borders, and focus rings
- [ ] 44px targets; 200% zoom and 320px reflow checked
- [ ] Baseline recorded if claiming a usability improvement
- [ ] `npm run build` passes
