"""End-of-day ops snapshot: IST boundaries, reconstructed state, no read side effects."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.core.database import SessionLocal
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.case import Case, CaseStatus
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.models.child import Child
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.incident import Incident, IncidentStatus
from app.models.leave import LeaveStatus, LeaveType, TherapistLeave
from app.models.notification import Notification
from app.models.ops_state_transition import OpsStateTransition
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.support_ticket import SupportTicket, TicketCategory, TicketStatus, TicketTopic
from app.models.user import User
from app.services.ops_daily_snapshot_service import ist_day_bounds

client = TestClient(app)

DAY = date(2019, 4, 2)
DURING = datetime(2019, 4, 2, 4, 0, tzinfo=timezone.utc)  # 09:30 IST
EARLY = datetime(2019, 1, 1, 4, 0, tzinfo=timezone.utc)
SECRET_NOTE = "CLINICAL-SECRET-NOTE"
SECRET_INCIDENT = "INCIDENT-SECRET-TEXT"
SECRET_BANK = "999888777"


def _login(email: str) -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _count(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _stamp(db, entity_type: str, entity_id: int, when: datetime) -> None:
    """Move recorded transitions into the reporting day before later mutations."""
    db.execute(
        update(OpsStateTransition)
        .where(
            OpsStateTransition.entity_type == entity_type,
            OpsStateTransition.entity_id == entity_id,
        )
        .values(occurred_at=when)
    )
    db.flush()


def _case(db, code: str, child_id: int, *, status: CaseStatus, created_at: datetime) -> Case:
    row = Case(
        case_code=code,
        child_id=child_id,
        service_type="homecare",
        product_module="homecare",
        status=status,
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    return row


def _session(
    db,
    *,
    case_id: int,
    therapist_id: int,
    status: SessionStatus,
    created_at: datetime,
    scheduled_date: date = DAY,
) -> TherapySession:
    row = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_id,
        scheduled_date=scheduled_date,
        start_time=time(9, 0),
        end_time=time(10, 0),
        status=status,
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    _stamp(db, "session", row.id, created_at if created_at < ist_day_bounds(DAY)[1] else DURING)
    return row


def _log(
    db,
    session_id: int,
    *,
    submitted_at: datetime | None,
    approval: str,
) -> DailyLog:
    row = DailyLog(
        session_id=session_id,
        attendance_status="PRESENT",
        session_notes=SECRET_NOTE,
        submitted_at=submitted_at,
        approval_status=approval,
    )
    db.add(row)
    db.flush()
    return row


def _ticket(
    db,
    *,
    raised_by: int,
    created_at: datetime,
    assigned_to: int | None = None,
    status: TicketStatus = TicketStatus.OPEN,
) -> SupportTicket:
    row = SupportTicket(
        raised_by_user_id=raised_by,
        assigned_to_user_id=assigned_to,
        category=TicketCategory.TECH,
        topic=TicketTopic.OTHER,
        subject="ops snapshot",
        body="ops snapshot body",
        status=status,
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    return row


def test_ist_day_bounds_are_half_open_kolkata_midnights():
    start, end = ist_day_bounds(DAY)
    assert start == datetime(2019, 4, 1, 18, 30, tzinfo=timezone.utc)
    assert end == datetime(2019, 4, 2, 18, 30, tzinfo=timezone.utc)
    assert start < DURING < end
    assert not (end < end)


def test_daily_snapshot_matches_end_of_day_not_later_mutations():
    start, end = ist_day_bounds(DAY)
    admin = _login("superadmin@demo.com")
    db = SessionLocal()
    try:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        superadmin = db.scalar(select(User).where(User.email == "superadmin@demo.com"))
        child = db.scalars(select(Child).limit(1)).first()
        assert therapist and superadmin and child
        therapist_name = therapist.full_name
        child_name = f"{child.first_name} {child.last_name}".strip()

        logs_case = _case(db, "OPS-2019-LOGS", child.id, status=CaseStatus.ACTIVE, created_at=EARLY)
        miss_a = _case(db, "OPS-2019-MISS-A", child.id, status=CaseStatus.ACTIVE, created_at=EARLY)
        miss_b = _case(db, "OPS-2019-MISS-B", child.id, status=CaseStatus.ACTIVE, created_at=EARLY)
        _case(db, "OPS-2019-NOSESS", child.id, status=CaseStatus.ACTIVE, created_at=EARLY)
        was_active = _case(db, "OPS-2019-WAS", child.id, status=CaseStatus.SUSPENDED, created_at=EARLY)
        _case(db, "OPS-2019-NEW", child.id, status=CaseStatus.ACTIVE, created_at=DURING)
        _case(db, "OPS-2019-OFF", child.id, status=CaseStatus.SUSPENDED, created_at=EARLY)
        db.add(
            CaseClientStatusAudit(
                case_id=was_active.id,
                previous_status=CaseStatus.ACTIVE.value,
                new_status=CaseStatus.SUSPENDED.value,
                effective_date=date(2019, 4, 3),
                reason="paused after the reporting day",
                changed_by_user_id=superadmin.id,
                changed_at=end + timedelta(hours=2),
            )
        )

        approved_session = _session(
            db, case_id=logs_case.id, therapist_id=therapist.id, status=SessionStatus.COMPLETED, created_at=DURING
        )
        pending_session = _session(
            db, case_id=logs_case.id, therapist_id=therapist.id, status=SessionStatus.COMPLETED, created_at=DURING
        )
        rejected_session = _session(
            db, case_id=logs_case.id, therapist_id=therapist.id, status=SessionStatus.COMPLETED, created_at=DURING
        )
        scheduled = _session(
            db, case_id=logs_case.id, therapist_id=therapist.id, status=SessionStatus.SCHEDULED, created_at=DURING
        )
        absent = _session(
            db, case_id=logs_case.id, therapist_id=therapist.id, status=SessionStatus.CLIENT_ABSENT, created_at=DURING
        )
        missing_a = _session(
            db, case_id=miss_a.id, therapist_id=therapist.id, status=SessionStatus.COMPLETED, created_at=DURING
        )
        missing_b = _session(
            db, case_id=miss_b.id, therapist_id=therapist.id, status=SessionStatus.COMPLETED, created_at=DURING
        )
        _session(
            db,
            case_id=logs_case.id,
            therapist_id=therapist.id,
            status=SessionStatus.COMPLETED,
            created_at=end,
        )

        approved_log = _log(
            db, approved_session.id, submitted_at=DURING, approval=LogApprovalStatus.PENDING.value
        )
        approved_log.approval_status = LogApprovalStatus.APPROVED.value
        db.flush()
        _stamp(db, "daily_log", approved_log.id, DURING)

        pending_log = _log(
            db, pending_session.id, submitted_at=DURING, approval=LogApprovalStatus.PENDING.value
        )
        _stamp(db, "daily_log", pending_log.id, DURING)
        pending_log.approval_status = LogApprovalStatus.APPROVED.value
        db.flush()

        rejected_log = _log(
            db, rejected_session.id, submitted_at=DURING, approval=LogApprovalStatus.PENDING.value
        )
        rejected_log.approval_status = LogApprovalStatus.REJECTED.value
        db.flush()
        _stamp(db, "daily_log", rejected_log.id, DURING)

        _log(db, missing_b.id, submitted_at=end + timedelta(hours=3), approval=LogApprovalStatus.PENDING.value)
        assert missing_a.id

        scheduled.status = SessionStatus.CANCELLED
        db.flush()

        open_then_closed = _ticket(
            db, raised_by=therapist.id, created_at=DURING, assigned_to=therapist.id, status=TicketStatus.OPEN
        )
        _stamp(db, "support_ticket", open_then_closed.id, DURING)
        open_then_closed.status = TicketStatus.CLOSED
        open_then_closed.assigned_to_user_id = superadmin.id
        db.flush()

        in_progress = _ticket(db, raised_by=therapist.id, created_at=DURING, status=TicketStatus.OPEN)
        in_progress.status = TicketStatus.IN_PROGRESS
        db.flush()
        _stamp(db, "support_ticket", in_progress.id, DURING)

        just_before = _ticket(
            db, raised_by=therapist.id, created_at=end - timedelta(seconds=1), status=TicketStatus.OPEN
        )
        _stamp(db, "support_ticket", just_before.id, DURING)

        at_end = _ticket(db, raised_by=therapist.id, created_at=end, status=TicketStatus.OPEN)
        at_start = _ticket(db, raised_by=therapist.id, created_at=start, status=TicketStatus.OPEN)
        _stamp(db, "support_ticket", at_start.id, start)

        closed_during = _ticket(db, raised_by=therapist.id, created_at=DURING, status=TicketStatus.OPEN)
        closed_during.status = TicketStatus.CLOSED
        db.flush()
        _stamp(db, "support_ticket", closed_during.id, DURING)

        reported_then_closed = Incident(
            reported_by_user_id=therapist.id,
            title="still reported at eod",
            description=SECRET_INCIDENT,
            status=IncidentStatus.REPORTED,
            priority="CRITICAL",
            created_at=DURING,
        )
        db.add(reported_then_closed)
        db.flush()
        _stamp(db, "incident", reported_then_closed.id, DURING)
        reported_then_closed.status = IncidentStatus.CLOSED
        db.flush()

        escalated = Incident(
            reported_by_user_id=therapist.id,
            title="escalated during day",
            description="daytime escalation",
            status=IncidentStatus.REPORTED,
            created_at=DURING,
        )
        db.add(escalated)
        db.flush()
        escalated.status = IncidentStatus.ESCALATED
        db.flush()
        _stamp(db, "incident", escalated.id, DURING)

        closed_incident = Incident(
            reported_by_user_id=therapist.id,
            title="closed during day",
            description="closed in day",
            status=IncidentStatus.REPORTED,
            created_at=DURING,
        )
        db.add(closed_incident)
        db.flush()
        closed_incident.status = IncidentStatus.CLOSED
        db.flush()
        _stamp(db, "incident", closed_incident.id, DURING)

        db.add(
            Incident(
                reported_by_user_id=therapist.id,
                title="starts at next midnight",
                description="excluded",
                status=IncidentStatus.REPORTED,
                created_at=end,
            )
        )

        leave = TherapistLeave(
            therapist_user_id=therapist.id,
            leave_type=LeaveType.SICK,
            start_date=DAY,
            end_date=DAY,
            status=LeaveStatus.PENDING,
            created_at=DURING,
        )
        db.add(leave)
        db.flush()
        leave.status = LeaveStatus.APPROVED
        leave.reviewed_by_user_id = superadmin.id
        db.flush()

        absence = SessionAbsenceRequest(
            session_id=absent.id,
            case_id=logs_case.id,
            therapist_user_id=therapist.id,
            absence_type=SessionAbsenceType.CLIENT_ABSENT,
            status=SessionAbsenceStatus.PENDING_APPROVAL,
            requested_by_user_id=therapist.id,
            created_at=DURING,
        )
        db.add(absence)
        db.flush()
        absence.status = SessionAbsenceStatus.APPROVED
        absence.reviewed_at = end + timedelta(hours=1)
        absence.reviewed_by_user_id = superadmin.id
        db.flush()

        billing = BillingApprovalRequest(
            case_id=logs_case.id,
            status=BillingApprovalStatus.PENDING,
            previous_billing={"client_rate_per_session_inr": 1000},
            proposed_billing={"client_rate_per_session_inr": 1200, "bank_account_number": SECRET_BANK},
            projected_profit_inr=200,
            requested_by_user_id=superadmin.id,
            requested_at=DURING,
        )
        db.add(billing)
        db.flush()
        billing.status = BillingApprovalStatus.APPROVED
        billing.reviewed_at = end + timedelta(hours=1)
        billing.reviewed_by_user_id = superadmin.id
        db.flush()

        still_pending = BillingApprovalRequest(
            case_id=miss_a.id,
            status=BillingApprovalStatus.PENDING,
            previous_billing={"client_rate_per_session_inr": 1000},
            proposed_billing={"bank_account_number": SECRET_BANK},
            projected_profit_inr=10,
            requested_by_user_id=superadmin.id,
        )
        db.add(still_pending)
        db.commit()
        pending_id = still_pending.id
        assert at_end.created_at is not None
    finally:
        db.close()

    res = client.get("/api/v1/admin/ops/daily-snapshot", headers=admin, params={"date": DAY.isoformat()})
    assert res.status_code == 200, res.text
    body = res.json()
    blob = res.text
    assert SECRET_NOTE not in blob
    assert SECRET_INCIDENT not in blob
    assert SECRET_BANK not in blob
    assert child_name not in blob
    assert "child_name" not in body

    assert body["date"] == DAY.isoformat()
    assert body["timezone"] == "Asia/Kolkata"
    assert body["window_start"].startswith("2019-04-01T18:30:00")
    assert body["window_end_exclusive"].startswith("2019-04-02T18:30:00")

    by_status = body["sessions"]["by_status"]
    assert by_status["COMPLETED"] == 5
    assert by_status["SCHEDULED"] == 1
    assert by_status["CLIENT_ABSENT"] == 1
    assert by_status["CANCELLED"] == 0
    assert set(by_status) == {item.value for item in SessionStatus}

    logs = body["session_logs"]
    assert logs["completed_sessions"] == 5
    assert logs["approved"] == 1
    assert logs["submitted_not_approved"] == 1
    assert logs["rejected"] == 1
    assert logs["nothing_submitted"] == 2
    assert logs["nothing_submitted_at_eod"] == 2
    assert logs["submitted_after_eod"] == 1
    assert logs["still_missing_at_eod"] == [
        {"therapist_name": therapist_name, "case_codes": ["OPS-2019-MISS-A", "OPS-2019-MISS-B"]}
    ]

    tickets = body["tickets"]
    assert tickets["not_closed_by_status"]["OPEN"] == 3
    assert tickets["not_closed_by_status"]["IN_PROGRESS"] == 1
    assert tickets["not_closed_total"] == 4
    assert tickets["unassigned"] == 3
    assert tickets["by_assignee"] == [{"name": therapist_name, "count": 1}]
    assert tickets["created_on_day"] == 5
    assert tickets["closed_after_day_end"] == 1

    incidents = body["incidents"]["not_closed_by_status"]
    assert incidents == {
        "REPORTED": 1,
        "IN_REVIEW": 0,
        "ACTION_TAKEN": 0,
        "ESCALATED": 1,
    }
    assert body["incidents"]["not_closed_total"] == 2

    assert body["child_absence_pending"] == 1
    assert body["leave_pending"] == {"count": 1, "therapist_names": [therapist_name]}
    assert body["billing_change_approvals_pending"] == {
        "count": 1,
        "case_codes": ["OPS-2019-LOGS"],
    }
    assert body["cases_created"] == ["OPS-2019-NEW"]
    assert body["active_cases_without_submitted_log"] == {
        "window_from": "2019-03-29",
        "window_to": "2019-04-02",
        "active_cases": 6,
        "without_submitted_log": 5,
    }

    listed = client.get("/api/v1/billing-approvals", headers=admin)
    assert listed.status_code == 200, listed.text
    assert SECRET_BANK not in listed.text
    ids = {item["id"] for item in listed.json()["items"]}
    assert pending_id in ids
    pending_row = next(item for item in listed.json()["items"] if item["id"] == pending_id)
    assert pending_row["status"] == "PENDING"
    assert "proposed_billing" not in pending_row
    assert "previous_billing" not in pending_row

    again = client.get("/api/v1/admin/ops/daily-snapshot", headers=admin, params={"date": "2019-04-02"})
    assert again.json() == body


def test_snapshot_auth_validation_and_no_writes():
    admin = _login("superadmin@demo.com")
    therapist = _login("therapist@demo.com")
    denied = client.get(
        "/api/v1/admin/ops/daily-snapshot",
        headers=therapist,
        params={"date": DAY.isoformat()},
    )
    assert denied.status_code == 403

    bad = client.get("/api/v1/admin/ops/daily-snapshot", headers=admin, params={"date": "not-a-date"})
    assert bad.status_code == 400
    assert "Invalid Form" not in bad.text
    assert "YYYY-MM-DD" in bad.text

    bad_status = client.get("/api/v1/billing-approvals", headers=admin, params={"status": "NOPE"})
    assert bad_status.status_code == 400
    assert "Invalid Form" not in bad_status.text

    therapist_list = client.get("/api/v1/billing-approvals", headers=therapist)
    assert therapist_list.status_code == 403

    db = SessionLocal()
    try:
        before = (
            _count(db, Notification),
            _count(db, OpsStateTransition),
            _count(db, AuditEvent),
        )
    finally:
        db.close()

    res = client.get("/api/v1/admin/ops/daily-snapshot", headers=admin, params={"date": DAY.isoformat()})
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        after = (
            _count(db, Notification),
            _count(db, OpsStateTransition),
            _count(db, AuditEvent),
        )
    finally:
        db.close()
    assert before == after


def test_list_incidents_does_not_escalate_or_notify(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("process_open_incidents must not run on GET /incidents")

    monkeypatch.setattr("app.services.incident_sla_service.process_open_incidents", _boom)

    db = SessionLocal()
    try:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        assert therapist
        incident = Incident(
            reported_by_user_id=therapist.id,
            title="critical stale read",
            description=SECRET_INCIDENT,
            status=IncidentStatus.REPORTED,
            priority="CRITICAL",
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            last_owner_activity_at=None,
        )
        db.add(incident)
        db.commit()
        incident_id = incident.id
        notes_before = _count(db, Notification)
    finally:
        db.close()

    admin = _login("superadmin@demo.com")
    res = client.get("/api/v1/incidents", headers=admin, params={"page_size": 100})
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        row = db.get(Incident, incident_id)
        assert row is not None
        assert row.status == IncidentStatus.REPORTED
        assert _count(db, Notification) == notes_before
    finally:
        db.close()


def test_list_sessions_does_not_auto_end(monkeypatch):
    import app.services.session_service as session_service

    real_auto_end = session_service.auto_end_if_stale

    def _boom(*_args, **_kwargs):
        raise AssertionError("auto_end_if_stale must not run on GET /sessions")

    monkeypatch.setattr(session_service, "auto_end_if_stale", _boom)

    scheduled = date.today() - timedelta(days=3)
    started = datetime.now(timezone.utc) - timedelta(days=3)
    db = SessionLocal()
    try:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        child = db.scalars(select(Child).limit(1)).first()
        assert therapist and child
        case = _case(
            db,
            f"OPS-STALE-{scheduled.isoformat()}",
            child.id,
            status=CaseStatus.ACTIVE,
            created_at=started,
        )
        row = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=scheduled,
            start_time=time(9, 0),
            end_time=time(10, 0),
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
            created_at=started,
        )
        db.add(row)
        db.commit()
        session_id = row.id
        case_id = case.id
    finally:
        db.close()

    admin = _login("superadmin@demo.com")
    res = client.get("/api/v1/sessions", headers=admin, params={"case_id": case_id, "page_size": 25})
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == SessionStatus.IN_PROGRESS.value

    db = SessionLocal()
    try:
        row = db.get(TherapySession, session_id)
        assert row is not None
        assert row.status == SessionStatus.IN_PROGRESS
        ended = real_auto_end(db, row)
        assert ended.status == SessionStatus.COMPLETED
        db.rollback()
        db.expire_all()
        fresh = db.get(TherapySession, session_id)
        assert fresh is not None
        assert fresh.status == SessionStatus.IN_PROGRESS
    finally:
        db.close()
