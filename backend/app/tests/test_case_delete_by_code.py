"""Maintenance hard-delete by case_code must clear absence + billing FK children."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import case_delete_service
from app.tests.conftest import isolated_homecare_case, login_headers

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_delete_case_by_code_clears_session_absences():
    db = SessionLocal()
    try:
        case = isolated_homecare_case(db)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=datetime.now(timezone.utc).date(),
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.now(timezone.utc),
            actual_end_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()
        db.add(
            SessionAbsenceRequest(
                session_id=session.id,
                case_id=case.id,
                therapist_user_id=therapist.id,
                absence_type=SessionAbsenceType.CLIENT_ABSENT,
                status=SessionAbsenceStatus.APPROVED,
                reason="Delete coverage fixture",
                requested_by_user_id=therapist.id,
            )
        )
        db.commit()
        case_code = case.case_code
        case_id = case.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        result = case_delete_service.delete_case_by_code(db, case_code)
        db.commit()
        assert result["deleted"] is True
        assert result["case_code"] == case_code
        assert db.get(Case, case_id) is None
        absences = db.scalars(
            select(SessionAbsenceRequest).where(SessionAbsenceRequest.case_id == case_id)
        ).all()
        assert absences == []
    finally:
        db.close()


def test_admin_delete_case_by_code_endpoint_requires_confirm():
    headers = login_headers(client, "superadmin@demo.com")
    res = client.post(
        "/api/v1/admin/maintenance/delete-case-by-code",
        headers=headers,
        json={"case_code": "IC-DOES-NOT-EXIST", "confirm": False},
    )
    assert res.status_code == 400
    assert "confirm" in res.json()["detail"].lower()
