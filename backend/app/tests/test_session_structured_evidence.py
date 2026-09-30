"""Structured session evidence: registry identity, log taps, flag-off no-ops."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.daily_log import DailyLog
from app.models.iep_identity import IepGoalItem, IepStrategyItem
from app.models.iep_plan import IepPlan
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.session_evidence import SessionGoalEntry, StrategyUseEvent
from app.models.user import User
from app.services import iep_plan_service, log_service, session_service
from app.tests.session_helpers import end_active_sessions_for_therapist

client = TestClient(app)
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND / "alembic") not in sys.path:
    sys.path.insert(0, str(_BACKEND / "alembic"))


@pytest.fixture(autouse=True)
def _isolate_therapist_sessions():
    end_active_sessions_for_therapist()
    yield
    end_active_sessions_for_therapist()


_SESSION_SEQ = 0


def _login(email: str, password: str = "demo123") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _complete_session(_headers: dict[str, str] | None = None) -> int:
    global _SESSION_SEQ
    _SESSION_SEQ += 1
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first() if therapist else None
        if not therapist or not assignment:
            pytest.skip("No therapist assignment")
        started = datetime.now(timezone.utc) - timedelta(hours=1)
        ended = started + timedelta(minutes=45)
        session = TherapySession(
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today_ist() - timedelta(days=_SESSION_SEQ),
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
        )
        db.add(session)
        db.flush()
        session_service.end_session(db, session, end_at=ended)
        db.commit()
        return session.id
    finally:
        db.close()


def _seed_iep(db, case_id: int, author_id: int) -> IepPlan:
    sections = {
        "schema_version": 2,
        "learning_environments": [
            {
                "environment": "home",
                "goals": "Request help with words\nShare a toy",
                "strategies": "Visual schedule\nWait time",
            }
        ],
    }
    plan = IepPlan(
        case_id=case_id,
        version="v1",
        status="DRAFT",
        sections_json=json.dumps(sections),
        created_by_user_id=author_id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def test_alembic_single_head_is_goal_repository_repair():
    cfg = Config(str(_BACKEND / "alembic.ini"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    # Current tip: SPOT role + staff employment / staff leave billing columns.
    assert heads == ["s7p0t3m4p5l6"]


def test_structured_evidence_revision_upgrade_and_downgrade(tmp_path):
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    url = f"sqlite:///{tmp_path / 'evidence.db'}"
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE iep_plans (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE daily_logs (id INTEGER PRIMARY KEY)"))
    spec = importlib.util.spec_from_file_location(
        "structured_evidence_rev",
        _BACKEND / "alembic/versions/s4e5v6i7d8e9_session_structured_evidence.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def _run(fn):
        with eng.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                fn()

    try:
        _run(mod.upgrade)
        insp = inspect(eng)
        for table in ("iep_goal_items", "iep_strategy_items", "session_goal_entries", "strategy_use_events"):
            assert insp.has_table(table)
        _run(mod.downgrade)
        insp.clear_cache()
        for table in ("iep_goal_items", "iep_strategy_items", "session_goal_entries", "strategy_use_events"):
            assert not insp.has_table(table)
        _run(mod.upgrade)
        insp.clear_cache()
        assert insp.has_table("session_goal_entries")
    finally:
        eng.dispose()


def test_flag_off_skips_registry_and_ignores_evidence_payload():
    headers = _login("therapist@demo.com")
    sid = _complete_session(headers)
    db = SessionLocal()
    try:
        session = db.get(TherapySession, sid)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _seed_iep(db, session.case_id, therapist.id)
        before_goals = db.scalar(select(func.count(IepGoalItem.id))) or 0
        iep = client.get(f"/api/v1/cases/{session.case_id}/iep-plan", headers=headers)
        assert iep.status_code == 200, iep.text
        assert "goal_items" not in iep.json()
        assert (db.scalar(select(func.count(IepGoalItem.id))) or 0) == before_goals
    finally:
        db.close()

    payload = {
        "session_id": sid,
        "attendance_status": "PRESENT",
        "activities_done": "Play therapy session",
        "goal_entries": [
            {
                "goal_id": 999999,
                "participation": "engaged",
                "support_level": "independent",
                "achievement": "emerging",
            }
        ],
    }
    created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    if created.status_code == 400 and "Late reason" in created.text:
        payload["late_reason"] = "Coverage for past-day seeded session"
        created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert "goal_entries" not in created.json()
    db = SessionLocal()
    try:
        assert (db.scalar(select(func.count(SessionGoalEntry.id)).where(
            SessionGoalEntry.daily_log_id == created.json()["id"]
        )) or 0) == 0
    finally:
        db.close()


def test_lazy_registration_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "enable_structured_evidence", True)
    headers = _login("therapist@demo.com")
    sid = _complete_session(headers)
    db = SessionLocal()
    try:
        session = db.get(TherapySession, sid)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _seed_iep(db, session.case_id, therapist.id)
        case_id = session.case_id
    finally:
        db.close()

    first = client.get(f"/api/v1/cases/{case_id}/iep-plan", headers=headers)
    assert first.status_code == 200, first.text
    assert len(first.json()["goal_items"]) == 2
    assert len(first.json()["strategy_items"]) == 2
    ids = {row["id"] for row in first.json()["goal_items"]}
    second = client.get(f"/api/v1/cases/{case_id}/iep-plan", headers=headers)
    assert {row["id"] for row in second.json()["goal_items"]} == ids
    db = SessionLocal()
    try:
        plan_id = first.json()["id"]
        assert db.scalar(select(func.count(IepGoalItem.id)).where(IepGoalItem.iep_plan_id == plan_id)) == 2
        assert db.scalar(select(func.count(IepStrategyItem.id)).where(IepStrategyItem.iep_plan_id == plan_id)) == 2
    finally:
        db.close()


def test_concurrent_registration_one_row_no_500(monkeypatch):
    monkeypatch.setattr(settings, "enable_structured_evidence", True)
    headers = _login("therapist@demo.com")
    sid = _complete_session(headers)
    db = SessionLocal()
    try:
        session = db.get(TherapySession, sid)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        plan = _seed_iep(db, session.case_id, therapist.id)
        case_id = session.case_id
        plan_id = plan.id
    finally:
        db.close()

    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _register():
        nested = SessionLocal()
        try:
            plan = nested.get(IepPlan, plan_id)
            barrier.wait(timeout=5)
            iep_plan_service.register_iep_identity_items(nested, plan)
            nested.commit()
        except Exception as exc:
            errors.append(exc)
            nested.rollback()
        finally:
            nested.close()

    workers = [threading.Thread(target=_register) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert errors == []

    listed = client.get(f"/api/v1/cases/{case_id}/iep-plan", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.status_code != 500
    assert len(listed.json()["goal_items"]) == 2
    db = SessionLocal()
    try:
        assert db.scalar(select(func.count(IepGoalItem.id)).where(IepGoalItem.iep_plan_id == plan_id)) == 2
        assert db.scalar(select(func.count(IepStrategyItem.id)).where(IepStrategyItem.iep_plan_id == plan_id)) == 2
    finally:
        db.close()


def test_create_persists_evidence_and_update_replaces_all(monkeypatch):
    monkeypatch.setattr(settings, "enable_structured_evidence", True)
    headers = _login("therapist@demo.com")
    sid = _complete_session(headers)
    db = SessionLocal()
    try:
        session = db.get(TherapySession, sid)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _seed_iep(db, session.case_id, therapist.id)
        case_id = session.case_id
    finally:
        db.close()

    plan = client.get(f"/api/v1/cases/{case_id}/iep-plan", headers=headers).json()
    g1, g2 = plan["goal_items"][0]["id"], plan["goal_items"][1]["id"]
    s1 = plan["strategy_items"][0]["id"]
    payload = {
        "session_id": sid,
        "attendance_status": "PRESENT",
        "activities_done": "Play therapy session",
        "goal_entries": [
            {
                "goal_id": g1,
                "participation": "engaged",
                "support_level": "occasional",
                "achievement": "progressing",
            },
            {
                "goal_id": g2,
                "participation": "supported",
                "support_level": "consistent",
                "achievement": "emerging",
            },
        ],
        "strategy_events": [{"strategy_id": s1, "response": "helpful"}],
    }
    created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    if created.status_code == 400 and "Late reason" in created.text:
        payload["late_reason"] = "Coverage for past-day seeded session"
        created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert len(body["goal_entries"]) == 2
    assert len(body["strategy_events"]) == 1

    updated = client.patch(
        f"/api/v1/daily-logs/{body['id']}",
        headers=headers,
        json={
            "goal_entries": [
                {
                    "goal_id": g1,
                    "participation": "mixed",
                    "support_level": "independent",
                    "achievement": "demonstrated",
                }
            ],
            "strategy_events": [],
        },
    )
    assert updated.status_code == 200, updated.text
    assert len(updated.json()["goal_entries"]) == 1
    assert updated.json()["goal_entries"][0]["goal_id"] == g1
    assert updated.json()["goal_entries"][0]["participation"] == "mixed"
    assert updated.json()["strategy_events"] == []


def test_evidence_rolls_back_with_parent_log(monkeypatch):
    monkeypatch.setattr(settings, "enable_structured_evidence", True)
    headers = _login("therapist@demo.com")
    sid = _complete_session(headers)
    db = SessionLocal()
    try:
        session = db.get(TherapySession, sid)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        plan = _seed_iep(db, session.case_id, therapist.id)
        goals, strats = iep_plan_service.register_iep_identity_items(db, plan)
        db.commit()
        log, created = log_service.create_daily_log(
            db,
            session_id=sid,
            attendance_status="PRESENT",
            activities_done="Play therapy session",
            late_reason="Rollback coverage",
            created_by_user_id=therapist.id,
            goal_entries=[
                {
                    "goal_id": goals[0]["id"],
                    "participation": "engaged",
                    "support_level": "independent",
                    "achievement": "emerging",
                }
            ],
            strategy_events=[{"strategy_id": strats[0]["id"], "response": "helpful"}],
        )
        assert created
        assert db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)).first()
        db.rollback()
        assert db.scalars(select(DailyLog).where(DailyLog.session_id == sid)).first() is None
        assert (
            db.scalar(select(func.count(SessionGoalEntry.id)).where(SessionGoalEntry.daily_log_id == log.id)) or 0
        ) == 0
        assert (
            db.scalar(select(func.count(StrategyUseEvent.id)).where(StrategyUseEvent.daily_log_id == log.id)) or 0
        ) == 0
    finally:
        db.close()


def test_approved_log_cannot_change_evidence(monkeypatch):
    monkeypatch.setattr(settings, "enable_structured_evidence", True)
    headers = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")
    sid = _complete_session(headers)
    db = SessionLocal()
    try:
        session = db.get(TherapySession, sid)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _seed_iep(db, session.case_id, therapist.id)
        case_id = session.case_id
    finally:
        db.close()
    plan = client.get(f"/api/v1/cases/{case_id}/iep-plan", headers=headers).json()
    g1 = plan["goal_items"][0]["id"]
    payload = {
        "session_id": sid,
        "attendance_status": "PRESENT",
        "activities_done": "Play therapy session",
        "goal_entries": [
            {
                "goal_id": g1,
                "participation": "engaged",
                "support_level": "independent",
                "achievement": "emerging",
            }
        ],
    }
    created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    if created.status_code == 400 and "Late reason" in created.text:
        payload["late_reason"] = "Coverage for past-day seeded session"
        created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    approve = client.post(f"/api/v1/daily-logs/{created.json()['id']}/approve", headers=admin)
    assert approve.status_code == 200, approve.text
    blocked = client.patch(
        f"/api/v1/daily-logs/{created.json()['id']}",
        headers=headers,
        json={
            "goal_entries": [
                {
                    "goal_id": g1,
                    "participation": "mixed",
                    "support_level": "occasional",
                    "achievement": "progressing",
                }
            ]
        },
    )
    assert blocked.status_code == 400
    assert "pending" in blocked.json()["detail"].lower() or "24 hours" in blocked.json()["detail"]
