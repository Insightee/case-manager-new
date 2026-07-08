# Insights Tab — Design Contract (Phase 1)

The Insights tab is a calm, rule-based therapist decision-support workspace — not an AI dashboard. Most content
comes from the app's own structured data (Layer 1). AI is only used to polish wording on explicit "Refresh
Insights" clicks (Layer 2/3), capped at **2 refreshes per case per therapist per week**.

## Section order (do not reorder)

1. **Child Snapshot** — warm strengths-based paragraph + 4 compact cards (Strengths & Interests, Helpful
   Supports, Support Needs, Recent Pattern Noticed) + source line.
2. **IEP Goal Progress** — one card per active IEP goal: status chip, measurement line, progress insight,
   "View evidence" link, next step.
3. **Strategy Response** — nested accordion inside each goal card (not a separate top-level section).
4. **Next Session Focus** — one action card: 1 goal + 1 strategy + 1 observe + 1 adapt.
5. **Collaborative Inputs** — Parent / Case Manager / School cards, each actionable.
6. **Session Log Insights & Evidence** — exactly 3 fixed cards: What's helping / Needs adapting / Support
   needs & concerns.
7. **Suggested Goals & Strategies** — safer actions only, no direct "add to active IEP".
8. **Bottom Actions** — exactly 2 primary actions: *Add selected insights to Monthly Report*, *Submit selected
   items for IEP Review*.

Mobile stacks the same content but drops "Suggested Goals & Strategies" to the end and uses one sticky bottom
button ("Add selected to Monthly Report") instead of the inline two-button row.

## Status vocabulary (never percentages)

**Goal progress status** (`goal_progress_analyzer.py`):
`Emerging` · `Building` · `Consistent` · `Needs adapting` · `Not enough evidence`

**Strategy response status** (`strategy_response_analyzer.py`):
`Helpful` · `Partly helpful` · `Needs adapting` · `Not enough evidence`

**Suggested item status** (`suggested_goal_strategy_engine.py`):
`Case-specific` · `Pending CM review` · `Approved strategy` · `Pool candidate` · `Suggested adaptation`

Evidence is always shown as a plain count/source line, e.g. "Addressed in 3/5 sessions", "Source: 5 session
logs", "Source: 1 incident note, 2 session logs" — never a progress bar.

## Insight object shape

Every entry in the flat `insights[]` array returned by `case_insight_aggregator.py` follows:

```json
{
  "id": "goal_12_progress",
  "type": "goal_progress | strategy_response | next_session | collaborative_input | evidence | suggested_goal | suggested_strategy | child_snapshot",
  "title": "string",
  "summary": "string",
  "status": "string | null",
  "source": { "type": "session_logs | incident_notes | parent_input | iep_plan | repository", "count": 5, "label": "Source: 5 session logs" },
  "linkedGoalId": "string | null",
  "linkedStrategyId": "string | null",
  "recommendedAction": "string",
  "reviewPath": "therapist_review | cm_review | iep_review",
  "confidence": "structured_data_supported",
  "requiresAI": false
}
```

## Banned words (never emit in generated titles/summaries or static copy)

`patient`, `compliance`, `behavioral clustering`, `cognitive progress analysis`, `neural patterns`,
`goal attainment`, `deficit`, `non-compliant`, `failed goal`, `aggressive child`.

Use instead: `child`, `progress insight`, `support pattern`, `participation`, `strategy response`,
`needs adapting`, `not enough evidence`, `communicated distress through behaviour`,
`strengths/interests supported engagement`.

## AI refresh messaging (verbatim)

- Cap exceeded: *"You've used your 2 AI refreshes for this week. Insights will still update from session logs
  and structured data."*
- No new data since last refresh: *"Insights are already up to date from the latest available data."*
- Loading state: *"Updating insights from latest logs…"*

## Retired in this phase

"Ask Insighte AI" follow-up chat and "Generation History" are removed with no direct replacement — the calmer
direction does not need a chat surface or a snapshot history list. `ClinicalSnapshot` rows are still written
(now tagged `insight_type="case_insight_refresh"`) purely as the AI refresh cache/weekly-cap ledger.
