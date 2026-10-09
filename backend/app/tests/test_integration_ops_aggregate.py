"""Org-wide integration ops counts: scope, IST days, and fixture deltas."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.case import BillingType, Case, CaseStatus
from app.models.child import Child
from app.models.client_billing import CarePackage, CarePackageStatus
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerEventType, LedgerSourceType
from app.models.leave import LeaveStatus, LeaveType, TherapistLeave
from app.models.ops_state_transition import OpsStateTransition
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import EmploymentStatus, User
from app.services.integration import ops_aggregate as ops_aggregate_service
from app.services.integration.rate_limit import reset_memory_rate_limits_for_tests
from app.tests.conftest import login_headers

UTC = timezone.utc
D0 = date(2031, 3, 10)
D1 = date(2031, 3, 11)
D2 = date(2031, 3, 12)
LEAK = "ZZLEAKOPSAGG"


@pytest.fixture(autouse=True)
def _enable_integration(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_enabled", True)
    monkeypatch.setattr(settings, "mcp_enabled", True)
    reset_memory_rate_limits_for_tests()
    yield
    reset_memory_rate_limits_for_tests()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _token(client, client_id: str, client_secret: str):
    res = client.post(
        "/api/v1/integrations/oauth/token",
        json={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _integration_headers(client, *, scopes, case_ids, info_access=None, allow_read=None):
    admin = login_headers(client, "superadmin@demo.com")
    body = {"name": f"Ops aggregate {uuid.uuid4().hex[:8]}", "case_ids": case_ids}
    if info_access is not None:
        body["info_access"] = info_access
        body["allow_read"] = True if allow_read is None else allow_read
    else:
        body["scopes"] = scopes
    created = client.post("/api/v1/admin/integration-clients", headers=admin, json=body)
    assert created.status_code == 201, created.text
    payload = created.json()
    token = _token(client, payload["client_id"], payload["client_secret"])
    return {"Authorization": f"Bearer {token}"}, payload


def _aggregate(client, headers, date_from=D0, date_to=D2):
    return client.get(
        "/api/v1/integrations/v1/ops/aggregate",
        headers=headers,
        params={"from": date_from.isoformat(), "to": date_to.isoformat()},
    )


def _walk_keys(value, found: set[str]) -> None:
    if isinstance(value, dict):
        found.update(value.keys())
        for item in value.values():
            _walk_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_keys(item, found)


def _day(body, day: date):
    matches = [row for row in body["days"] if row["date"] == day.isoformat()]
    assert len(matches) == 1
    return matches[0]


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def test_scope_required_and_empty_grants_do_not_zero_org_counts(client):
    denied, _ = _integration_headers(client, scopes=["ops:summary"], case_ids=[])
    blocked = _aggregate(client, denied)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "forbidden"
    assert LEAK not in blocked.text

    headers, created = _integration_headers(
        client, scopes=["ops:summary", "ops:aggregate:read"], case_ids=[]
    )
    assert created["granted_case_count"] == 0
    assert "ops:aggregate:read" in created["scopes"]
    summary = client.get("/api/v1/integrations/v1/ops/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["granted_case_count"] == 0
    assert summary.json()["active_case_count"] == 0

    org = _aggregate(client, headers)
    assert org.status_code == 200, org.text
    body = org.json()
    assert "granted_case_count" not in body
    assert set(body["snapshot"]["cases_by_status"]) >= {item.value for item in CaseStatus}
    assert set(body["snapshot"]["billing_ledger_by_billable_status"]) >= {item.value for item in BillableStatus}
    assert set(body["days"][0]["sessions_by_status"]) >= {item.value for item in SessionStatus}
    assert set(body["days"][0]["monthly_reports_by_status"]) >= {item.value for item in ReportStatus}
    assert sum(body["snapshot"]["cases_by_status"].values()) > 0
    cases = client.get("/api/v1/integrations/v1/cases", headers=headers)
    assert cases.status_code == 403


def test_admin_grants_scope_without_case_ids(client):
    headers, created = _integration_headers(
        client, scopes=None, case_ids=[], info_access=["ops_aggregate"]
    )
    assert created["scopes"] == ["ops:aggregate:read"]
    assert created["all_cases"] is False
    assert created["granted_case_count"] == 0
    assert "ops_aggregate" in created["info_access"]
    res = _aggregate(client, headers)
    assert res.status_code == 200, res.text


def test_existing_key_does_not_gain_scope_until_admin_updates_it(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case_id = db.scalars(select(Case.id).limit(1)).first()
    finally:
        db.close()
    created = client.post(
        "/api/v1/admin/integration-clients",
        headers=admin,
        json={"name": "Existing ops key", "scopes": ["ops:summary"], "case_ids": [case_id]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert "ops:aggregate:read" not in body["scopes"]
    token = _token(client, body["client_id"], body["client_secret"])
    headers = {"Authorization": f"Bearer {token}"}
    assert _aggregate(client, headers).status_code == 403

    updated = client.patch(
        f"/api/v1/admin/integration-clients/{body['id']}",
        headers=admin,
        json={"scopes": ["ops:summary", "ops:aggregate:read"]},
    )
    assert updated.status_code == 200, updated.text
    assert "ops:aggregate:read" in updated.json()["scopes"]
    # Access tokens keep the scopes they were issued with. The next token picks up the grant.
    refreshed = {"Authorization": f"Bearer {_token(client, body['client_id'], body['client_secret'])}"}
    assert _aggregate(client, refreshed).status_code == 200


def test_postgres_ist_day_sql_uses_kolkata_timezone():
    day_expr = ops_aggregate_service._ist_day_expr_for_dialect("postgresql", DailyLog.created_at)
    stmt = select(day_expr, DailyLog.approval_status, func.count()).group_by(day_expr, DailyLog.approval_status)
    compiled = stmt.compile(dialect=postgresql.dialect())
    assert "timezone" in str(compiled)
    assert "Asia/Kolkata" in compiled.params.values()


def test_date_window_guidance_and_get_only(client):
    headers, _ = _integration_headers(client, scopes=["ops:aggregate:read"], case_ids=[])
    backwards = _aggregate(client, headers, date_from=D1, date_to=D0)
    assert backwards.status_code == 422
    assert backwards.json()["detail"]["code"] == "validation_error"
    assert "Invalid" not in backwards.json()["detail"]["message"]

    too_long = _aggregate(client, headers, date_from=date(2031, 1, 1), date_to=date(2031, 4, 4))
    assert too_long.status_code == 422
    allowed = _aggregate(client, headers, date_from=date(2031, 1, 1), date_to=date(2031, 4, 3))
    assert allowed.status_code == 200, allowed.text
    assert len(allowed.json()["days"]) == 93

    posted = client.post(
        "/api/v1/integrations/v1/ops/aggregate",
        headers=headers,
        params={"from": D0.isoformat(), "to": D0.isoformat()},
    )
    assert posted.status_code == 405


def test_fixture_counts_ist_days_and_no_pii(client, monkeypatch):
    headers, _ = _integration_headers(client, scopes=["ops:aggregate:read"], case_ids=[])
    before = _aggregate(client, headers)
    assert before.status_code == 200, before.text
    before_body = before.json()

    db = SessionLocal()
    case_ids: list[int] = []
    user_ids: list[int] = []
    session_ids: list[int] = []
    log_ids: list[int] = []
    child_id = None
    try:
        parent = db.scalars(select(User).where(User.email == "parent@demo.com")).one()
        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).one()
        suffix = uuid.uuid4().hex[:4].upper()
        # SQLite reuses deleted rowids and does not cascade, so a new case can inherit
        # another test's assignment. Reserved ids stay outside that recycled range.
        id_base = 50_000_000 + int(suffix, 16) * 200
        seq = {"n": 0}

        def take_id() -> int:
            seq["n"] += 1
            return id_base + seq["n"]

        def code(n: int) -> str:
            return f"IC-2031-{suffix}-{n:02d}"

        child = Child(
            id=take_id(),
            first_name=f"{LEAK}CHILD",
            last_name=f"{LEAK}LAST",
            date_of_birth=date(2016, 4, 2),
        )
        db.add(child)
        db.flush()
        child_id = child.id

        def user(email_key: str, *, active: bool, employment: EmploymentStatus) -> User:
            row = User(
                id=take_id(),
                email=f"{email_key}-{suffix.lower()}@example.com",
                password_hash="not-a-login",
                full_name=f"{LEAK}THERAPIST",
                phone="9990001111",
                is_active=active,
                employment_status=employment,
            )
            db.add(row)
            db.flush()
            user_ids.append(row.id)
            return row

        inactive = user("inactive", active=False, employment=EmploymentStatus.ACTIVE)
        suspended_emp = user("suspended", active=True, employment=EmploymentStatus.SUSPENDED)
        healthy = user("healthy", active=True, employment=EmploymentStatus.ACTIVE)

        def add_case(n: int, status: CaseStatus, **extra) -> Case:
            row = Case(
                id=take_id(),
                case_code=code(n),
                child_id=child.id,
                service_type="homecare",
                product_module="homecare",
                status=status,
                notes=f"{LEAK}NOTE",
                status_reason=f"{LEAK}REASON",
                **extra,
            )
            db.add(row)
            db.flush()
            case_ids.append(row.id)
            return row

        c_unassigned = add_case(1, CaseStatus.ACTIVE)
        c_inactive = add_case(2, CaseStatus.ACTIVE)
        c_emp = add_case(3, CaseStatus.ACTIVE)
        c_healthy = add_case(4, CaseStatus.ACTIVE)
        c_ended = add_case(5, CaseStatus.ACTIVE)
        c_susp = add_case(6, CaseStatus.SUSPENDED, status_effective_date=date(2031, 3, 1))
        c_susp_null = add_case(7, CaseStatus.SUSPENDED, status_effective_date=None)
        c_susp_future = add_case(8, CaseStatus.SUSPENDED, status_effective_date=date(2031, 3, 15))
        c_closed = add_case(9, CaseStatus.CLOSED, status_effective_date=date(2031, 3, 1))
        c_closed_null = add_case(10, CaseStatus.CLOSED, status_effective_date=None)
        c_deact_null = add_case(11, CaseStatus.DEACTIVATED, status_effective_date=None)
        c_deact = add_case(12, CaseStatus.DEACTIVATED, status_effective_date=date(2031, 2, 1))
        add_case(13, CaseStatus.PENDING_ALLOTMENT)
        add_case(14, CaseStatus.PENDING_REPLACEMENT)
        c_pkg_null = add_case(15, CaseStatus.ACTIVE, billing_type=BillingType.PACKAGE, package_session_count=None)
        c_pkg_zero = add_case(16, CaseStatus.ACTIVE, billing_type=BillingType.PACKAGE, package_session_count=0)
        c_pkg_ok = add_case(17, CaseStatus.ACTIVE, billing_type=BillingType.PACKAGE, package_session_count=8)
        c_per = add_case(18, CaseStatus.ACTIVE, billing_type=BillingType.PER_SESSION, package_session_count=None)
        c_closed_same = add_case(19, CaseStatus.CLOSED, status_effective_date=D0)

        def assign(case: Case, therapist: User, status: CaseAssignmentStatus) -> None:
            db.add(
                CaseAssignment(
                    case_id=case.id,
                    therapist_user_id=therapist.id,
                    start_date=date(2031, 1, 1),
                    status=status,
                )
            )

        assign(c_inactive, inactive, CaseAssignmentStatus.ACTIVE)
        assign(c_emp, suspended_emp, CaseAssignmentStatus.ACTIVE)
        assign(c_healthy, healthy, CaseAssignmentStatus.ACTIVE)
        assign(c_ended, healthy, CaseAssignmentStatus.ENDED)
        db.flush()

        def add_session(case: Case, day: date, status: SessionStatus, *, therapist: User = healthy) -> TherapySession:
            row = TherapySession(
                id=take_id(),
                case_id=case.id,
                therapist_user_id=therapist.id,
                scheduled_date=day,
                status=status,
            )
            db.add(row)
            db.flush()
            session_ids.append(row.id)
            return row

        s_logged = add_session(c_healthy, D0, SessionStatus.COMPLETED)
        s_missing = add_session(c_healthy, D0, SessionStatus.COMPLETED)
        s_boundary = add_session(c_unassigned, D0, SessionStatus.COMPLETED)
        s_susp_sched = add_session(c_susp, D0, SessionStatus.SCHEDULED)
        s_susp_done = add_session(c_susp, D0, SessionStatus.COMPLETED)
        s_cancelled = add_session(c_susp, D0, SessionStatus.CANCELLED)
        s_unknown = add_session(c_susp_null, D0, SessionStatus.COMPLETED)
        s_before_suspend = add_session(c_susp_future, D0, SessionStatus.COMPLETED)
        s_after_close = add_session(c_closed, D1, SessionStatus.COMPLETED)
        s_on_close_day = add_session(c_closed_same, D0, SessionStatus.COMPLETED)
        s_after_deact = add_session(c_deact, D1, SessionStatus.SCHEDULED)
        add_session(c_deact_null, D1, SessionStatus.SCHEDULED)
        s_day1 = add_session(c_healthy, D1, SessionStatus.SCHEDULED)
        add_session(c_closed, date(2031, 3, 2), SessionStatus.COMPLETED)
        s_outside_before = add_session(c_closed, date(2031, 2, 1), SessionStatus.COMPLETED)

        def add_log(session: TherapySession, approval: str, created_at: datetime) -> None:
            row = DailyLog(
                session_id=session.id,
                attendance_status="PRESENT",
                session_notes=f"{LEAK}CLINICAL",
                approval_status=approval,
                created_at=created_at,
            )
            db.add(row)
            db.flush()
            log_ids.append(row.id)

        add_log(s_logged, LogApprovalStatus.PENDING.value, _at(D0, 18, 0))
        add_log(s_boundary, LogApprovalStatus.APPROVED.value, _at(D0, 20, 0))
        add_log(s_outside_before, LogApprovalStatus.REJECTED.value, _at(date(2031, 2, 1), 4, 0))

        db.add_all(
            [
                MonthlyReport(
                    case_id=c_healthy.id,
                    therapist_user_id=healthy.id,
                    month="Mar 2031",
                    status=ReportStatus.APPROVED,
                    summary=f"{LEAK}SUMMARY",
                    created_at=_at(D0, 20, 30),
                ),
                MonthlyReport(
                    case_id=c_unassigned.id,
                    therapist_user_id=healthy.id,
                    month="Sep 2026",
                    status=ReportStatus.DRAFT,
                    summary=f"{LEAK}SUMMARY",
                    created_at=_at(D0, 10, 0),
                ),
                MonthlyReport(
                    case_id=c_closed.id,
                    therapist_user_id=healthy.id,
                    month="Jan 2031",
                    status=ReportStatus.APPROVED,
                    submitted_for_review_at=_at(date(2031, 1, 20), 6, 0),
                    created_at=_at(date(2031, 1, 15), 6, 0),
                ),
                ClinicalReport(
                    case_id=c_inactive.id,
                    report_type="monthly",
                    title=f"{LEAK}TITLE",
                    status=ClinicalReportStatus.APPROVED.value,
                    created_by_id=admin.id,
                    submitted_at=None,
                ),
                ClinicalReport(
                    case_id=c_healthy.id,
                    report_type="monthly",
                    title="Submitted clinical",
                    status=ClinicalReportStatus.APPROVED.value,
                    created_by_id=admin.id,
                    submitted_at=_at(D0, 12, 0),
                ),
                ObservationReport(
                    case_id=c_unassigned.id,
                    therapist_user_id=healthy.id,
                    title=f"{LEAK}OBS",
                    content=f"{LEAK}OBSNOTE",
                    status=ReportStatus.APPROVED,
                ),
            ]
        )
        db.flush()

        pkg_mismatch = CarePackage(
            case_id=c_pkg_ok.id,
            parent_user_id=parent.id,
            name="Mismatch package",
            total_sessions=8,
            used_sessions=2,
            status=CarePackageStatus.ACTIVE,
        )
        pkg_match = CarePackage(
            case_id=c_healthy.id,
            parent_user_id=parent.id,
            name="Matched package",
            total_sessions=8,
            used_sessions=1,
            status=CarePackageStatus.ACTIVE,
        )
        pkg_cancelled = CarePackage(
            case_id=c_per.id,
            parent_user_id=parent.id,
            name="Cancelled consumption",
            total_sessions=4,
            used_sessions=1,
            status=CarePackageStatus.EXHAUSTED,
        )
        pkg_ignored = CarePackage(
            case_id=c_pkg_null.id,
            parent_user_id=parent.id,
            name="Unpaid package",
            total_sessions=4,
            used_sessions=9,
            status=CarePackageStatus.PENDING_PAYMENT,
        )
        db.add_all([pkg_mismatch, pkg_match, pkg_cancelled, pkg_ignored])
        db.flush()

        def ledger(case, event, status, *, package=None, session=None):
            db.add(
                BillingLedger(
                    case_id=case.id,
                    source_type=LedgerSourceType.PACKAGE_CONSUMPTION
                    if event == LedgerEventType.PACKAGE_CONSUMPTION
                    else LedgerSourceType.SESSION,
                    ledger_month="Mar 2031",
                    event_date=D0,
                    event_type=event,
                    billable_status=status,
                    care_package_id=package.id if package else None,
                    session_id=session.id if session else None,
                    admin_note=f"{LEAK}LEDGER",
                )
            )

        ledger(c_healthy, LedgerEventType.PACKAGE_CONSUMPTION, BillableStatus.BILLABLE, package=pkg_match, session=s_logged)
        ledger(
            c_per,
            LedgerEventType.PACKAGE_CONSUMPTION,
            BillableStatus.NON_BILLABLE,
            package=pkg_cancelled,
            session=s_cancelled,
        )
        ledger(c_healthy, LedgerEventType.SESSION_COMPLETED, BillableStatus.PENDING_REVIEW, session=s_missing)
        ledger(c_pkg_ok, LedgerEventType.MANUAL_ADJUSTMENT, BillableStatus.BILLABLE)

        db.add_all(
            [
                BillingApprovalRequest(
                    case_id=c_pkg_ok.id,
                    status=BillingApprovalStatus.PENDING,
                    previous_billing={"note": f"{LEAK}BILLING"},
                    proposed_billing={"note": "rate"},
                    projected_profit_inr=10,
                    requested_by_user_id=admin.id,
                ),
                BillingApprovalRequest(
                    case_id=c_per.id,
                    status=BillingApprovalStatus.APPROVED,
                    previous_billing={"note": "old"},
                    proposed_billing={"note": "new"},
                    projected_profit_inr=1,
                    requested_by_user_id=admin.id,
                ),
                SessionAbsenceRequest(
                    session_id=s_susp_sched.id,
                    case_id=c_susp.id,
                    therapist_user_id=healthy.id,
                    absence_type=SessionAbsenceType.CLIENT_ABSENT,
                    status=SessionAbsenceStatus.PENDING_APPROVAL,
                    requested_by_user_id=admin.id,
                    reason=f"{LEAK}ABSENCE",
                ),
                SessionAbsenceRequest(
                    session_id=s_day1.id,
                    case_id=c_healthy.id,
                    therapist_user_id=healthy.id,
                    absence_type=SessionAbsenceType.THERAPIST_LEAVE,
                    status=SessionAbsenceStatus.APPROVED,
                    requested_by_user_id=admin.id,
                ),
                TherapistLeave(
                    therapist_user_id=inactive.id,
                    leave_type=LeaveType.ANNUAL,
                    start_date=D0,
                    end_date=D1,
                    status=LeaveStatus.PENDING,
                    case_id=c_inactive.id,
                    reason=f"{LEAK}LEAVE",
                ),
                TherapistLeave(
                    therapist_user_id=healthy.id,
                    leave_type=LeaveType.SICK,
                    start_date=D0,
                    end_date=D0,
                    status=LeaveStatus.APPROVED,
                    case_id=c_healthy.id,
                ),
            ]
        )
        db.commit()

        case_count = int(db.scalar(select(func.count()).select_from(Case)) or 0)
        session_count = int(db.scalar(select(func.count()).select_from(TherapySession)) or 0)
        after = _aggregate(client, headers)
        assert after.status_code == 200, after.text
        assert int(db.scalar(select(func.count()).select_from(Case)) or 0) == case_count
        assert int(db.scalar(select(func.count()).select_from(TherapySession)) or 0) == session_count
        body = after.json()
        assert LEAK not in after.text
        keys: set[str] = set()
        _walk_keys(body, keys)
        leaked = keys & {
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "session_notes",
            "summary",
            "body_html",
            "content",
            "title",
            "case_id",
            "therapist_user_id",
            "child_id",
            "previous_billing",
            "admin_note",
            "notes",
            "status_reason",
        }
        assert leaked == set()

        snap_before = before_body["snapshot"]
        snap = body["snapshot"]
        assert snap["cases_by_status"]["ACTIVE"] - snap_before["cases_by_status"]["ACTIVE"] == 9
        assert snap["cases_by_status"]["SUSPENDED"] - snap_before["cases_by_status"]["SUSPENDED"] == 3
        assert snap["cases_by_status"]["CLOSED"] - snap_before["cases_by_status"]["CLOSED"] == 3
        assert snap["cases_by_status"]["DEACTIVATED"] - snap_before["cases_by_status"]["DEACTIVATED"] == 2
        assert snap["cases_by_status"]["PENDING_ALLOTMENT"] - snap_before["cases_by_status"]["PENDING_ALLOTMENT"] == 1
        assert snap["cases_by_status"]["PENDING_REPLACEMENT"] - snap_before["cases_by_status"]["PENDING_REPLACEMENT"] == 1
        active_assignment_exists = (
            select(CaseAssignment.id)
            .where(
                CaseAssignment.case_id == Case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
            .exists()
        )
        our_unassigned = db.scalars(
            select(Case.case_code).where(
                Case.id.in_(case_ids),
                Case.status == CaseStatus.ACTIVE,
                ~active_assignment_exists,
            )
        ).all()
        our_active_assignments = int(
            db.scalar(
                select(func.count())
                .select_from(CaseAssignment)
                .where(
                    CaseAssignment.case_id.in_(case_ids),
                    CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                )
            )
            or 0
        )
        unassigned_delta = snap["active_cases_unassigned"] - snap_before["active_cases_unassigned"]
        assignment_delta = snap["active_case_assignments"] - snap_before["active_case_assignments"]
        assert unassigned_delta == len(our_unassigned), (
            f"unassigned api {unassigned_delta} fixture {list(our_unassigned)}"
        )
        assert set(our_unassigned) == {
            c_unassigned.case_code,
            c_ended.case_code,
            c_pkg_null.case_code,
            c_pkg_zero.case_code,
            c_pkg_ok.case_code,
            c_per.case_code,
        }
        assert assignment_delta == our_active_assignments == 3
        assert (
            snap["daily_logs_by_approval_status"]["PENDING"]
            - snap_before["daily_logs_by_approval_status"]["PENDING"]
            == 1
        )
        assert (
            snap["daily_logs_by_approval_status"]["APPROVED"]
            - snap_before["daily_logs_by_approval_status"]["APPROVED"]
            == 1
        )
        assert (
            snap["billing_ledger_by_billable_status"]["PENDING_REVIEW"]
            - snap_before["billing_ledger_by_billable_status"]["PENDING_REVIEW"]
            == 1
        )
        assert snap["billing_approval_requests_pending"] - snap_before["billing_approval_requests_pending"] == 1
        assert (
            snap["session_absence_requests_pending_approval"]
            - snap_before["session_absence_requests_pending_approval"]
            == 1
        )
        assert snap["therapist_leaves_pending"] - snap_before["therapist_leaves_pending"] == 1

        def day_delta(day: date, bucket: str, status: str) -> int:
            return _day(body, day)[bucket][status] - _day(before_body, day)[bucket].get(status, 0)

        assert day_delta(D0, "sessions_by_status", "COMPLETED") == 7
        assert day_delta(D0, "sessions_by_status", "SCHEDULED") == 1
        assert day_delta(D0, "sessions_by_status", "CANCELLED") == 1
        assert day_delta(D1, "sessions_by_status", "COMPLETED") == 1
        assert day_delta(D1, "sessions_by_status", "SCHEDULED") == 3
        assert day_delta(D2, "sessions_by_status", "COMPLETED") == 0
        assert day_delta(D0, "daily_logs_created_by_approval_status", "PENDING") == 1
        assert day_delta(D0, "daily_logs_created_by_approval_status", "APPROVED") == 0
        assert day_delta(D1, "daily_logs_created_by_approval_status", "APPROVED") == 1
        assert day_delta(D1, "daily_logs_created_by_approval_status", "PENDING") == 0
        assert day_delta(D0, "monthly_reports_by_status", "DRAFT") == 1
        assert day_delta(D0, "monthly_reports_by_status", "APPROVED") == 0
        assert day_delta(D1, "monthly_reports_by_status", "APPROVED") == 1
        assert day_delta(D2, "monthly_reports_by_status", "DRAFT") == 0

        integrity = body["integrity"]
        before_integrity = before_body["integrity"]

        def count_delta(key: str) -> int:
            return integrity[key]["count"] - before_integrity[key]["count"]

        assert count_delta("active_case_inactive_therapist") == 2
        assert {c_inactive.case_code, c_emp.case_code} <= set(integrity["active_case_inactive_therapist"]["case_codes"])
        assert c_healthy.case_code not in integrity["active_case_inactive_therapist"]["case_codes"]

        assert count_delta("sessions_on_suspended_case") == 2
        assert c_susp.case_code in integrity["sessions_on_suspended_case"]["case_codes"]
        assert c_susp_future.case_code not in integrity["sessions_on_suspended_case"]["case_codes"]
        assert c_susp_null.case_code not in integrity["sessions_on_suspended_case"]["case_codes"]

        unknown = integrity["suspended_sessions_missing_status_effective_date"]
        assert unknown["count"] is None
        assert unknown["status"] == "unknown"
        assert (
            unknown["unclassified_session_count"]
            - before_integrity["suspended_sessions_missing_status_effective_date"]["unclassified_session_count"]
            == 1
        )
        assert c_susp_null.case_code in unknown["case_codes"]

        assert count_delta("sessions_after_closure") == 3
        assert {c_closed.case_code, c_deact.case_code} <= set(integrity["sessions_after_closure"]["case_codes"])
        assert c_closed_same.case_code not in integrity["sessions_after_closure"]["case_codes"]
        assert c_closed_null.case_code not in integrity["sessions_after_closure"]["case_codes"]

        assert count_delta("closed_or_deactivated_missing_effective_date") == 2
        assert {c_closed_null.case_code, c_deact_null.case_code} <= set(
            integrity["closed_or_deactivated_missing_effective_date"]["case_codes"]
        )
        assert c_closed.case_code not in integrity["closed_or_deactivated_missing_effective_date"]["case_codes"]

        assert count_delta("monthly_reports_approved_missing_submission") == 1
        assert c_healthy.case_code in integrity["monthly_reports_approved_missing_submission"]["case_codes"]
        assert c_closed.case_code not in integrity["monthly_reports_approved_missing_submission"]["case_codes"]

        assert count_delta("clinical_reports_approved_missing_submission") == 1
        assert c_inactive.case_code in integrity["clinical_reports_approved_missing_submission"]["case_codes"]
        assert c_healthy.case_code not in integrity["clinical_reports_approved_missing_submission"]["case_codes"]

        observation = integrity["observation_reports_approved_missing_submission"]
        assert observation["count"] is None
        assert observation["status"] == "unknown"
        assert "case_codes" not in observation

        assert count_delta("completed_sessions_missing_daily_log") == 6
        assert c_healthy.case_code in integrity["completed_sessions_missing_daily_log"]["case_codes"]
        assert c_unassigned.case_code not in integrity["completed_sessions_missing_daily_log"]["case_codes"]

        assert count_delta("care_packages_used_vs_ledger_consumption") == 1
        assert c_pkg_ok.case_code in integrity["care_packages_used_vs_ledger_consumption"]["case_codes"]
        assert c_healthy.case_code not in integrity["care_packages_used_vs_ledger_consumption"]["case_codes"]
        assert c_per.case_code not in integrity["care_packages_used_vs_ledger_consumption"]["case_codes"]
        assert c_pkg_null.case_code not in integrity["care_packages_used_vs_ledger_consumption"]["case_codes"]

        assert count_delta("care_packages_used_vs_completed_sessions") == 2
        assert {c_pkg_ok.case_code, c_per.case_code} <= set(
            integrity["care_packages_used_vs_completed_sessions"]["case_codes"]
        )
        assert c_healthy.case_code not in integrity["care_packages_used_vs_completed_sessions"]["case_codes"]

        assert count_delta("package_cases_missing_session_count") == 2
        assert {c_pkg_null.case_code, c_pkg_zero.case_code} <= set(
            integrity["package_cases_missing_session_count"]["case_codes"]
        )
        assert c_pkg_ok.case_code not in integrity["package_cases_missing_session_count"]["case_codes"]
        assert c_per.case_code not in integrity["package_cases_missing_session_count"]["case_codes"]

        assert {item["metric"] for item in body["not_computed"]} == {
            "observation_reports_approved_missing_submission",
            "suspended_sessions_missing_status_effective_date",
        }
        assert all(item["status"] == "unknown" for item in body["not_computed"])

        monkeypatch.setattr(ops_aggregate_service, "CASE_CODE_LIST_LIMIT", 1)
        capped = _aggregate(client, headers)
        assert capped.status_code == 200, capped.text
        inactive_list = capped.json()["integrity"]["active_case_inactive_therapist"]
        assert inactive_list["count"] >= 2
        assert len(inactive_list["case_codes"]) == 1
        assert inactive_list["case_codes_truncated"] is True
    finally:
        db.rollback()
        if case_ids:
            db.execute(
                delete(OpsStateTransition).where(
                    OpsStateTransition.entity_type == "daily_log",
                    OpsStateTransition.entity_id.in_(log_ids or [-1]),
                )
            )
            db.execute(
                delete(OpsStateTransition).where(
                    OpsStateTransition.entity_type == "session",
                    OpsStateTransition.entity_id.in_(session_ids or [-1]),
                )
            )
            db.execute(delete(BillingLedger).where(BillingLedger.case_id.in_(case_ids)))
            db.execute(delete(SessionAbsenceRequest).where(SessionAbsenceRequest.case_id.in_(case_ids)))
            if session_ids:
                db.execute(delete(DailyLog).where(DailyLog.session_id.in_(session_ids)))
            db.execute(delete(TherapySession).where(TherapySession.case_id.in_(case_ids)))
            db.execute(delete(CarePackage).where(CarePackage.case_id.in_(case_ids)))
            db.execute(delete(MonthlyReport).where(MonthlyReport.case_id.in_(case_ids)))
            db.execute(delete(ObservationReport).where(ObservationReport.case_id.in_(case_ids)))
            db.execute(delete(ClinicalReport).where(ClinicalReport.case_id.in_(case_ids)))
            db.execute(delete(BillingApprovalRequest).where(BillingApprovalRequest.case_id.in_(case_ids)))
            db.execute(delete(TherapistLeave).where(TherapistLeave.case_id.in_(case_ids)))
            db.execute(delete(CaseAssignment).where(CaseAssignment.case_id.in_(case_ids)))
            db.execute(delete(Case).where(Case.id.in_(case_ids)))
        if child_id:
            db.execute(delete(Child).where(Child.id == child_id))
        if user_ids:
            db.execute(delete(TherapistLeave).where(TherapistLeave.therapist_user_id.in_(user_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()
        db.close()
