"""Session duration compliance: audit outliers and therapist warnings."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.models.case import Case, CaseDayType, CaseStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.services import session_duration_compliance_service as svc


def _case(*, product_module: str = "homecare", day_type: CaseDayType | None = None) -> Case:
    return Case(
        id=1,
        case_code="C-001",
        child_id=1,
        service_type="OT",
        product_module=product_module,
        day_type=day_type,
        status=CaseStatus.ACTIVE,
    )


def _session_and_log(
    *,
    product_module: str = "homecare",
    day_type: CaseDayType | None = None,
    duration_mins: int = 90,
    approved: bool = False,
    attendance: str = "PRESENT",
    session_status: SessionStatus = SessionStatus.COMPLETED,
) -> tuple[Case, TherapySession, DailyLog]:
    case = _case(product_module=product_module, day_type=day_type)
    start = datetime(2026, 8, 5, 4, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration_mins)
    session = TherapySession(
        id=10,
        case_id=case.id,
        therapist_user_id=2,
        scheduled_date=date(2026, 8, 5),
        start_time=time(9, 30),
        end_time=time(11, 0),
        mode=SessionMode.HOME,
        status=session_status,
        actual_start_at=start,
        actual_end_at=end,
    )
    log = DailyLog(
        id=20,
        session_id=session.id,
        attendance_status=attendance,
        approval_status=LogApprovalStatus.APPROVED if approved else LogApprovalStatus.PENDING,
    )
    return case, session, log


def test_effective_duration_uses_clock_when_pending():
    _, session, log = _session_and_log(duration_mins=75, approved=False)
    assert svc.effective_duration_minutes(session, log) == 75


def test_effective_duration_uses_edited_when_approved():
    case, session, log = _session_and_log(duration_mins=60, approved=True)
    session.edited_start_at = session.actual_start_at
    session.edited_end_at = session.actual_start_at + timedelta(minutes=95)
    assert svc.effective_duration_minutes(session, log) == 95


def test_is_billable_session_log_excludes_absence():
    _, session, log = _session_and_log(attendance="CLIENT_ABSENT")
    assert svc.is_billable_session_log(session, log) is False


def test_is_billable_session_log_excludes_cancelled():
    _, session, log = _session_and_log(session_status=SessionStatus.CANCELLED)
    assert svc.is_billable_session_log(session, log) is False


def test_audit_outlier_shadow_under_3h():
    assert svc.audit_outlier_flag("shadow_support", 179) == "shadow_under_3h"


def test_audit_outlier_homecare_under_30m():
    assert svc.audit_outlier_flag("homecare", 29) == "homecare_under_30m"


def test_audit_outlier_over_10h():
    assert svc.audit_outlier_flag("homecare", 601) == "over_10h"
    assert svc.audit_outlier_flag("shadow_support", 601) == "over_10h"


def test_audit_outlier_none_for_normal():
    assert svc.audit_outlier_flag("homecare", 90) is None
    assert svc.audit_outlier_flag("shadow_support", 240) is None


def test_expected_bounds_scheduled():
    case, session, _ = _session_and_log()
    bounds = svc.expected_duration_bounds(case, session)
    assert bounds.has_schedule is True
    assert bounds.min_mins == bounds.max_mins == 90


def test_expected_bounds_shadow_half_day():
    case, session, _ = _session_and_log(product_module="shadow_support", day_type=CaseDayType.HALF_DAY)
    session.start_time = None
    session.end_time = None
    bounds = svc.expected_duration_bounds(case, session)
    assert bounds.min_mins == bounds.max_mins == 300


def test_expected_bounds_homecare_unscheduled():
    case, session, _ = _session_and_log()
    session.start_time = None
    session.end_time = None
    bounds = svc.expected_duration_bounds(case, session)
    assert bounds.min_mins == 60
    assert bounds.max_mins == 240


def test_duration_compliance_warning_homecare_short():
    case, session, log = _session_and_log(duration_mins=45)
    session.start_time = None
    session.end_time = None
    warning = svc.duration_compliance_warning(case, session, log)
    assert warning is not None
    assert warning["code"] == "under_minimum"
    assert warning["actual_mins"] == 45


def test_duration_compliance_warning_none_when_in_range():
    case, session, log = _session_and_log(duration_mins=90)
    assert svc.duration_compliance_warning(case, session, log) is None
