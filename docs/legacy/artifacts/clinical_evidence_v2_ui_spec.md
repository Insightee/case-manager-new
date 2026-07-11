> **STATUS: SUPERSEDED** — retained only for historical and migration context. Do not use this document for new implementation.

# Clinical Evidence V2 UI Spec (frozen for implementation)

_Status: artifact only — not implemented in Pass 1_

## Component target

Extend existing session log evidence surfaces:
- `frontend/src/components/session-log/SessionLogEvidencePanel.jsx`
- `frontend/src/components/session-log/GoalSessionCard.jsx`

## Evidence card per goal

```text
Goal addressed
Strategy/support used
Where did this happen?
What was the activity?
How did the child participate?
What support helped?
How did the child respond?
What should we do next?
```

## Chip → contract field mapping

| UI chip group | Contract field | Required V2 |
|---------------|----------------|-------------|
| Child response | `support_and_response.child_response` | Recommended |
| Regulation | `support_and_response.regulation_signal` | Optional |
| Participation | `support_and_response.participation_signal` | Already derived; allow override |
| Child agency | `support_and_response.child_agency_signal` | Recommended |
| Participation quality | `support_and_response.participation_quality` | Optional |
| Environment fit | `context.environment_fit` | Recommended |
| Barriers | `context.barrier_type[]` | Advanced |
| Adaptation type | `strategy_linkage.adaptation_type[]` | When feedback = NEEDS_ADAPTATION |
| Adaptation note | `strategy_linkage.adaptation_note` | Optional text |
| Next step | `therapist_view.therapist_interpretation` | Recommended |
| Sensitive | `visibility_and_governance.sensitivity_level` | Advanced |

## Save payload extension (backend V2)

Add optional fields to goal/strategy items in `SessionEvidenceSave`. On save:
- Write to structured columns or JSON blob on `SessionGoalEntry` / `StrategyUseEvent`
- Set `field_provenance[field] = human_selected`

## UX constraints

- Session log evidence entry target: under 5 minutes total
- 44px touch targets
- Sticky footer save in thumb zone
- No LLM on chip `onChange` — token economy rule

## Parent-safe preview (Pass 3 UI)

Separate read-only panel at report stage showing internal vs parent-safe phrasing. See parent language rules in `CLINICAL_EVIDENCE_EVENT_CONTRACT.md`.
