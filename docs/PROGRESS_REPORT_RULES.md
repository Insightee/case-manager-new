# Progress Report Status Rules

Deterministic, neuro-affirmative goal statuses for the clinical_reports progress engine. Layer 1 only — no LLM inference.

## Status vocabulary

| Status | Meaning |
|--------|---------|
| **Emerging** | 1–2 approved sessions in the review period with weak or moderate evidence; early signal |
| **Building** | Moderate evidence strength, or an improving trend within the period |
| **Consistent** | Strong operational evidence plus stable or improving trend in the period |
| **Needs adapting** | `latest_trend == needs_support` in the period, or dominant negative strategy feedback |
| **Not enough evidence** | Zero approved sessions in the period for this goal |

## Evidence inputs (scoped)

All inputs are limited to the report `review_period_start` … `review_period_end` with `evidence_cutoff_at`:

- Session logs: `submitted_at` set, `approval_status = APPROVED`, session `scheduled_date` in period
- Goal/strategy events: linked to scoped `daily_log_id`s only
- Monthly reports: engine monthlies in `APPROVED` or `LOCKED` whose month overlaps the period

## Suggested vs final

Population and refresh set **suggested** fields only:

- `suggested_status`, `suggested_summary`

Therapists set **final** fields via `PATCH /reports/{id}/progress/goals/{goal_id}`:

- `final_status`, `final_summary`, `therapist_rationale`, `status_confirmed`

Submit requires every active goal to have `final_status` **or** confirmed `suggested_status`.

## Implementation

- Rules: `backend/app/services/progress_status_rules.py`
- Scoping: `backend/app/services/progress_evidence_scope_service.py`
- Orchestration: `backend/app/services/progress_report_service.py`
