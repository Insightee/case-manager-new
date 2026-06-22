from __future__ import annotations

import pytest
from datetime import date, datetime, time, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.leave import TherapistLeave, LeaveType, LeaveBillingCategory, LeaveStatus
from app.models.session import Session as TherapySession, SessionStatus
from app.models.case import Case
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.support_ticket import SupportTicket
from app.models.document_comment import DocumentComment, DocumentEntityType
from app.seed.demo_seed import run as seed_run

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()

def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def test_duplicate_leave_request_gating():
    therapist_headers = _login("therapist@demo.com")
    
    # 1. Create a therapist leave request first (valid/approved or pending)
    # The API endpoint: POST /api/v1/leave
    # Let's request leave for 2026-11-10 to 2026-11-15
    res = client.post(
        "/api/v1/leave",
        headers=therapist_headers,
        json={
            "service_line": "shadow_support",
            "start_date": "2026-11-10",
            "end_date": "2026-11-15",
            "reason": "Initial Leave",
            "consulted_with_parents": True,
        }
    )
    assert res.status_code == 201, res.text
    
    # 2. Try to request overlapping leave
    res2 = client.post(
        "/api/v1/leave",
        headers=therapist_headers,
        json={
            "service_line": "shadow_support",
            "start_date": "2026-11-12",
            "end_date": "2026-11-14",
            "reason": "Overlapping Leave",
            "consulted_with_parents": True,
        }
    )
    assert res2.status_code == 400
    assert "Leave is already marked for this date. View existing leave." in res2.json()["detail"]


def test_virtual_daily_logs_returned():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        assert therapist and parent
        
        # Let's find a case that has assignments or just use the first case
        case = db.scalars(select(Case)).first()
        assert case
        
        # Make sure parent is assigned as parent_user_id on the case
        case.parent_user_id = parent.id
        
        # Let's check if there is a CaseAssignment for the therapist, or assign them if not
        assignment = db.scalars(
            select(CaseAssignment)
            .where(CaseAssignment.case_id == case.id, CaseAssignment.therapist_user_id == therapist.id)
        ).first()
        if not assignment:
            assignment = CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist.id,
                start_date=date(2025, 1, 1),
                status=CaseAssignmentStatus.ACTIVE,
            )
            db.add(assignment)
        db.commit()
        
        # Create a session with status THERAPIST_LEAVE
        session_leave = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            status=SessionStatus.THERAPIST_LEAVE,
            scheduled_date=date(2026, 11, 20),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        # Create a session with status CLIENT_ABSENT
        session_absent = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            status=SessionStatus.CLIENT_ABSENT,
            scheduled_date=date(2026, 11, 21),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        db.add_all([session_leave, session_absent])
        db.commit()
        
        session_leave_id = session_leave.id
        session_absent_id = session_absent.id
    finally:
        db.close()

    # Now let's fetch daily logs for therapist
    therapist_headers = _login("therapist@demo.com")
    res = client.get("/api/v1/daily-logs", headers=therapist_headers)
    assert res.status_code == 200
    items = res.json()
    
    # We should see virtual logs with negative IDs
    virtual_leave_log = next((item for item in items if item["id"] == -session_leave_id), None)
    virtual_absent_log = next((item for item in items if item["id"] == -session_absent_id), None)
    
    assert virtual_leave_log is not None
    assert virtual_leave_log["attendance_status"] == "THERAPIST_LEAVE"
    
    assert virtual_absent_log is not None
    assert virtual_absent_log["attendance_status"] == "CLIENT_ABSENT"

    # Now let's check parent endpoint
    parent_headers = _login("parent@demo.com")
    res_parent = client.get("/api/v1/parent/session-logs", headers=parent_headers)
    assert res_parent.status_code == 200
    parent_logs = res_parent.json()
    
    parent_leave_log = next((item for item in parent_logs if item["id"] == -session_leave_id), None)
    parent_absent_log = next((item for item in parent_logs if item["id"] == -session_absent_id), None)
    
    assert parent_leave_log is not None
    assert parent_leave_log["attendance_status"] == "THERAPIST_LEAVE"
    
    assert parent_absent_log is not None
    assert parent_absent_log["attendance_status"] == "CLIENT_ABSENT"


