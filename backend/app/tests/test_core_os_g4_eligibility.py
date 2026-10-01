"""G4: therapist eligibility + exit (Core OS Stabilisation PR2 / DEC-03)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.permissions import ROLE_PERMISSIONS, RoleName
from app.core.timezone import today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.support_ticket import SupportTicket, TicketCategory
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import EmploymentStatus, User
from app.services.therapist_eligibility_service import (
    RESTORE_TICKET_SUBJECT,
    apply_therapist_exit,
    therapist_may_hold_case,
)
from app.services import assignment_service

client = TestClient(app)


def _admin_headers() -> dict:
    r = client.post("/api/v1/auth/login", json={"email": "superadmin@demo.com", "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cm_still_lacks_case_assign():
    assert "case.assign" not in set(ROLE_PERMISSIONS[RoleName.CASE_MANAGER])


def test_therapist_may_hold_case_blocks_inactive():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None
        therapist.is_active = False
        db.commit()
        assert therapist_may_hold_case(db, therapist.id) is False
        therapist.is_active = True
        therapist.employment_status = EmploymentStatus.ACTIVE
        db.commit()
        assert therapist_may_hold_case(db, therapist.id) is True
    finally:
        # Always restore demo therapist so other suites stay green.
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        if therapist:
            therapist.is_active = True
            therapist.employment_status = EmploymentStatus.ACTIVE
            db.commit()
        db.close()


def test_exit_ends_assignments_and_flags_replacement():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None
        active = list(
            db.scalars(
                select(CaseAssignment).where(
                    CaseAssignment.therapist_user_id == therapist.id,
                    CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                )
            ).all()
        )
        if not active:
            pytest.skip("demo therapist has no ACTIVE assignments")
        case_id = active[0].case_id
        case = db.get(Case, case_id)
        case.status = CaseStatus.ACTIVE
        db.commit()

        result = apply_therapist_exit(db, therapist.id, reason="G4 exit test")
        db.commit()
        assert result["ended_assignments"] >= 1
        remaining = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all()
        assert remaining == []
        case = db.get(Case, case_id)
        assert case.status == CaseStatus.PENDING_REPLACEMENT

        # Restore case to ACTIVE for later suites — leave assignment ended (seed may re-allot).
        case.status = CaseStatus.ACTIVE
        case.status_effective_date = None
        case.status_reason = None
        # Re-create a minimal ACTIVE assignment so therapist portal tests keep working.
        ended = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.case_id == case_id,
            )
            .order_by(CaseAssignment.id.desc())
        ).first()
        if ended:
            ended.status = CaseAssignmentStatus.ACTIVE
            ended.end_date = None
            ended.reason_for_change = "G4 restore after exit test"
        db.commit()
    finally:
        db.close()


def test_assignment_rejects_inactive_therapist():
    from app.services import case_service_service
    from app.services.therapist_eligibility_service import TherapistIneligibleError

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        assert therapist and admin and case
        cs = case_service_service.ensure_default_case_service(db, case)
        therapist.is_active = False
        db.commit()
        with pytest.raises(TherapistIneligibleError) as exc:
            assignment_service.add_assignment_to_service(
                db,
                case_id=case.id,
                case_service_id=cs.id,
                therapist_user_id=therapist.id,
                assigned_by_user_id=admin.id,
                start_date=today_ist(),
            )
        assert exc.value.code == "THERAPIST_INACTIVE"
    finally:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        if therapist:
            therapist.is_active = True
            therapist.employment_status = EmploymentStatus.ACTIVE
            db.rollback()
            therapist.is_active = True
            therapist.employment_status = EmploymentStatus.ACTIVE
            db.commit()
        db.close()


def test_login_blocked_when_inactive_allows_restore_ticket():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None
        therapist.is_active = False
        therapist.employment_status = EmploymentStatus.SUSPENDED
        db.commit()
    finally:
        db.close()

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123"},
    )
    assert blocked.status_code == 403, blocked.text
    detail = blocked.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("can_request_restore") is True

    restore = client.post(
        "/api/v1/auth/request-status-restore",
        json={"email": "therapist@demo.com", "password": "demo123", "note": "Please restore my access"},
    )
    assert restore.status_code == 200, restore.text
    ticket_id = restore.json()["ticket_id"]

    db = SessionLocal()
    try:
        ticket = db.get(SupportTicket, ticket_id)
        assert ticket is not None
        assert ticket.category == TicketCategory.HR
        assert ticket.subject == RESTORE_TICKET_SUBJECT
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        therapist.is_active = True
        therapist.employment_status = EmploymentStatus.ACTIVE
        db.commit()
    finally:
        db.close()

    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123"},
    )
    assert ok.status_code == 200, ok.text


def test_profile_paused_blocks_hold():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        if profile is None:
            pytest.skip("no therapist profile")
        prev = profile.status
        profile.status = TherapistProfileStatus.PAUSED
        db.commit()
        assert therapist_may_hold_case(db, therapist.id) is False
        profile.status = prev or TherapistProfileStatus.APPROVED
        db.commit()
        assert therapist_may_hold_case(db, therapist.id) is True
    finally:
        db.close()
