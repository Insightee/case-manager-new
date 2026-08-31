"""Therapist invoice buckets — pending vs still-paid vs cancelled-not-billed."""

from __future__ import annotations

import base64
import re
import zlib
from datetime import date, time

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.services import invoice_attendance_service as attendance
from app.services import invoice_billing_service as billing
from app.services import therapist_invoice_labels as labels
from app.services import therapist_statement_pdf_service as pdf_svc
from app.seed.demo_seed import run as seed_run


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _therapist(db) -> User:
    return db.scalars(select(User).where(User.email == "therapist@demo.com")).first()


def _case_for_module(db, therapist: User, module_substr: str) -> Case:
    rows = db.scalars(
        select(CaseAssignment)
        .join(Case, Case.id == CaseAssignment.case_id)
        .where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            Case.product_module.ilike(f"%{module_substr}%"),
        )
    ).all()
    for a in rows:
        case = db.get(Case, a.case_id)
        if case:
            return case
    pytest.skip(f"No {module_substr} case for therapist")


def test_homecare_child_absence_is_info_not_pending():
    db = SessionLocal()
    try:
        therapist = _therapist(db)
        case = _case_for_module(db, therapist, "homecare")
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 6, 10),
            start_time=time(9, 0),
            end_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.CLIENT_ABSENT,
        )
        db.add(session)
        db.flush()
        req = SessionAbsenceRequest(
            session_id=session.id,
            case_id=case.id,
            therapist_user_id=therapist.id,
            requested_by_user_id=therapist.id,
            absence_type=SessionAbsenceType.CLIENT_ABSENT,
            status=SessionAbsenceStatus.APPROVED,
            reason="Family travel",
        )
        db.add(req)
        db.commit()

        facts = attendance.month_attendance_facts(
            db, therapist_user_id=therapist.id, ym="2026-06", case=case
        )
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        abs_lines = case_facts["child_absence_lines"]
        assert abs_lines
        line = abs_lines[0]
        assert line["breakdown_bucket"] == labels.BUCKET_INFO
        assert line["ui_label"] == "Session cancelled"
        assert line.get("status_tag") in (None, "")
        assert float(line.get("display_amount_inr") or 0) == 0
        assert all(l.get("breakdown_bucket") != labels.BUCKET_PENDING or l.get("line_kind") == "PENDING_ABSENCE" for l in abs_lines)
    finally:
        db.close()


def test_shadow_child_away_is_session_cancelled_zero():
    db = SessionLocal()
    try:
        therapist = _therapist(db)
        case = _case_for_module(db, therapist, "shadow")
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 6, 12),
            start_time=time(9, 0),
            end_time=time(14, 0),
            mode=SessionMode.SCHOOL,
            status=SessionStatus.CLIENT_ABSENT,
        )
        db.add(session)
        db.flush()
        req = SessionAbsenceRequest(
            session_id=session.id,
            case_id=case.id,
            therapist_user_id=therapist.id,
            requested_by_user_id=therapist.id,
            absence_type=SessionAbsenceType.CLIENT_ABSENT,
            status=SessionAbsenceStatus.APPROVED,
            reason="Child unwell",
        )
        db.add(req)
        db.commit()

        facts = attendance.month_attendance_facts(
            db, therapist_user_id=therapist.id, ym="2026-06", case=case
        )
        case_facts = next(c for c in facts["cases"] if c["case_id"] == case.id)
        line = case_facts["child_absence_lines"][0]
        assert line["breakdown_bucket"] == labels.BUCKET_INFO
        assert line["ui_label"] == "Session cancelled"
        assert float(line.get("display_amount_inr") or 0) == 0
        assert line.get("status_tag") in (None, "")
    finally:
        db.close()


def _pdf_extract_text(raw: bytes) -> bytes:
    """Best-effort extract of literal strings from ReportLab PDF content streams."""
    out = []
    for m in re.finditer(rb"/Length\s+(\d+)\s*\n>>\nstream\n", raw):
        length = int(m.group(1))
        chunk = raw[m.end() : m.end() + length]
        try:
            if b"~>" in chunk:
                wrapped = chunk if chunk.startswith(b"<~") else b"<~" + chunk
                if not wrapped.endswith(b"~>"):
                    wrapped = wrapped + b"~>"
                decoded = base64.a85decode(wrapped, adobe=True)
                chunk = zlib.decompress(decoded)
            else:
                chunk = zlib.decompress(chunk)
        except Exception:
            pass
        out.append(chunk)
    text = b"\n".join(out)
    # Also join PDF string literals for easier asserts
    literals = re.findall(rb"\((?:\\.|[^\\)])*\)", text)
    return text + b"\n" + b" ".join(s[1:-1] for s in literals)


def test_pdf_uses_childcare_company_and_session_rows():
    payload = {
        "statementNumber": "INV-0001",
        "monthLabel": "Jun 2026",
        "generatedAt": "01 Jun 2026",
        "status": "In Review",
        "therapistName": "Demo Therapist",
        "employeeId": "T1",
        "designation": "Therapist",
        "pan": "—",
        "bankAccount": "—",
        "sessionsCount": 2,
        "grossInr": 6000,
        "leaveDeductionInr": 0,
        "adjustmentInr": 0,
        "tdsInr": 600,
        "netPayableInr": 5400,
        "company": pdf_svc.INSIGHTE_COMPANY,
        "cases": [
            {
                "caseCode": "HC-1",
                "childName": "Asha",
                "homecare": True,
                "caseTotal": 6000,
                "rows": [["2026-06-01", "Session completed", "₹3,000", "Yes"]],
                "nextMonthPlan": {"session_count": 4, "notes": "Prefer mornings"},
            }
        ],
        "leaveBalance": None,
        "notes": None,
    }
    raw = pdf_svc.therapist_statement_pdf_bytes(payload)
    assert raw.startswith(b"%PDF")
    assert b"Session Logger" not in raw
    text = _pdf_extract_text(raw)
    assert b"Insighte" in text
    assert b"Homecare" in text or b"Session completed" in text
    assert b"4 session" in text or b"Next month" in text


def test_next_month_plan_normalized_on_preview_edit():
    preview = {
        "month_label": "Jun 2026",
        "therapist_user_id": 1,
        "leave_deduction_inr": 0,
        "subtotal_inr": 0,
        "net_amount_inr": 0,
        "total_sessions": 0,
        "cases": [
            {
                "case_id": 42,
                "case_code": "HC-PLAN",
                "billing": {"billing_type": "PER_SESSION", "product_module": "homecare"},
                "billing_profile": "session_based",
                "session_lines": [],
                "child_absence_lines": [],
                "pending_approval_lines": [],
                "cycle": {},
                "therapist_share_inr": 0,
                "included_sessions": 0,
                "additional_sessions": 0,
            }
        ],
    }
    edited = billing.apply_preview_edits(
        preview,
        {
            "next_month_plans": {
                "42": {
                    "notes": "Morning preference",
                    "session_count": 6,
                }
            }
        },
    )
    plan = edited["cases"][0]["next_month_session_plan"]
    assert plan["notes"] == "Morning preference"
    assert plan["session_count"] == 6
