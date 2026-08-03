"""Step 5 — timestamp-complete eligibility; PENDING_REVIEW hold; SESSION-keyed approve in place."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerSourceType
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import billing_ledger_service, session_service


def _therapist_and_per_session_case(db):
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assert therapist
    case = db.scalars(
        select(Case)
        .join(CaseAssignment, CaseAssignment.case_id == Case.id)
        .where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            Case.billing_type == BillingType.PER_SESSION,
        )
    ).first()
    if case:
        return therapist, case
    assignment = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    assert assignment
    case = db.get(Case, assignment.case_id)
    case.billing_type = BillingType.PER_SESSION
    if case.client_rate_per_session_inr is None:
        case.client_rate_per_session_inr = 1500.0
    db.flush()
    return therapist, case


def _completed_session(db, *, therapist_id: int, case_id: int, scheduled: date | None = None):
    started = datetime.now(timezone.utc) - timedelta(hours=1)
    ended = started + timedelta(minutes=45)
    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_id,
        scheduled_date=scheduled or date(2026, 7, 15),
        start_time=time(10, 0),
        end_time=time(11, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.IN_PROGRESS,
        actual_start_at=started,
    )
    db.add(session)
    db.flush()
    return session_service.end_session(db, session, end_at=ended)


def _session_ledger_count(db, session_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(BillingLedger.session_id == session_id)
        )
        or 0
    )


def test_completed_without_approved_log_creates_pending_review_hold():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case.id)
        db.commit()
        rows = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].source_type == LedgerSourceType.SESSION
        assert rows[0].source_id == session.id
        assert rows[0].billable_status == BillableStatus.PENDING_REVIEW
        summary = billing_ledger_service.eligibility_exceptions_summary(
            db, ledger_month="2026-07", case_id=case.id
        )
        assert summary["logHoldCount"] >= 1
        assert summary["logHoldStatus"] == "PENDING_REVIEW"
    finally:
        db.close()


def test_approve_flips_same_row_no_daily_log_duplicate():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case.id)
        hold = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).one()
        hold_id = hold.id
        before = _session_ledger_count(db, session.id)
        assert before == 1

        log = DailyLog(
            session_id=session.id,
            attendance_status="PRESENT",
            activities_done="Worked on goals",
            observations="Steady session",
            approval_status=LogApprovalStatus.APPROVED.value,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.flush()
        session.daily_log = log
        billing_ledger_service.upsert_from_daily_log_approved(db, log)
        db.commit()

        after = _session_ledger_count(db, session.id)
        assert after == before == 1
        row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).one()
        assert row.id == hold_id
        assert row.billable_status == BillableStatus.BILLABLE
        assert row.source_type == LedgerSourceType.SESSION
        assert row.source_id == session.id
        daily_dupes = db.scalars(
            select(BillingLedger).where(
                BillingLedger.session_id == session.id,
                BillingLedger.source_type == LedgerSourceType.DAILY_LOG,
            )
        ).all()
        assert daily_dupes == []
    finally:
        db.close()


def test_time_confirmation_required_stays_out_of_billing_until_confirmed():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        started = datetime.now(timezone.utc) - timedelta(hours=2)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 7, 16),
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
            time_confirmation_required=True,
        )
        db.add(session)
        db.flush()
        ended = session_service.end_session(
            db, session, end_at=started + timedelta(minutes=50), auto_ended=True
        )
        assert ended.time_confirmation_required is True
        assert _session_ledger_count(db, ended.id) == 0
        queue = billing_ledger_service.list_needs_therapist_confirmation(
            db, case_id=case.id
        )
        assert any(q["sessionId"] == ended.id for q in queue)

        # Confirm via time edit (clears confirmation flag) → becomes PENDING_REVIEW hold.
        session_service.update_actual_times(
            db,
            ended,
            therapist.id,
            actual_start_at=started,
            actual_end_at=started + timedelta(minutes=45),
            edit_reason="Confirmed auto-ended times for billing",
        )
        db.commit()
        rows = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == ended.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].billable_status == BillableStatus.PENDING_REVIEW
    finally:
        db.close()


def test_reject_log_marks_existing_row_non_billable():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case.id)
        log = DailyLog(
            session_id=session.id,
            attendance_status="PRESENT",
            activities_done="Notes",
            observations="ok",
            approval_status=LogApprovalStatus.PENDING.value,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.flush()
        session.daily_log = log
        hold = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).one()
        assert hold.billable_status == BillableStatus.PENDING_REVIEW

        log.approval_status = LogApprovalStatus.REJECTED.value
        billing_ledger_service.sync_session_status(db, session)
        db.commit()
        row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).one()
        assert row.id == hold.id
        assert row.billable_status == BillableStatus.NON_BILLABLE
    finally:
        db.close()


def test_time_edit_updates_same_row_in_place():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case.id)
        hold = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).one()
        hold_id = hold.id
        new_start = session.actual_start_at
        new_end = session.actual_end_at + timedelta(minutes=5)
        session_service.update_actual_times(
            db,
            session,
            therapist.id,
            actual_start_at=new_start,
            actual_end_at=new_end,
            edit_reason="Therapist logged out late — corrected checkout",
        )
        db.commit()
        assert _session_ledger_count(db, session.id) == 1
        row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == session.id)
        ).one()
        assert row.id == hold_id
        assert row.source_type == LedgerSourceType.SESSION
        assert row.billable_status == BillableStatus.PENDING_REVIEW
    finally:
        db.close()


def test_july_orphan_pattern_surfaces_as_holds():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        ids = []
        for day in (10, 11, 12):
            s = _completed_session(
                db,
                therapist_id=therapist.id,
                case_id=case.id,
                scheduled=date(2026, 7, day),
            )
            ids.append(s.id)
        db.commit()
        holds = db.scalars(
            select(BillingLedger).where(
                BillingLedger.session_id.in_(ids),
                BillingLedger.billable_status == BillableStatus.PENDING_REVIEW,
            )
        ).all()
        assert len(holds) == 3
        assert all(h.source_type == LedgerSourceType.SESSION for h in holds)
        count = billing_ledger_service.count_log_holds(
            db, ledger_month="2026-07", case_id=case.id
        )
        assert count >= 3
    finally:
        db.close()


def test_void_after_hold_marks_non_billable_same_row():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_per_session_case(db)
        started = datetime.now(timezone.utc) - timedelta(minutes=30)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date.today(),
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
        )
        db.add(session)
        db.flush()
        ended = session_service.end_session(
            db, session, end_at=started + timedelta(minutes=20)
        )
        hold = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == ended.id)
        ).one()
        voided = session_service.void_session_before_log(db, ended, therapist.id)
        db.commit()
        assert voided.status in (SessionStatus.SCHEDULED, SessionStatus.CANCELLED)
        row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == ended.id)
        ).one()
        assert row.id == hold.id
        assert row.billable_status == BillableStatus.NON_BILLABLE
    finally:
        db.close()
