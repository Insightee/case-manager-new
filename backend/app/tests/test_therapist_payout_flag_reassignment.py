"""Reassignment payout flag — created on flagged change, refused while a transition is open."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseDayType, CompensationMode
from app.models.therapist_payout_flag import TherapistPayoutFlag
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import assignment_service, therapist_transition_service


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _throwaway_therapist(db, email: str) -> User:
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing:
        return existing
    user = User(
        email=email,
        password_hash=hash_password("demo123"),
        full_name=email.split("@")[0].replace(".", " ").title(),
    )
    db.add(user)
    db.flush()
    return user


def _case_with_single_therapist(db, *, email: str) -> tuple[Case, User]:
    case = db.scalar(select(Case).order_by(Case.id))
    assert case is not None
    case.billing_type = BillingType.PER_SESSION
    case.client_rate_per_session_inr = 1200
    case.compensation_mode = CompensationMode.PERCENTAGE
    case.pay_share_amount_inr = 600
    case.day_type = case.day_type or CaseDayType.FULL_DAY
    for row in db.scalars(
        select(CaseAssignment).where(CaseAssignment.case_id == case.id)
    ).all():
        if row.status == CaseAssignmentStatus.ACTIVE:
            row.status = CaseAssignmentStatus.ENDED
            row.end_date = date(2026, 7, 1)
    outgoing = _throwaway_therapist(db, email)
    assignment_service.create_assignment(
        db,
        case_id=case.id,
        therapist_user_id=outgoing.id,
        assigned_by_user_id=outgoing.id,
        start_date=date(2026, 7, 1),
    )
    db.flush()
    return case, outgoing


def test_flagged_reassignment_records_month_flag_for_outgoing_therapist():
    db = SessionLocal()
    try:
        case, outgoing = _case_with_single_therapist(
            db, email="flag.outgoing@demo.com"
        )
        incoming = _throwaway_therapist(db, "flag.incoming@demo.com")

        assignment_service.create_assignment(
            db,
            case_id=case.id,
            therapist_user_id=incoming.id,
            assigned_by_user_id=incoming.id,
            start_date=date(2026, 11, 3),
            reason_for_change="Therapist left before completing handover",
            flag_outgoing_therapist=True,
        )

        flags = list(
            db.scalars(
                select(TherapistPayoutFlag).where(
                    TherapistPayoutFlag.therapist_user_id == outgoing.id,
                    TherapistPayoutFlag.is_active.is_(True),
                )
            ).all()
        )
        assert len(flags) == 1
        assert flags[0].billing_month == "2026-11"
        assert flags[0].case_id == case.id
        assert flags[0].cleared_at is None
    finally:
        db.rollback()
        db.close()


def test_unflagged_reassignment_records_no_flag():
    db = SessionLocal()
    try:
        case, outgoing = _case_with_single_therapist(
            db, email="noflag.outgoing@demo.com"
        )
        incoming = _throwaway_therapist(db, "noflag.incoming@demo.com")

        assignment_service.create_assignment(
            db,
            case_id=case.id,
            therapist_user_id=incoming.id,
            assigned_by_user_id=incoming.id,
            start_date=date(2026, 11, 3),
            reason_for_change="Planned caseload rebalance",
        )

        flag = db.scalar(
            select(TherapistPayoutFlag).where(
                TherapistPayoutFlag.therapist_user_id == outgoing.id
            )
        )
        assert flag is None
    finally:
        db.rollback()
        db.close()


def test_open_transition_blocks_reassignment_and_flagging():
    db = SessionLocal()
    try:
        case, outgoing = _case_with_single_therapist(
            db, email="locked.outgoing@demo.com"
        )
        incoming = _throwaway_therapist(db, "locked.incoming@demo.com")
        start = date.today() + timedelta(days=20)

        therapist_transition_service.create_transition(
            db,
            case_id=case.id,
            incoming_therapist_user_id=incoming.id,
            transition_dates=[
                (start + timedelta(days=offset)).isoformat() for offset in range(3)
            ],
            created_by_user_id=outgoing.id,
            billing_update={
                "billing_type": "PER_SESSION",
                "client_rate_per_session_inr": 1500,
                "compensation_mode": "PERCENTAGE",
                "pay_share_amount_inr": 800,
            },
        )

        with pytest.raises(ValueError, match="transition"):
            assignment_service.create_assignment(
                db,
                case_id=case.id,
                therapist_user_id=incoming.id,
                assigned_by_user_id=outgoing.id,
                start_date=date(2026, 11, 3),
                reason_for_change="Therapist left mid handover",
                flag_outgoing_therapist=True,
            )

        flag = db.scalar(
            select(TherapistPayoutFlag).where(
                TherapistPayoutFlag.therapist_user_id == outgoing.id
            )
        )
        assert flag is None
    finally:
        db.rollback()
        db.close()
