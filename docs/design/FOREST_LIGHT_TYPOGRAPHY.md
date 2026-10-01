# Forest Light Typography

Canonical fonts for Forest Light. **Colour, spacing, buttons, and layout live in the product contract:** [UI_CONTRACT.md](./UI_CONTRACT.md). This file does not define a second palette.

Source tokens (shipped Forest v1): `frontend/src/styles/forest-light-theme.css`  
Loaded in: `frontend/index.html` (Google Fonts)

Do not expand this document into a competing visual spec. If type roles change, update Layer 2 of the UI contract in the same PR.

## Font roles

| Role | Family | CSS variable | When to use |
|------|--------|--------------|-------------|
| **Headline** | Manrope 600–700 | `--font-headline` | Client name, page titles, large emphasis |
| **Body** | Inter 400–500 | `--font-body` | Paragraphs, KV values, list items, buttons, meta text |
| **Label / section** | JetBrains Mono 500 | `--font-mono` | **Existing approved eyebrows only** (`PROFILE SNAPSHOT`, small uppercase action links already using mono) |

## Rules (mandatory)

1. **Default to Inter** for all readable content — names, dates, descriptions, table/KV values, card body text.
2. **Manrope** only for headlines (h1–h2 client name, dashboard title).
3. **JetBrains Mono** only for:
   - Section card eyebrows (`cov-card__title`, uppercase tracking)
   - Small uppercase action links already in Forest v1 (e.g. pending `Complete`)
   - Interest tag text (optional; may use Inter semibold instead)
4. **Do not expand** uppercase monospace styling to new surfaces, table headers, goal titles, care-team names, or KV values.
5. **Never** use legacy system monospace / Courier / `ui-monospace` — always `var(--font-body)` or `var(--font-mono)` explicitly. `.cr-section__label` currently uses system monospace; that is a defect tracked in [UX_BACKLOG.md](./UX_BACKLOG.md) TH-ST-04.

## Examples

```css
/* Section eyebrow — mono OK */
.cov-card__title {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* KV label + value — both Inter */
.cov-kv dt,
.cov-kv dd {
  font-family: var(--font-body);
}

/* Client name in header */
.clinical-case-header__name {
  font-family: var(--font-headline);
}
```

## Case header layout (typography + structure)

Single `clinical-case-header__profile-row`:

- **Left (`__identity` → `__info`):** avatar, name, case code, then `__meta-row` with service badge + **status dropdown** + support
- **Right:** Change case button

Mobile: Change case `order: -1` at top-right; profile block below.

Status must live inside `__info` / `__meta-row` — not a separate `__actions` column.

This header structure remains the target for the therapist case profile migration ([SURFACE_MIGRATION.md](./SURFACE_MIGRATION.md) TH-03). It is not implemented as `CaseProfileShell` today.
