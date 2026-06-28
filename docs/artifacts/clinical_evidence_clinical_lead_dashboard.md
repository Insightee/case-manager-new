# Clinical Lead Learning Dashboard (Pass 4 artifact)

_Status: artifact only — not implemented in Pass 1_

## Purpose

Organisation-wide learning from structured evidence — not from free-text notes or unreviewed AI output.

## Metrics (aggregated, de-identified where required)

| Metric | Contract fields |
|--------|-----------------|
| Most adapted strategies | `adaptation_type`, `strategy_feedback = NEEDS_ADAPTATION` |
| Strategies frequently needing adaptation | `strategy_id` + feedback counts |
| Environment-specific effectiveness | `environment` × `strategy_feedback` |
| Custom strategies created by therapists | `is_custom_strategy` frequency |
| Goal concepts with weak measurement | low `evidence_strength` rate by `goal_concept_id` |
| Environment barriers across cases | `barrier_type` distribution |
| Contradictory evidence patterns | same strategy + different `environment_fit` outcomes |

## Learning eligibility filter

Only include events where:
- `learning_eligibility` in (`eligible_now`, `deidentified_research_candidate`)
- `sensitivity_level == normal`
- `ai_learning_allowed == true`
- NOT `do_not_use_for_ai`

## Recommendation feedback loop (Pass 4)

When Clinical Brain suggests a strategy:
- Record `recommendation_feedback.was_brain_recommended = true`
- Capture `therapist_action` (accepted, dismissed_child_preference, etc.)
- Feed back into strategy pool confidence scores

## Dependencies

- Pass 2: sufficient structured capture volume
- Pass 3: CM-reviewed clean data pipeline
- Optional: snapshot table for query performance
