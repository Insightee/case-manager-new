"""Case Insights aggregation layer — rule-based "Clinical Brain" (no AI required to render).

Every analyzer here is a pure, deterministic function over already-existing structured data
(session logs, IEP goal cards, strategy events, repository items, collaborative inputs).
AI is only layered on top by ``ai_insight_refresh_service`` when the therapist explicitly clicks
"Refresh Insights" — see docs/design/stitch/insights-tab/DESIGN.md.
"""
