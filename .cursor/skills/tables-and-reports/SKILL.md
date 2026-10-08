---
name: tables-and-reports
description: Rules for data tables, lists, dashboards, exports and clinical/finance reports in InsighteCase. Use when building or fixing any table, list view, metric card, CSV/PDF export, invoice or payout preview, session-log report, IEP/observation/progress report, or anything showing counts, totals, dates or rupee amounts.
---

# Tables and Reports (InsighteCase)

Wrong counts and totals destroy trust faster than any crash. Metric definitions live in `docs/REPORT_METRICS.md`; read the contract for the report you touch before changing it.

## Data tables

- **Mobile:** tables become cards below the breakpoint. Admin: `components/admin-portal/ui/AdminDataList` (`desktop` + `mobile` props), 900px breakpoint. Card shows the 2-3 fields a user acts on plus the primary action above the fold. No horizontal page scroll at 375px.
- **States, always all four:** loading (`components/shared/PageSkeleton` / `QueryState`), empty with guidance (`admin-portal/ui/AdminEmptyState` with `hints` + `action`), error with the real reason and a retry (`shared/ErrorBanner`), and data.
- **Sorting, filtering, pagination happen on the server** for anything that can exceed one page. Keep filters in the URL. Never compute a total from the current page only (finance previews show 50 rows; exports cap at `MAX_EXPORT_ROWS` 5000 - say when capped).
- Default sort is stated and stable (tie-break on id). Column headers say the unit.
- Sticky header on long tables; filters via `AdminStickyFilterRow` / `AdminCollapsibleFilters`.

## Dates and numbers

- **Business dates are IST** (Asia/Kolkata). Timestamp filters use half-open UTC intervals (start inclusive, end exclusive); date-only columns are not shifted. Use `frontend/src/lib/datetime.js` (`formatDateIN`, `formatDateTimeIN`, `formatTimeIST`, `formatDisplayDateRange`), never `toLocaleDateString()` without a zone. Backend: convert with the existing IST helpers, not naive `date.today()` on a UTC server.
- **Rupees:** `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })` via an existing helper: `lib/financeConfidence.js` `formatInr` (returns `null` for unknown) or `admin-portal/ui/adminUtils.js` `formatCurrency` (shows `—`). Do not add another helper. `components/invoices/invoiceUtils.js` `formatInr` turns `null` into ₹0, so do not use it for values that may be unknown.
- **Unknown is not zero.** A missing source is shown as "unavailable" / `—`, never 0. Zero means the query ran and found none.
- Counts use Indian grouping (1,23,456) consistently; percentages state their denominator.

## Reports and exports (clinical and finance)

- **Screen = export = PDF.** One backend query/service feeds the card, the table, the CSV and the PDF. If they can disagree, the PR is wrong. Add a test asserting the export total equals the screen total for the same filters.
- **Reconcile totals:** sum of rows = footer total = summary card; line items = invoice total; payouts per therapist sum to the payout run. Rounding happens once, at the end.
- **Correct counts:** define the grain (one row = one session / case x assignment window / invoice line) and dedupe on it. Cancelled, no-show, handover and late sessions follow the metric contract, not ad-hoc filters. Package cases with no session count are flagged as data exceptions (HTTP 422 + named case), not crashes and not zero.
- **Billing source of truth:** amounts come from the billing engine (`.cursor/rules/insighte-billing.mdc`); reports never recompute prices. Parents never see margin or payout; therapists never see client billing.
- **Clinical reports:** evidence counts come from one shared helper so the evidence panel, report builder and summaries match; follow `docs/design/UI_CONTRACT.md` for IEP/observation structure; AI may draft but never sets a report to Complete.
- **Scoping:** an export or PDF applies exactly the same role scope as the screen (see `security-review`).
- **Month-end:** anything feeding invoice preview/submit or the `invoice-month-end` cron must skip and report a bad row rather than fail the whole run.

## Verify

- Fixture test with known literal totals (not recomputed in the test).
- Check the same filters on screen, CSV and PDF; paste the three totals in the PR.
- Mobile card view checked at 375/390px (`mobile-responsive-qa`).
- Cross-portal: who sees this report (parent / therapist / admin) and with which columns (`cross-portal-impact`).
