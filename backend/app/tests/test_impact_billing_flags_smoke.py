"""One-off impact smoke executed under pytest DB bootstrap."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case
from app.models.ledger_billing import BillingLedger
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import billing_ledger_service as bls
from app.services import session_service
from datetime import date, datetime, time, timedelta, timezone


def test_impact_core_paths_with_billing_writes_off(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "enable_billing", False)
    monkeypatch.setattr(settings, "billing_ledger_writes", False)

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    login = client.post("/api/v1/auth/login", json={"email": "therapist@demo.com", "password": "demo123"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    cases = client.get("/api/v1/cases?page_size=1", headers=headers)
    assert cases.status_code == 200, cases.text
    # billing routers gated
    assert client.get("/api/v1/admin/ledger-billing/ledger", headers=headers).status_code == 404

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        asg = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        case = db.get(Case, asg.case_id)
        case.billing_type = BillingType.PER_SESSION
        case.client_rate_per_session_inr = case.client_rate_per_session_inr or 1500.0
        started = datetime.now(timezone.utc) - timedelta(hours=1)
        ended = started + timedelta(minutes=45)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 8, 2),
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
        rows = db.scalars(select(BillingLedger).where(BillingLedger.session_id == session.id)).all()
        assert rows == []
        assert bls._ledger_writes_allowed() is False
        db.rollback()
    finally:
        db.close()
