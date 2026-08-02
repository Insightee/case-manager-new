# Human Finance UAT Script — Stage 1 Finance Control Tower

**Prerequisite stamp:** `HUMAN_FINANCE_UAT_REQUIRED_BEFORE_MERGE`  
**Gate:** Gate 3 (after Gate 2 live staging is green)  
**Audience:** Finance user (e.g. Chandra) — complete **without** developer guidance  
**Environment:** Documented staging only (not production)  
**Flags expected:** `VITE_ENABLE_FINANCE_DASHBOARD_V1=true`, `FINANCE_CUTOVER_COMPLETE=false`, `BILLING_LEDGER_WRITES=false`

Route: `/admin/invoices?tab=overview`

For each task record: completed (yes/no), time (minutes), confusion, terminology questions, missing drill-downs, whether Excel was needed, requested changes.

| # | Task | Completed | Time | Confusion / notes | Excel needed? | Requested changes |
|---|------|-----------|------|-------------------|---------------|-------------------|
| 1 | Find all records ready for billing for the selected month | | | | | |
| 2 | Find cases missing package counts | | | | | |
| 3 | Find assignment gaps or overlaps | | | | | |
| 4 | Identify the largest **reliable** financial impact | | | | | |
| 5 | Explain why a selected KPI is Partial, Estimated, or Incomplete | | | | | |
| 6 | Drill from a card to its underlying records | | | | | |
| 7 | Return to Control Tower without losing the month filter | | | | | |
| 8 | Identify which figures are provisional before cutover | | | | | |
| 9 | Find payout-related holds | | | | | |
| 10 | Identify an unavailable section without losing the rest of the page | | | | | |

## Overall

- Would you trust these numbers for month-end prep (with provisional banner)? ___
- Could you operate without exporting to Excel? ___
- Ready to approve merge behind disabled production flags? ___

**Sign-off:** Name ____________ Date ____________  
**Outcome:** `STAGE_1_APPROVED_FOR_MERGE_BEHIND_FLAG` / `STAGE_1_REQUIRES_FIXES` / other: ____________
