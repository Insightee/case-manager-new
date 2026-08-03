"""Session clinical insight + longitudinal aggregator tests."""

from __future__ import annotations

from app.core.config import settings
from app.services.session_clinical_insight_service import build_session_clinical_insights
from app.services.session_longitudinal_aggregator import format_strategy_longitudinal_line


def test_format_strategy_longitudinal_line_requires_denominator(monkeypatch):
    monkeypatch.setattr(settings, "enable_clinical_brain_insights", True)
    line = format_strategy_longitudinal_line("Visual timer", {"worked_well": 3, "partially_worked": 1})
    assert line is not None
    assert "4 of 4" in line
    assert format_strategy_longitudinal_line("Visual timer", {"worked_well": 1}) is None


def test_build_session_clinical_insights_from_confirmed(monkeypatch):
    monkeypatch.setattr(settings, "enable_clinical_brain_insights", True)
    monkeypatch.setattr(
        "app.services.session_clinical_insight_service.recent_confirmed_session_count",
        lambda *a, **k: 0,
    )
    monkeypatch.setattr(
        "app.services.session_clinical_insight_service.strategy_outcome_counts",
        lambda *a, **k: {},
    )
    structured = {
        "goals": [
            {
                "goal_label": "Turn-taking",
                "status": "confirmed",
                "strategies": [{"strategy_label": "First-then", "feedback": "worked_well"}],
            }
        ],
        "strategies_session_level": [],
        "child_response_signals": [],
    }

    insights = build_session_clinical_insights(
        None,
        case_id=1,
        session_id=2,
        structured=structured,
        extraction_insights=[],
    )
    assert any(i["insight_type"] == "learned_today" for i in insights)
    assert any(i["insight_type"] == "limitation" for i in insights)
