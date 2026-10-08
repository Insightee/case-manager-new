"""Preview/submit and month-end auto-submit when PACKAGE cases lack package_session_count."""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.billing_calc_errors import MISSING_PACKAGE_COUNT_CODE
from app.core.database import SessionLocal
from app.core.permissions import RoleName
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseStatus, CompensationMode
from app.models.child import Child
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.seed.demo_seed import get_or_create_user, run as seed_run
from app.services import invoice_billing_service as billing
from app.services.invoice_auto_submit_service import auto_submit_unsubmitted_invoices

client = TestClient(app)

YM = "2099-08"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _assert_missing_package_detail(response, *, case_id: int, case_code: str) -> None:
    assert response.status_code == 422, response.text
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == MISSING_PACKAGE_COUNT_CODE
    assert case_code in detail.get("message", "")
    assert detail.get("caseId") == case_id


def _package_case_with_assignment(db, therapist: User) -> Case:
    child = db.scalars(select(Child).limit(1)).first()
    assert child is not None
    case = Case(
        case_code=f"PKG-ROUTE-{uuid.uuid4().hex[:8]}",
        child_id=child.id,
        service_type="Homecare",
        product_module="homecare",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.PACKAGE,
        package_session_count=10,
        package_amount_inr=25000,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=15000,
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
    db.refresh(case)
    return case


def _per_session_case_with_assignment(db, therapist: User) -> Case:
    child = db.scalars(select(Child).limit(1)).first()
    assert child is not None
    case = Case(
        case_code=f"PS-ROUTE-{uuid.uuid4().hex[:8]}",
        child_id=child.id,
        service_type="Homecare",
        product_module="homecare",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.PER_SESSION,
        client_rate_per_session_inr=2000,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=1200,
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
    db.refresh(case)
    return case


def _approved_late_session(db, therapist: User, case: Case, ym: str = YM) -> None:
    year, month_num = 2099, 8
    created = billing.create_late_session(
        db,
        therapist.id,
        case_id=case.id,
        month=ym,
        session_date=date(year, month_num, 12),
        start_time=time(10, 0),
        end_time=time(11, 0),
        attendance_status="present",
        activities_done="missing package count route test",
        observations=None,
        late_reason="fixture",
    )
    log = db.get(DailyLog, created["daily_log_id"])
    log.approval_status = LogApprovalStatus.APPROVED
    db.commit()


def _broken_package_fixture() -> tuple[int, str, int]:
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = _package_case_with_assignment(db, therapist)
        _approved_late_session(db, therapist, case)
        case.package_session_count = None
        db.commit()
        return therapist.id, case.case_code, case.id
    finally:
        db.close()


def _cleanup_case(case_id: int) -> None:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if not case:
            return
        case.package_session_count = 10
        case.status = CaseStatus.DEACTIVATED
        for assignment in db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all():
            assignment.status = CaseAssignmentStatus.ENDED
        db.commit()
    finally:
        db.close()


def test_preview_missing_package_count_returns_422():
    therapist_id, case_code, case_id = _broken_package_fixture()
    headers = _login("therapist@demo.com")
    r = client.get(f"/api/v1/invoices/preview?month={YM}", headers=headers)
    _assert_missing_package_detail(r, case_id=case_id, case_code=case_code)
    _cleanup_case(case_id)


def test_admin_submit_missing_package_count_returns_422():
    therapist_id, case_code, case_id = _broken_package_fixture()
    headers = _login("finance@demo.com")
    r = client.post(
        "/api/v1/invoices/submit-for-therapist",
        headers=headers,
        json={"therapist_user_id": therapist_id, "month": YM},
    )
    _assert_missing_package_detail(r, case_id=case_id, case_code=case_code)
    _cleanup_case(case_id)


def test_therapist_submit_missing_package_count_returns_422():
    _therapist_id, case_code, case_id = _broken_package_fixture()

    headers = _login("therapist@demo.com")
    r = client.post(
        "/api/v1/invoices/submit",
        headers=headers,
        json={"month": YM, "notes": "should fail"},
    )
    _assert_missing_package_detail(r, case_id=case_id, case_code=case_code)
    _cleanup_case(case_id)


def test_month_end_auto_submit_skips_bad_therapist_and_submits_good():
    db = SessionLocal()
    case_ids: list[int] = []
    good_therapist_id: int | None = None
    bad_therapist_id: int | None = None
    try:
        bad_therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        good_therapist = get_or_create_user(
            db,
            "autosubmit-good@demo.com",
            "demo123",
            "Auto Submit Good",
            RoleName.THERAPIST.value,
        )
        db.commit()

        bad_case = _package_case_with_assignment(db, bad_therapist)
        _approved_late_session(db, bad_therapist, bad_case)
        bad_case.package_session_count = None
        case_ids.append(bad_case.id)

        good_case = _per_session_case_with_assignment(db, good_therapist)
        _approved_late_session(db, good_therapist, good_case)
        case_ids.append(good_case.id)

        for therapist_id in (bad_therapist.id, good_therapist.id):
            for inv in db.scalars(
                select(Invoice).where(
                    Invoice.therapist_user_id == therapist_id,
                    Invoice.month.in_([YM, "Aug 2099"]),
                    Invoice.status != InvoiceStatus.REJECTED,
                )
            ).all():
                db.delete(inv)
        db.commit()

        bad_therapist_id = bad_therapist.id
        good_therapist_id = good_therapist.id
        bad_case_id = bad_case.id
        bad_case_code = bad_case.case_code
    finally:
        db.close()

    db = SessionLocal()
    try:
        result = auto_submit_unsubmitted_invoices(db, YM)
    finally:
        db.close()

    submitted_ids = {row["therapist_user_id"] for row in result["submitted"]}
    assert good_therapist_id in submitted_ids
    bad_skips = [
        s
        for s in result["skipped"]
        if s.get("therapist_user_id") == bad_therapist_id
        and s.get("reason") == "missing_package_session_count"
    ]
    assert bad_skips, result["skipped"]
    assert bad_skips[0].get("case_id") == bad_case_id
    assert bad_skips[0].get("case_code") == bad_case_code

    db = SessionLocal()
    try:
        for cid in case_ids:
            case = db.get(Case, cid)
            if case:
                case.status = CaseStatus.DEACTIVATED
                if case.billing_type == BillingType.PACKAGE:
                    case.package_session_count = 10
                for assignment in db.scalars(
                    select(CaseAssignment).where(CaseAssignment.case_id == cid)
                ).all():
                    assignment.status = CaseAssignmentStatus.ENDED
        if good_therapist_id:
            for inv in db.scalars(
                select(Invoice).where(
                    Invoice.therapist_user_id == good_therapist_id,
                    Invoice.month.in_([YM, "Aug 2099"]),
                )
            ).all():
                db.delete(inv)
        db.commit()
    finally:
        db.close()
