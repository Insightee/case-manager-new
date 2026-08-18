# Session structured evidence — V1 known debt

Reword is unsolved in V1 and that is accepted.

Lazy registration upserts `iep_goal_items` / `iep_strategy_items` by `(iep_plan_id, normalised statement)`. A CM reword during IEP review creates a **second registry row**. Historical `session_goal_entries` keep pointing at the original id. The split is queryable, countable, and mergeable by a later tool.

Do not “fix” this with a statement hash or a positional index into `sections_json`.

Related: a new IEP version (`iep_plans` row) also mints new registry ids for the same wording. Same merge problem; same later tool.
