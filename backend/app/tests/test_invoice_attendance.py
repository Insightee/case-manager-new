"""Invoice attendance facts — leaves, child absence, pending submissions."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CompensationMode
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.ledger_billing import ProductBillingRule
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.services import invoice_attendance_service as attendance
from app.services import invoice_billing_service as billing
from app.seed.demo_seed import run as seed_run


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _therapist_and_case(db, *, product_module: str = "homecare") -> tuple[User, Case]:
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assignment = db.scalars(
        select(CaseAssignment)
        .join(Case, Case.id == CaseAssignment.case_id)
        .where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            Case.product_module.ilike(f"%{product_module}%"),
        )
    ).first()
    case = db.get(Case, assignment.case_id)
    return therapist, case


def _shadow_case(db) -> tuple[User, Case]:
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assignment = db.scalars(
        select(CaseAssignment)
        .join(Case, Case.id == CaseAssignment.case_id)
        .where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    for a in assignment:
        case = db.get(Case, a.case_id)
        if case and attendance.billing_profile_for_case(case) == attendance.BillingProfile.CALENDAR_DAY:
            return therapist, case
    pytest.skip("No shadow/calendar-day case in seed")


def test_session_based_leave_taken_no_deduction():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_case(db)
        ym = "2026-06"
        leave = TherapistLeave(
            therapist_user_id=therapist.id,
            case_id=case.id,
            leave_type=LeaveType.CASUAL,
            billing_category=LeaveBillingCategory.UNPAID,
            start_date=date(2026, 6, 3),
            end_date=date(2026, 6, 5),
            reason="Homecare leave informational",
            status=LeaveStatus.APPROVED,
        )
        db.add(leave)
        db.commit()

        preview = billing.build_month_preview(db, therapist.id, ym)
        assert preview["leave_deduction_inr"] == 0
        assert preview["attendance_summary"]["leave_taken"] == 3
        assert preview["attendance_summary"].get("paid_leaves") is None or preview["attendance_summary"]["paid_leaves"] == 0

        db.delete(leave)
        db.commit()
    finally:
        db.close()


def test_calendar_day_unpaid_leave_deduction():
    db = SessionLocal()
    try:
        therapist, case = _shadow_case(db)
        ym = "2026-07"
        leave = TherapistLeave(
            therapist_user_id=therapist.id,
            case_id=case.id,
            leave_type=LeaveType.UNPAID,
            billing_category=LeaveBillingCategory.UNPAID,
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 11),
            reason="Shadow unpaid leave",
            status=LeaveStatus.APPROVED,
            includes_shadow_cases=True,
        )
        db.add(leave)
        db.commit()

        preview = billing.build_month_preview(db, therapist.id, ym)
        assert preview["attendance_summary"]["unpaid_leaves"] >= 2
        assert preview["leave_deduction_inr"] > 0

        db.delete(leave)
        db.commit()
    finally:
        db.close()


def test_pending_submitted_log_in_pending_approval():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_case(db)
        ym = "2026-08"
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 8, 31),
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
        )
        db.add(session)
        db.flush()
        log = DailyLog(
            session_id=session.id,
            attendance_status="present",
            submitted_at=datetime.now(timezone.utc),
            approval_status=LogApprovalStatus.PENDING,
            late_addition=False,
        )
        db.add(log)
        db.commit()

        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym=ym)
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        pending = case_facts["pending_approval_lines"]
        assert any(
            p.get("flags", {}).get("pending_reason") == "Awaiting log approval" for p in pending
        )

        db.delete(log)
        db.delete(session)
        db.commit()
    finally:
        db.close()


def test_forgotten_session_pending_then_approved():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_case(db)
        ym = "2026-04"
        created = billing.create_late_session(
            db,
            therapist.id,
            case_id=case.id,
            month=ym,
            session_date=date(2026, 4, 18),
            start_time=time(15, 0),
            end_time=time(16, 0),
            attendance_status="present",
            activities_done="Make-up",
            observations=None,
            late_reason="Forgot to log",
        )
        db.commit()
        preview = billing.build_month_preview(db, therapist.id, ym)
        case_group = next(c for c in preview["cases"] if c["case_id"] == case.id)
        pending = case_group["pending_approval_lines"]
        assert any(p.get("flags", {}).get("pending_reason") == "Added late" for p in pending)

        log = db.get(DailyLog, created["daily_log_id"])
        log.approval_status = LogApprovalStatus.APPROVED
        db.commit()
        approved_preview = billing.build_month_preview(db, therapist.id, ym)
        approved_case = next(c for c in approved_preview["cases"] if c["case_id"] == case.id)
        assert any(
            sl.get("session_id") == created["session_id"] for sl in approved_case["session_lines"]
        )

        session = db.get(TherapySession, created["session_id"])
        db.delete(log)
        db.delete(session)
        db.commit()
    finally:
        db.close()


def test_rejected_log_in_rejected_notes():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_case(db)
        ym = "2026-03"
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 3, 12),
            status=SessionStatus.COMPLETED,
        )
        db.add(session)
        db.flush()
        log = DailyLog(
            session_id=session.id,
            attendance_status="present",
            approval_status=LogApprovalStatus.REJECTED,
            late_reason="Duplicate entry",
        )
        db.add(log)
        db.commit()

        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym=ym)
        assert any(n["type"] == "session_log" for n in facts["rejected_notes"])
        preview = billing.build_month_preview(db, therapist.id, ym)
        assert preview["subtotal_inr"] >= 0

        db.delete(log)
        db.delete(session)
        db.commit()
    finally:
        db.close()


def test_child_absence_not_payable_rejected_notes():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_case(db)
        rule = attendance._resolve_rule(db, case)
        if rule:
            rule.child_absent_therapist_payable = False
            rule.package_consumes_on_child_absent = False
        ym = "2026-02"
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 2, 8),
            status=SessionStatus.CLIENT_ABSENT,
        )
        db.add(session)
        db.flush()
        req = SessionAbsenceRequest(
            session_id=session.id,
            case_id=case.id,
            therapist_user_id=therapist.id,
            absence_type=SessionAbsenceType.CLIENT_ABSENT,
            status=SessionAbsenceStatus.APPROVED,
            reason="Child sick",
            requested_by_user_id=therapist.id,
        )
        db.add(req)
        db.commit()

        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym=ym)
        assert any(n["type"] == "child_absence" for n in facts["rejected_notes"])

        db.delete(req)
        db.delete(session)
        if rule:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()


def test_apply_preview_edits_preserves_leave_deduction():
    db = SessionLocal()
    try:
        therapist, _case = _shadow_case(db)
        ym = "2026-07"
        preview = billing.build_month_preview(db, therapist.id, ym)
        leave_before = preview["leave_deduction_inr"]
        if not preview["cases"]:
            pytest.skip("No cases in preview")
        first_line = next(
            (l for c in preview["cases"] for l in c.get("session_lines", []) if l.get("session_id")),
            None,
        )
        if not first_line:
            pytest.skip("No excludable session lines")
        edited = billing.apply_preview_edits(
            preview, {"exclude_session_ids": [first_line["session_id"]]}
        )
        assert edited["leave_deduction_inr"] == leave_before
        assert edited["subtotal_inr"] <= preview["subtotal_inr"]
    finally:
        db.close()


def test_zero_activity_case_has_activity_false():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = Case(
            case_code="TEST-ZERO-ACT",
            child_id=1,
            service_type="Homecare",
            product_module="homecare",
            billing_type=BillingType.PER_SESSION,
            compensation_mode=CompensationMode.PERCENTAGE,
            pay_share_amount_inr=500,
            client_rate_per_session_inr=1000,
        )
        db.add(case)
        db.flush()
        db.add(
            CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist.id,
                status=CaseAssignmentStatus.ACTIVE,
                start_date=date(2026, 1, 1),
            )
        )
        db.commit()

        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym="2099-01")
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        assert case_facts["has_activity"] is False

        assignment = db.scalars(
            select(CaseAssignment).where(CaseAssignment.case_id == case.id)
        ).first()
        db.delete(assignment)
        db.delete(case)
        db.commit()
    finally:
        db.close()


def test_child_absence_payable_consumes_package_slot():
    db = SessionLocal()
    try:
        therapist, case = _therapist_and_case(db)
        if case.billing_type != BillingType.PACKAGE:
            case.billing_type = BillingType.PACKAGE
            case.package_session_count = case.package_session_count or 30
            case.pay_share_amount_inr = case.pay_share_amount_inr or 22000
        rule = attendance._resolve_rule(db, case)
        if not rule:
            rule = ProductBillingRule(
                product_name="Test package",
                product_category="Homecare",
                product_module=case.product_module,
                billing_model="PREPAID_PACKAGE",
                child_absent_therapist_payable=True,
                package_consumes_on_child_absent=True,
                active=True,
            )
            db.add(rule)
            db.flush()
            case.product_billing_rule_id = rule.id
        else:
            rule.child_absent_therapist_payable = True
            rule.package_consumes_on_child_absent = True
        db.commit()

        per_session = round(float(case.pay_share_amount_inr) / int(case.package_session_count), 2)
        ym = "2026-01"
        absence_session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 1, 5),
            status=SessionStatus.CLIENT_ABSENT,
        )
        db.add(absence_session)
        db.flush()
        db.add(
            SessionAbsenceRequest(
                session_id=absence_session.id,
                case_id=case.id,
                therapist_user_id=therapist.id,
                absence_type=SessionAbsenceType.CLIENT_ABSENT,
                status=SessionAbsenceStatus.APPROVED,
                reason="Approved absence",
                requested_by_user_id=therapist.id,
            )
        )
        db.commit()

        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym=ym)
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        billable = [l for l in case_facts["child_absence_lines"] if l.get("included")]
        assert billable
        assert billable[0]["ui_label"] == "Child absence (uses package slot)"
        assert billable[0]["amount_inr"] == pytest.approx(per_session, rel=0.01)

        req = db.scalars(
            select(SessionAbsenceRequest).where(SessionAbsenceRequest.session_id == absence_session.id)
        ).first()
        db.delete(req)
        db.delete(absence_session)
        db.commit()
    finally:
        db.close()
