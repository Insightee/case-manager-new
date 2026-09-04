"""Invoice attendance facts — leaves, child absence, pending submissions."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import uuid

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseDayType, CaseStatus, CompensationMode
from app.models.child import Child
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
        assert preview["attendance_summary"].get("paid_leaves") is None

        db.delete(leave)
        db.commit()
    finally:
        db.close()


def test_zero_leave_taken_omitted_from_summary():
    db = SessionLocal()
    try:
        therapist, _case = _therapist_and_case(db)
        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym="2026-03")
        assert facts["attendance_summary"].get("leave_taken") is None
        assert facts["attendance_summary"].get("paid_leaves") is None
        assert facts["attendance_summary"].get("unpaid_leaves") is None
    finally:
        db.close()


def test_invoice_breakdown_from_preview_net_matches_subtotal():
    db = SessionLocal()
    try:
        from app.models.invoice import Invoice, InvoiceStatus

        invoice = db.scalars(
            select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        ).first()
        if not invoice:
            pytest.skip("No in-review invoice in seed")
        breakdown = billing.invoice_breakdown(db, invoice.id)
        if not breakdown.get("from_preview"):
            pytest.skip("Invoice has persisted lines — covered by test_invoice_breakdown_stored")
        assert breakdown["subtotal_inr"] - breakdown["leave_deduction_inr"] == pytest.approx(
            breakdown["net_amount_inr"], rel=0.01
        )
        assert breakdown["amount_inr"] == breakdown["net_amount_inr"]
    finally:
        db.close()


def _isolated_shadow_calendar_case(db) -> tuple[User, Case]:
    """Dedicated shadow case so calendar-day leave tests do not depend on seed case modules."""
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    child = db.scalars(select(Child).limit(1)).first()
    assert therapist is not None and child is not None
    case = Case(
        case_code=f"SHADOW-LEAVE-{uuid.uuid4().hex[:8]}",
        child_id=child.id,
        service_type="Shadow Support",
        product_module="shadow_support",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.PER_SESSION,
        compensation_mode=CompensationMode.FIXED_LUMP,
        client_rate_per_session_inr=1000,
        therapist_fixed_pay_inr=20000,
        pay_share_amount_inr=20000,
        day_type=CaseDayType.FULL_DAY,
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
    return therapist, case


def test_calendar_day_unpaid_leave_deduction():
    db = SessionLocal()
    try:
        therapist, case = _isolated_shadow_calendar_case(db)
        ym = "2099-08"
        for day in (date(2099, 8, 10), date(2099, 8, 11)):
            db.add(
                TherapySession(
                    case_id=case.id,
                    therapist_user_id=therapist.id,
                    scheduled_date=day,
                    start_time=time(9, 0),
                    end_time=time(10, 0),
                    mode=SessionMode.SCHOOL,
                    status=SessionStatus.SCHEDULED,
                )
            )
        leave = TherapistLeave(
            therapist_user_id=therapist.id,
            case_id=case.id,
            leave_type=LeaveType.UNPAID,
            billing_category=LeaveBillingCategory.UNPAID,
            paid_days=0,
            unpaid_days=2,
            start_date=date(2099, 8, 10),
            end_date=date(2099, 8, 11),
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
            p.get("flags", {}).get("pending_reason") == "Waiting for log review" for p in pending
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
        assert any(p.get("flags", {}).get("pending_reason") == "Added from invoice" for p in pending)

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
        original_payable = rule.child_absent_therapist_payable if rule else None
        original_consumes = rule.package_consumes_on_child_absent if rule else None
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
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        info_lines = [
            l
            for l in case_facts["child_absence_lines"]
            if l.get("breakdown_bucket") == "info"
        ]
        # Non-payable child away stays on the breakdown as Session cancelled — not as rejected_notes spam.
        assert info_lines or any(
            "cancelled" in (l.get("ui_label") or "").lower() for l in case_facts["child_absence_lines"]
        )
        assert not any(
            n["type"] == "child_absence" and n.get("status") != "REJECTED"
            for n in facts["rejected_notes"]
        )

        db.delete(req)
        db.delete(session)
        if rule:
            rule.child_absent_therapist_payable = original_payable
            rule.package_consumes_on_child_absent = original_consumes
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
        therapist, existing = _therapist_and_case(db)
        case = Case(
            case_code="TEST-ZERO-ACT",
            child_id=existing.child_id,
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
        db.flush()

        facts = attendance.month_attendance_facts(db, therapist_user_id=therapist.id, ym="2099-01")
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        assert case_facts["has_activity"] is False
        db.rollback()
    finally:
        db.close()


def test_homecare_child_absence_never_billed_even_if_rule_payable():
    """Homecare pay is sessions-done only — child away cannot consume package pay."""
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
        lines = case_facts["child_absence_lines"]
        assert lines
        assert lines[0]["included"] is False
        assert lines[0]["breakdown_bucket"] == "info"
        assert lines[0]["ui_label"] == "Session cancelled"
        assert float(lines[0].get("amount_inr") or 0) == 0

        req = db.scalars(
            select(SessionAbsenceRequest).where(SessionAbsenceRequest.session_id == absence_session.id)
        ).first()
        db.delete(req)
        db.delete(absence_session)
        db.commit()
    finally:
        db.close()