def test_daily_log_comments():
    db = SessionLocal()
    try:
        # Create a real daily log first to test comments on real/virtual logs
        # We can also comment on virtual log IDs (negative IDs)
        session = db.scalars(select(TherapySession).where(TherapySession.status == SessionStatus.COMPLETED)).first()
        assert session
        session_id = session.id
    finally:
        db.close()

    parent_headers = _login("parent@demo.com")
    therapist_headers = _login("therapist@demo.com")
    
    # Use a negative ID (virtual log) for the comment test
    virtual_log_id = -session_id
    
    # 1. Post a comment from parent
    res_post = client.post(
        f"/api/v1/parent/session-logs/{virtual_log_id}/comments",
        headers=parent_headers,
        json={"body": "This is a parent comment on virtual log"}
    )
    assert res_post.status_code == 201, res_post.text
    data = res_post.json()
    assert data["body"] == "This is a parent comment on virtual log"
    
    # 2. Get comments from therapist
    res_get = client.get(
        f"/api/v1/daily-logs/{virtual_log_id}/comments",
        headers=therapist_headers
    )
    assert res_get.status_code == 200
    comments = res_get.json()
    assert len(comments) >= 1
    assert comments[0]["body"] == "This is a parent comment on virtual log"
    
    # 3. Post a reply from therapist
    res_reply = client.post(
        f"/api/v1/daily-logs/{virtual_log_id}/comments",
        headers=therapist_headers,
        json={"body": "Therapist reply"}
    )
    assert res_reply.status_code == 201
    
    # 4. Get comments from parent
    res_get_parent = client.get(
        f"/api/v1/parent/session-logs/{virtual_log_id}/comments",
        headers=parent_headers
    )
    assert res_get_parent.status_code == 200
    parent_comments = res_get_parent.json()
    assert len(parent_comments) >= 2
    assert parent_comments[1]["body"] == "Therapist reply"


def test_parent_session_dispute():
    db = SessionLocal()
    try:
        case = db.scalars(select(Case)).first()
        parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and parent and therapist
        
        # Create an absent session to dispute
        absent_session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            status=SessionStatus.CLIENT_ABSENT,
            scheduled_date=date(2026, 11, 25),
            start_time=time(14, 0),
            end_time=time(15, 0),
        )
        db.add(absent_session)
        db.commit()
        absent_session_id = absent_session.id
    finally:
        db.close()

    parent_headers = _login("parent@demo.com")
    
    # Dispute the session
    res_dispute = client.post(
        f"/api/v1/parent/session-logs/{absent_session_id}/dispute",
        headers=parent_headers,
        json={"comment": "I dispute this client absent record. The therapist did not inform us."}
    )
    assert res_dispute.status_code == 200, res_dispute.text
    dispute_data = res_dispute.json()
    assert dispute_data["status"] == "disputed"
    assert dispute_data["ticket_id"] is not None
    
    # Verify support ticket is created and linked
    db = SessionLocal()
    try:
        ticket = db.scalars(
            select(SupportTicket).where(SupportTicket.disputed_session_id == absent_session_id)
        ).first()
        assert ticket is not None
        assert f"Dispute session" in ticket.subject
        assert "I dispute this client absent record." in ticket.body
        assert ticket.status == "OPEN"
        
        # Verify the session dispute_status field dynamically when fetching parent logs
        res_logs = client.get("/api/v1/parent/session-logs", headers=parent_headers)
        assert res_logs.status_code == 200
        parent_logs = res_logs.json()
        target_log = next((item for item in parent_logs if item["id"] == -absent_session_id), None)
        assert target_log is not None
        assert target_log["dispute_status"] == "DISPUTED"
    finally:
        db.close()
