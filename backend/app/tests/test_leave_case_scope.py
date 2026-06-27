"""Case-scoped leave overlays and overlap validation."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import Case
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.user import User
from app.services import leave_service, slot_calendar_service as cal
from app.tests.test_leave_policy import _ensure_therapist_profile


def _therapist_and_cases():
    db = SessionLocal()
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    cases = db.scalars(select(Case).limit(2)).all()
    _ensure_therapist_profile(db, therapist.id)
    return db, therapist, cases


def test_case_scoped_overlay_not_therapist_wide():
    db, therapist, cases = _therapist_and_cases()
    try:
        if len(cases) < 1:
            pytest.skip("Need a case")
        day = date(2026, 8, 10)
        db.add(
            TherapistLeave(
                therapist_user_id=therapist.id,
                leave_type=LeaveType.ANNUAL,
                billing_category=LeaveBillingCategory.PAID,
                start_date=day,
                end_date=day,
                status=LeaveStatus.APPROVED,
                case_id=cases[0].id,
                case_ids=[cases[0].id],
            )
        )
        db.commit()
        overlays = cal._leave_dates(db, therapist.id, day, day)
        row = overlays[day.isoformat()]
        assert row["therapist_wide"] is False
        assert cases[0].id in row["case_ids"]
        assert cal.is_day_on_leave(db, therapist.id, day, cases[0].id) is True
        if len(cases) > 1:
            assert cal.is_day_on_leave(db, therapist.id, day, cases[1].id) is False
        assert cal.is_therapist_wide_leave_day(db, therapist.id, day) is False
    finally:
        db.close()


def test_therapist_wide_overlay_blocks_whole_day():
    db, therapist, _cases = _therapist_and_cases()
    try:
        day = date(2026, 8, 11)
        db.add(
            TherapistLeave(
                therapist_user_id=therapist.id,
                leave_type=LeaveType.CASUAL,
                billing_category=LeaveBillingCategory.UNPAID,
                start_date=day,
                end_date=day,
                status=LeaveStatus.APPROVED,
            )
        )
        db.commit()
        overlays = cal._leave_dates(db, therapist.id, day, day)
        assert overlays[day.isoformat()]["therapist_wide"] is True
        assert cal.is_therapist_wide_leave_day(db, therapist.id, day) is True
    finally:
        db.close()


def test_disjoint_case_leaves_allowed_same_date():
    db, therapist, cases = _therapist_and_cases()
    try:
        if len(cases) < 2:
            pytest.skip("Need two cases")
        day = date(2026, 8, 12)
        db.add(
            TherapistLeave(
                therapist_user_id=therapist.id,
                leave_type=LeaveType.ANNUAL,
                billing_category=LeaveBillingCategory.PAID,
                start_date=day,
                end_date=day,
                status=LeaveStatus.APPROVED,
                case_id=cases[0].id,
                case_ids=[cases[0].id],
            )
        )
        db.commit()
        leave_service.create_therapist_leave_request(
            db,
            therapist=therapist,
            start_date=day,
            end_date=day,
            case_ids=[cases[1].id],
            auto_approve=True,
            reviewer_user_id=therapist.id,
        )
        db.commit()
        overlays = cal._leave_dates(db, therapist.id, day, day)
        assert set(overlays[day.isoformat()]["case_ids"]) == {cases[0].id, cases[1].id}
    finally:
        db.close()


def test_overlapping_same_case_blocked():
    db, therapist, cases = _therapist_and_cases()
    try:
        if len(cases) < 1:
            pytest.skip("Need a case")
        day = date(2026, 8, 13)
        db.add(
            TherapistLeave(
                therapist_user_id=therapist.id,
                leave_type=LeaveType.SICK,
                billing_category=LeaveBillingCategory.UNPAID,
                start_date=day,
                end_date=day,
                status=LeaveStatus.APPROVED,
                case_id=cases[0].id,
                case_ids=[cases[0].id],
            )
        )
        db.commit()
        with pytest.raises(ValueError, match="Leave already exists"):
            leave_service.create_therapist_leave_request(
                db,
                therapist=therapist,
                start_date=day,
                end_date=day,
                case_ids=[cases[0].id],
                auto_approve=True,
                reviewer_user_id=therapist.id,
            )
    finally:
        db.close()
