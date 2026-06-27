from __future__ import annotations

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.timezone import today_ist
from app.main import app
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus, SessionMode
from app.models.user import User
from app.models.email_log import EmailLog
from app.services.email.events import EmailEvent
from app.core.database import SessionLocal
from app.seed.demo_seed import run as seed_run
from app.models.parent import ParentGuardian
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.notification import Notification
from app.models.therapist_profile import TherapistProfile

client = TestClient(app)

def _login(email: str, password: str = "demo123") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()

def test_parent_visibility_and_comments_flow():
    db = SessionLocal()
    try:
        # Get users
        therapist_user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        parent_user = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        casemanager_user = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        assert therapist_user and parent_user and casemanager_user

        # Find the parent's child and case
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent_user.id)).first()
        assert pg and pg.children
        child_id = list(pg.children)[0].id
        case = db.scalars(select(Case).where(Case.child_id == child_id)).first()
        assert case

        # Assign case manager
        case.case_manager_user_id = casemanager_user.id
        db.commit()

        # Ensure therapist is assigned to this case
        assignment = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.therapist_user_id == therapist_user.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE
            )
        ).first()
        if not assignment:
            assignment = CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist_user.id,
                status=CaseAssignmentStatus.ACTIVE,
                start_date=today_ist(),
            )
            db.add(assignment)
            db.commit()

        # 1. Create a completed session
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist_user.id,
            scheduled_date=today_ist(),
            start_time=datetime.now(timezone.utc).time(),
            end_time=datetime.now(timezone.utc).time(),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.now(timezone.utc),
            actual_end_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # 2. Therapist submits the daily log
        therapist_headers = _login("therapist@demo.com")
        res = client.post(
            "/api/v1/daily-logs",
            headers=therapist_headers,
            json={
                "session_id": session.id,
                "attendance_status": "PRESENT",
                "session_notes": "Great session today!",
                "activities_done": "Puzzles",
                "goals_addressed": "Cognitive tasks",
                "observations": "Attentive",
                "follow_ups": "Repeat puzzles next time",
            }
        )
        assert res.status_code == 201
        log_id = res.json()["id"]

        # Ensure email log has 1 entry for this daily log submission
        email_logs = db.scalars(
            select(EmailLog).where(
                EmailLog.entity_type == "daily_log",
                EmailLog.entity_id == log_id,
                EmailLog.event_type == EmailEvent.SESSION_LOG_SUBMITTED.value,
            )
        ).all()
        assert len(email_logs) >= 1
        original_email_log_count = len(email_logs)

        # Re-save/update log as therapist to check email idempotency guard
        res = client.patch(
            f"/api/v1/daily-logs/{log_id}",
            headers=therapist_headers,
            json={"session_notes": "Updated notes."}
        )
        assert res.status_code == 200

        # Verify no duplicate email was sent
        email_logs_after = db.scalars(
            select(EmailLog).where(
                EmailLog.entity_type == "daily_log",
                EmailLog.entity_id == log_id,
                EmailLog.event_type == EmailEvent.SESSION_LOG_SUBMITTED.value,
            )
        ).all()
        assert len(email_logs_after) == original_email_log_count

        # 3. Parent fetches daily logs - under-review log must be visible
        parent_headers = _login("parent@demo.com")
        res = client.get("/api/v1/parent/session-logs", headers=parent_headers)
        assert res.status_code == 200
        logs = res.json()
        
        # Find our newly submitted log
        parent_log = next((l for l in logs if l["id"] == log_id), None)
        assert parent_log is not None
        assert parent_log["parent_display_status"] == "Under Review"
        assert parent_log["can_parent_comment"] is True

        mentor_user = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        tp = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == therapist_user.id)).first()
        if tp and mentor_user:
            tp.mentor_user_id = mentor_user.id
            db.commit()

        # 4. Parent posts a comment to the log
        comment_res = client.post(
            f"/api/v1/parent/session-logs/{log_id}/comments",
            headers=parent_headers,
            json={"body": "Hello team, thank you for the feedback!"}
        )
        assert comment_res.status_code == 201
        comment_id = comment_res.json()["id"]

        db.expire_all()
        for uid in {therapist_user.id, casemanager_user.id, mentor_user.id if mentor_user else None} - {None}:
            staff_notifs = db.scalars(
                select(Notification).where(
                    Notification.user_id == uid,
                    Notification.entity_type == "daily_log",
                    Notification.entity_id == log_id,
                )
            ).all()
            assert any("Family comment" in n.title for n in staff_notifs), f"Expected staff bell alert for user {uid}"

        # 5. Therapist, CM, and Admin see the parent's comment
        for role_email in ["therapist@demo.com", "casemanager@demo.com", "superadmin@demo.com"]:
            headers = _login(role_email)
            c_res = client.get(f"/api/v1/daily-logs/{log_id}/comments", headers=headers)
            assert c_res.status_code == 200
            comments = c_res.json()
            comment_found = next((c for c in comments if c["id"] == comment_id), None)
            assert comment_found is not None
            assert comment_found["body"] == "Hello team, thank you for the feedback!"

        # 6. CM approves the log
        cm_headers = _login("casemanager@demo.com")
        approve_res = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=cm_headers)
        assert approve_res.status_code == 200, f"Approve failed: {approve_res.status_code} - {approve_res.text}"

        # 7. Parent displays status changes to "Reviewed"
        res = client.get("/api/v1/parent/session-logs", headers=parent_headers)
        assert res.status_code == 200
        parent_log = next((l for l in res.json() if l["id"] == log_id), None)
        assert parent_log is not None
        assert parent_log["parent_display_status"] == "Reviewed"

        # 8. Check reviewed email NOT sent on CM approval by default
        db.expire_all()
        reviewed_emails = db.scalars(
            select(EmailLog).where(
                EmailLog.entity_type == "daily_log",
                EmailLog.entity_id == log_id,
                EmailLog.event_type == EmailEvent.SESSION_LOG_REVIEWED.value,
            )
        ).all()
        assert len(reviewed_emails) == 0

        # 9. CM posts an internal note
        internal_res = client.post(
            f"/api/v1/daily-logs/{log_id}/comments",
            headers=cm_headers,
            json={"body": "This is an internal CM review note.", "visibility": "internal_only"}
        )
        assert internal_res.status_code == 201
        internal_id = internal_res.json()["id"]

        db.expire_all()
        parent_reply_notifs_before = db.scalars(
            select(Notification).where(
                Notification.user_id == parent_user.id,
                Notification.entity_type == "daily_log",
                Notification.entity_id == log_id,
            )
        ).all()
        parent_reply_count_before = sum(1 for n in parent_reply_notifs_before if "Reply on" in n.title)

        # Parent fetches comments - must NOT see internal note
        parent_c_res = client.get(f"/api/v1/parent/session-logs/{log_id}/comments", headers=parent_headers)
        assert parent_c_res.status_code == 200
        assert all(c["id"] != internal_id for c in parent_c_res.json())

        # 10. CM posts a parent-visible reply
        reply_res = client.post(
            f"/api/v1/daily-logs/{log_id}/comments",
            headers=cm_headers,
            json={"body": "We have seen this, thank you!", "visibility": "parent_team"}
        )
        assert reply_res.status_code == 201
        reply_id = reply_res.json()["id"]

        # Parent fetches comments - must see public reply
        parent_c_res2 = client.get(f"/api/v1/parent/session-logs/{log_id}/comments", headers=parent_headers)
        reply_found = next((c for c in parent_c_res2.json() if c["id"] == reply_id), None)
        assert reply_found is not None
        assert reply_found["author_role"] == "case_manager"
        assert reply_found["visibility"] == "parent_team"

        db.expire_all()
        parent_reply_notifs_after = db.scalars(
            select(Notification).where(
                Notification.user_id == parent_user.id,
                Notification.entity_type == "daily_log",
                Notification.entity_id == log_id,
            )
        ).all()
        parent_reply_count_after = sum(1 for n in parent_reply_notifs_after if "Reply on" in n.title)
        assert parent_reply_count_after == parent_reply_count_before + 1

        therapist_reply_res = client.post(
            f"/api/v1/daily-logs/{log_id}/comments",
            headers=_login("therapist@demo.com"),
            json={"body": "Thanks — we will follow up at the next session.", "visibility": "parent_team"},
        )
        assert therapist_reply_res.status_code == 201
        db.expire_all()
        parent_reply_notifs_therapist = db.scalars(
            select(Notification).where(
                Notification.user_id == parent_user.id,
                Notification.entity_type == "daily_log",
                Notification.entity_id == log_id,
            )
        ).all()
        assert sum(1 for n in parent_reply_notifs_therapist if "Reply on" in n.title) == parent_reply_count_after + 1

        # Parent comment status should automatically transition to "acknowledged" due to reply
        parent_comment = next((c for c in parent_c_res2.json() if c["id"] == comment_id), None)
        assert parent_comment is not None
        assert parent_comment["status"] == "acknowledged"

        # Comment counts on list endpoints
        cm_list = client.get(f"/api/v1/daily-logs?case_id={case.id}", headers=cm_headers)
        assert cm_list.status_code == 200
        cm_log = next((l for l in cm_list.json() if l["id"] == log_id), None)
        assert cm_log is not None
        assert cm_log["comment_count"] >= 4
        assert cm_log["open_parent_comment_count"] == 0

        parent_list = client.get("/api/v1/parent/session-logs", headers=parent_headers)
        parent_log_counts = next((l for l in parent_list.json() if l["id"] == log_id), None)
        assert parent_log_counts is not None
        assert parent_log_counts["comment_count"] == 3

        # Comment counts batch endpoint
        batch = client.get(
            f"/api/v1/daily-logs/comment-counts?log_ids={log_id}",
            headers=cm_headers,
        )
        assert batch.status_code == 200
        assert batch.json()[str(log_id)]["comment_count"] >= 4

        # 11. CM updates parent comment status to "resolved"
        status_res = client.patch(
            f"/api/v1/daily-logs/comments/{comment_id}/status",
            headers=cm_headers,
            json={"status": "resolved"}
        )
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "resolved"

    finally:
        db.rollback()
        db.close()
