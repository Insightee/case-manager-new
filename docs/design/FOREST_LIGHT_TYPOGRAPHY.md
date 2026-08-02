# Forest Light Typography

Canonical fonts for therapist portal revamp (Stitch: Modern Therapist Case Dashboard and related screens).

Source tokens: `frontend/src/styles/forest-light-theme.css`  
Loaded in: `frontend/index.html` (Google Fonts)

## Font roles

| Role | Family | CSS variable | When to use |
|------|--------|--------------|-------------|
| **Headline** | Manrope 600–700 | `--font-headline` | Client name, page titles, large emphasis |
| **Body** | Inter 400–500 | `--font-body` | Paragraphs, KV values, list items, buttons, meta text |
| **Label / section** | JetBrains Mono 500 | `--font-mono` | Card section titles (`PROFILE SNAPSHOT`), uppercase chips, pending action links |

## Rules (mandatory)

1. **Default to Inter** for all readable content — names, dates, descriptions, table/KV values, card body text.
2. **Manrope** only for headlines (h1–h2 client name, dashboard title).
3. **JetBrains Mono** only for:
   - Section card eyebrows (`cov-card__title`, uppercase tracking)
   - Small uppercase action links (e.g. pending `Complete`)
   - Interest tag text (optional; may use Inter semibold instead)
4. **Never** use monospace for KV pair values, summary paragraphs, goal titles, or care team names.
5. **Never** use legacy system monospace / Courier — always `var(--font-body)` or `var(--font-mono)` explicitly.

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
