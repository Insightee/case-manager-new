# Clinical Evidence Event Contract

_Last updated: June 2026 · Pass 1 implemented_

## Purpose

The **ClinicalEvidenceEventContract** is the atomic unit of structured clinical learning in InsighteCase. It is a **logical contract** materialized from existing rows — primarily `session_goal_entries` and `strategy_use_events` — not a third parallel evidence store in V1.

```text
goal → strategy/support → environment → activity → participation → therapist interpretation
```

The Clinical Brain, monthly report compiler (Pass 3), and IEP review must consume **materialized contract objects**, not raw session prose or report HTML.

## Contract version

| Field | Value |
|-------|-------|
| `contract_version` | `1.1.0` |
| `contract_status` | `active` |
| Schema artifact | [`backend/app/schemas/clinical_evidence_event_contract.json`](../backend/app/schemas/clinical_evidence_event_contract.json) |
| Materializer | [`backend/app/services/clinical_evidence_event_service.py`](../backend/app/services/clinical_evidence_event_service.py) |
| Enums | [`backend/app/core/clinical_evidence_contract.py`](../backend/app/core/clinical_evidence_contract.py) |

## What is evidence (Pass 1)

| Source | Materialized? |
|--------|---------------|
| `SessionGoalEntry` structured fields | Yes |
| `StrategyUseEvent` structured fields | Yes |
| Linked goal + strategy pairs | Yes (one event per pair) |
| Goal-only rows (no strategy) | Yes (with completeness gaps noted) |
| `DailyLog.session_notes` prose | **No** |
| Report HTML / narrative sections | **No** |
| `GoalEvidenceEvent.summary` rollup | **No** (backward-compat only) |
| `ai_draft_outputs` | **No** unless human-accepted (Pass 1: never read) |

## Materialization rules

1. **`evidence_event_id`**: stable UUID5 from `(goal_entry_id, strategy_use_event_id)`.
2. **`goal_concept_id`**: deterministic hash from goal card / repository id + normalized title.
3. **One event per linked (goal, strategy) pair**; goal-only when no strategy linked.
4. **Do not infer** `child_response`, `regulation_signal`, `child_agency_signal`, `environment_fit`, or `barrier_type` from free-text notes or AI in Pass 1.
5. **Safe derivation only** from structured fields:
   - `participation_signal` ← participation enum or 0–4 score
   - `participation_quality` ← participation enum (direct map)
   - `therapist_interpretation` ← `strategy_feedback` enum
   - `environment` ← normalized structured environment value

## evidence_strength (internal only)

`evidence_strength` (`weak` | `moderate` | `strong`) measures **structured data completeness**, not clinical success or goal achievement.

- It is flagged `evidence_strength_internal_only: true`.
- It must **never** be parent-visible.
- It must **not** decide goal achievement or strategy success by itself.
- CM dashboards may use it to queue review, not to label the child.

## Parent-facing language rules

When translating internal evidence to parent-safe language (Pass 3 report preview):

**Do describe:**
- Support provided (visual schedule, extra time, choice)
- Context and environment (crowded corridor vs calm classroom)
- Participation patterns (engaged with support, needed preparation)
- Team adaptations and next steps

**Do not use:**
- Deficit labels (“non-compliant”, “failed”, “refused task”)
- Compliance framing (“did not follow instructions”)
- Blame language (“child chose not to…”)
- Strategy success/failure without environment context

**Example:**

| Internal | Parent-safe |
|----------|-------------|
| Child became overwhelmed during noisy corridor transition | Transitions in crowded spaces were harder this month. The team is adjusting the environment and giving more preparation time. |

## Visibility and learning gates

| Field | Default (Pass 1) |
|-------|------------------|
| `parent_visible` | `false` |
| `sensitivity_level` | `normal` |
| `learning_eligibility` | `eligible_after_review` |
| `ai_learning_allowed` | computed from sensitivity + eligibility |

Sensitive evidence (`safeguarding_related`, `do_not_use_for_ai`) is never parent-visible and excluded from Clinical Brain learning.

## V1.1 optional fields (schema reservation — V2 UI capture)

These fields exist in the contract schema with `"capture_status": "v2_ui"`. Pass 1 returns `null` / `[]` unless safely derived from structured rows:

- `child_agency_signal`
- `participation_quality` (may be system_derived from participation enum)
- `environment_fit`
- `barrier_type`
- `adaptation_type` / `adaptation_note`
- `child_preference_signal`
- `field_provenance` (populated for system-derived fields in Pass 1)
- `recommendation_feedback` (Pass 4 learning loop)

See [`docs/artifacts/clinical_evidence_v2_ui_spec.md`](artifacts/clinical_evidence_v2_ui_spec.md).

## API (read-only, Pass 1)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/daily-logs/{log_id}/clinical-evidence-events` | Materialize events for one log |
| `GET /api/v1/cases/{case_id}/clinical-evidence-events?month=YYYY-MM` | Materialize + rollup for case month |

RBAC: same case scope as daily logs.

## Consumers (Pass 1)

- `clinical_brain_evidence_service.summarize_report_evidence()` — uses materialized events + rollup
- Tests: `backend/app/tests/test_clinical_evidence_event.py`

**Not wired yet (by design):**
- Monthly report compiler
- `goal_evidence_aggregation_service`
- Frontend session log UI

## Future: snapshot cache

If aggregation becomes slow, add `clinical_evidence_event_snapshots` (cache only, not source of truth). See [`docs/artifacts/clinical_evidence_snapshot_table.md`](artifacts/clinical_evidence_snapshot_table.md).

## Related docs

- [`docs/CLINICAL_EVIDENCE_ROADMAP.md`](CLINICAL_EVIDENCE_ROADMAP.md) — Pass 2–4 plan
- [`docs/REPORT_ARCHITECTURE.md`](REPORT_ARCHITECTURE.md) — report engine strangler
