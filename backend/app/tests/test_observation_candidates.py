"""Observation report goal/strategy candidates via repository."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.goal_repository import GoalRepositoryItem, StrategyRepositoryItem

client = TestClient(app)
ensure_sqlite_schema_patches()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_observation_goal_and_strategy_candidates():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id

    ws = client.get(f"/api/v1/cases/{case_id}/reports/observation", headers=headers)
    assert ws.status_code == 200
    report_id = ws.json()["report_id"]

    r = client.post(
        f"/api/v1/reports/{report_id}/observation/goal-candidates",
        headers=headers,
        json={"label": "Initiate peer play with visual supports", "domain_key": "social"},
    )
    assert r.status_code == 200, r.text
    goal_id = r.json()["id"]

    r = client.post(
        f"/api/v1/reports/{report_id}/observation/strategy-candidates",
        headers=headers,
        json={"label": "First-then board for transitions", "description": "Used during classroom observation"},
    )
    assert r.status_code == 200, r.text

    r = client.get(f"/api/v1/reports/{report_id}/observation/candidates", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["goals"]) >= 1
    assert len(data["strategies"]) >= 1

    with SessionLocal() as db:
        goal = db.get(GoalRepositoryItem, goal_id)
        assert goal is not None
        assert goal.source == "observation_report"
        assert goal.source_clinical_report_id == report_id
        assert goal.status == "candidate"
        strat = db.scalars(
            select(StrategyRepositoryItem).where(StrategyRepositoryItem.source_clinical_report_id == report_id)
        ).first()
        assert strat is not None
        assert strat.source == "observation_report"
