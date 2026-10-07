"""Read-only end-of-day ops counts for one Asia/Kolkata calendar day.

Window is half-open: [midnight IST, next midnight IST). Ticket, incident,
session, and log-approval figures are the state a point-in-time read would
have seen at the exclusive end. Status changes recorded in
``ops_state_transitions`` are replayed; rows that never changed after the
day ended fall back to the current columns and, where the product already
audits the action, to that audit trail.

This module only SELECTs. It does not escalate incidents, end sessions, or
send notifications.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import IST
from app.models.audit_event import AuditEvent
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.case import Case, CaseStatus
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.models.daily_log import DailyLog
from app.models.incident import Incident, IncidentMessage, IncidentStatus
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.ops_state_transition import OpsStateTransition
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.support_ticket import SupportTicket, TicketMessage, TicketStatus
from app.models.user import User

_MISSING = object()
_TICKET_TERMINAL = frozenset({TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value})
_TICKET_OPEN = (TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value)
_INCIDENT_OPEN = (
    IncidentStatus.REPORTED.value,
    IncidentStatus.IN_REVIEW.value,
    IncidentStatus.ACTION_TAKEN.value,
    IncidentStatus.ESCALATED.value,
)
_LEAVE_REVIEWED = frozenset(
    {LeaveStatus.APPROVED.value, LeaveStatus.REJECTED.value, LeaveStatus.CANCELLED.value}
)
_ABSENCE_REVIEWED = frozenset(
    {SessionAbsenceStatus.APPROVED.value, SessionAbsenceStatus.REJECTED.value}
)


def ist_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC instants for [day 00:00 IST, next day 00:00 IST)."""
    start = datetime.combine(day, time.min, tzinfo=IST)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _norm(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _before(value: datetime | None, end: datetime) -> bool:
    instant = _as_utc(value)
    return instant is not None and instant < end


def _in_window(value: datetime | None, start: datetime, end: datetime) -> bool:
    instant = _as_utc(value)
    return instant is not None and start <= instant < end


def _chunks(ids: list[int], size: int = 400):
    for offset in range(0, len(ids), size):
        yield ids[offset : offset + size]


def _load_transitions(db: Session, entity_type: str, ids: list[int]) -> dict[int, list[OpsStateTransition]]:
    grouped: dict[int, list[OpsStateTransition]] = defaultdict(list)
    if not ids:
        return grouped
    for chunk in _chunks(ids):
        rows = db.scalars(
            select(OpsStateTransition)
            .where(
                OpsStateTransition.entity_type == entity_type,
                OpsStateTransition.entity_id.in_(chunk),
            )
            .order_by(OpsStateTransition.occurred_at, OpsStateTransition.id)
        ).all()
        for row in rows:
            grouped[row.entity_id].append(row)
    return grouped


def _replay(rows: list[OpsStateTransition], field_name: str, end: datetime) -> object:
    """Value of ``field_name`` just before ``end``. ``_MISSING`` if unrecorded."""
    matched = [row for row in rows if row.field_name == field_name]
    if not matched:
        return _MISSING
    before = [row for row in matched if _before(row.occurred_at, end)]
    if before:
        return before[-1].new_value
    after = [row for row in matched if not _before(row.occurred_at, end)]
    if after:
        return after[0].old_value
    return _MISSING


def _names(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
    return {row.id: row.full_name for row in rows}


def _parse_ticket_status_message(body: str) -> str | None:
    if body.startswith("[Status] Changed to "):
        label = body[len("[Status] Changed to ") :].split(".", 1)[0].strip()
        mapped = {
            "Open": TicketStatus.OPEN.value,
            "In Progress": TicketStatus.IN_PROGRESS.value,
            "Resolved": TicketStatus.RESOLVED.value,
            "Closed": TicketStatus.CLOSED.value,
        }
        return mapped.get(label)
    if body.startswith("[Closed]"):
        return TicketStatus.CLOSED.value
    if body.startswith("[Reopened]"):
        return TicketStatus.IN_PROGRESS.value
    if body.startswith("[Escalated]") or body.startswith("[Picked up]"):
        return TicketStatus.IN_PROGRESS.value
    return None


def _ticket_status_at(
    ticket: SupportTicket,
    rows: list[OpsStateTransition],
    end: datetime,
    audits: list[AuditEvent],
    messages: list[TicketMessage],
) -> str | None:
    replayed = _replay(rows, "status", end)
    if replayed is not _MISSING:
        return _norm(replayed) if replayed is not None else None
    if _before(ticket.updated_at, end):
        return _norm(ticket.status)
    events: list[tuple[datetime, str]] = []
    if _before(ticket.created_at, end):
        events.append((_as_utc(ticket.created_at), TicketStatus.OPEN.value))  # type: ignore[arg-type]
    for audit in audits:
        instant = _as_utc(audit.created_at)
        if instant is None or instant >= end:
            continue
        if audit.action == "resolve":
            events.append((instant, TicketStatus.RESOLVED.value))
        elif audit.action == "close":
            events.append((instant, TicketStatus.CLOSED.value))
        elif audit.action in {"pick_up", "escalate"}:
            events.append((instant, TicketStatus.IN_PROGRESS.value))
    for message in messages:
        instant = _as_utc(message.created_at)
        if instant is None or instant >= end:
            continue
        parsed = _parse_ticket_status_message(message.body or "")
        if parsed:
            events.append((instant, parsed))
    if not events:
        return _norm(ticket.status) if _before(ticket.created_at, end) else None
    events.sort(key=lambda item: item[0])
    return events[-1][1]


def _ticket_assignee_at(ticket: SupportTicket, rows: list[OpsStateTransition], end: datetime) -> int | None:
    replayed = _replay(rows, "assigned_to_user_id", end)
    if replayed is _MISSING:
        if _before(ticket.updated_at, end) or not rows:
            return ticket.assigned_to_user_id
        return ticket.assigned_to_user_id
    if replayed is None or replayed == "":
        return None
    try:
        return int(replayed)
    except (TypeError, ValueError):
        return None


def _incident_status_at(
    incident: Incident,
    rows: list[OpsStateTransition],
    end: datetime,
    audits: list[AuditEvent],
    messages: list[IncidentMessage],
) -> str | None:
    replayed = _replay(rows, "status", end)
    if replayed is not _MISSING:
        return _norm(replayed) if replayed is not None else None
    events: list[tuple[datetime, str]] = []
    created = _as_utc(incident.created_at)
    if created is not None and created < end:
        events.append((created, IncidentStatus.REPORTED.value))
    for audit in audits:
        instant = _as_utc(audit.created_at)
        if instant is None:
            continue
        if audit.action == "close":
            events.append((instant, IncidentStatus.CLOSED.value))
        elif audit.action == "escalate":
            events.append((instant, IncidentStatus.ESCALATED.value))
    for message in messages:
        instant = _as_utc(message.created_at)
        body = message.body or ""
        if instant is None:
            continue
        if body.startswith("[Closed]"):
            events.append((instant, IncidentStatus.CLOSED.value))
        elif body.startswith("[Escalated]"):
            events.append((instant, IncidentStatus.ESCALATED.value))
    escalated = _as_utc(incident.escalated_at)
    if escalated is not None:
        events.append((escalated, IncidentStatus.ESCALATED.value))
    post = [item for item in events if item[0] >= end]
    pre = [item for item in events if item[0] < end]
    if not post:
        return _norm(incident.status) if created is not None and created < end else None
    if not pre:
        return IncidentStatus.REPORTED.value if created is not None and created < end else None
    pre.sort(key=lambda item: item[0])
    return pre[-1][1]


def _session_status_at(session: TherapySession, rows: list[OpsStateTransition], end: datetime) -> str | None:
    if not _before(session.created_at, end):
        return None
    replayed = _replay(rows, "status", end)
    if replayed is not _MISSING and replayed is not None:
        return _norm(replayed)
    status = _norm(session.status) or SessionStatus.SCHEDULED.value
    ended = _as_utc(session.actual_end_at)
    started = _as_utc(session.actual_start_at)
    if status == SessionStatus.COMPLETED.value and ended is not None and ended >= end:
        if started is not None and started < end:
            return SessionStatus.IN_PROGRESS.value
        return SessionStatus.SCHEDULED.value
    if status == SessionStatus.IN_PROGRESS.value and started is not None and started >= end:
        return SessionStatus.SCHEDULED.value
    return status


def _approval_at(
    log: DailyLog,
    rows: list[OpsStateTransition],
    audits: list[AuditEvent],
    end: datetime,
) -> str | None:
    """Approval as of end, or None when nothing had been submitted yet."""
    if not _before(log.submitted_at, end):
        return None
    replayed = _replay(rows, "approval_status", end)
    if replayed is not _MISSING and replayed is not None:
        return _norm(replayed)
    if not audits:
        return _norm(log.approval_status) or "PENDING"
    status = "PENDING"
    ordered = sorted(audits, key=lambda item: _as_utc(item.created_at) or end)
    for audit in ordered:
        instant = _as_utc(audit.created_at)
        if instant is None or instant >= end:
            continue
        if audit.action in {"create", "resubmit"}:
            status = "PENDING"
        elif audit.action == "approve":
            status = "APPROVED"
        elif audit.action == "reject":
            status = "REJECTED"
    return status


def _load_audits(db: Session, entity_type: str, ids: list[int]) -> dict[int, list[AuditEvent]]:
    grouped: dict[int, list[AuditEvent]] = defaultdict(list)
    if not ids:
        return grouped
    wanted = {str(entity_id) for entity_id in ids}
    for chunk in _chunks(ids):
        str_ids = [str(entity_id) for entity_id in chunk]
        rows = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id.in_(str_ids))
            .order_by(AuditEvent.created_at, AuditEvent.id)
        ).all()
        for row in rows:
            if row.entity_id in wanted:
                grouped[int(row.entity_id)].append(row)
    return grouped


def _case_status_at_eod(
    case: Case,
    audits: list[CaseClientStatusAudit],
    end: datetime,
) -> str:
    status = _norm(case.status) or ""
    ordered = sorted(
        (audit for audit in audits if not _before(audit.changed_at, end)),
        key=lambda audit: (_as_utc(audit.changed_at), audit.id),
        reverse=True,
    )
    for audit in ordered:
        status = _norm(audit.previous_status) or status
    return status


def _pending_billing(row: BillingApprovalRequest, end: datetime) -> bool:
    if not _before(row.requested_at, end):
        return False
    status = _norm(row.status)
    if status == BillingApprovalStatus.PENDING.value:
        return True
    reviewed = _as_utc(row.reviewed_at)
    return reviewed is not None and reviewed >= end and status in {
        BillingApprovalStatus.APPROVED.value,
        BillingApprovalStatus.REJECTED.value,
    }


def _pending_leave(row: TherapistLeave, end: datetime) -> bool:
    if not _before(row.created_at, end):
        return False
    status = _norm(row.status)
    if status == LeaveStatus.PENDING.value:
        return True
    reviewed = _as_utc(row.updated_at) if row.reviewed_by_user_id else None
    return reviewed is not None and reviewed >= end and status in _LEAVE_REVIEWED


def _pending_absence(row: SessionAbsenceRequest, end: datetime) -> bool:
    if _norm(row.absence_type) != SessionAbsenceType.CLIENT_ABSENT.value:
        return False
    if not _before(row.created_at, end):
        return False
    status = _norm(row.status)
    if status == SessionAbsenceStatus.PENDING_APPROVAL.value:
        return True
    reviewed = _as_utc(row.reviewed_at)
    return reviewed is not None and reviewed >= end and status in _ABSENCE_REVIEWED


def build_daily_snapshot(db: Session, day: date) -> dict[str, Any]:
    """Assemble the COO daily snapshot. Performs no writes."""
    start, end = ist_day_bounds(day)
    window_from = day - timedelta(days=4)

    with db.no_autoflush:
        return _build(db, day, start, end, window_from)


def _build(
    db: Session,
    day: date,
    start: datetime,
    end: datetime,
    window_from: date,
) -> dict[str, Any]:
    sessions = db.scalars(
        select(TherapySession).where(TherapySession.scheduled_date == day)
    ).all()
    sessions = [row for row in sessions if _before(row.created_at, end)]
    session_ids = [row.id for row in sessions]
    session_transitions = _load_transitions(db, "session", session_ids)
    session_status: dict[int, str] = {}
    by_status = {item.value: 0 for item in SessionStatus}
    for row in sessions:
        status = _session_status_at(row, session_transitions.get(row.id, []), end)
        if not status:
            continue
        session_status[row.id] = status
        by_status[status] = by_status.get(status, 0) + 1

    completed_ids = [sid for sid, status in session_status.items() if status == SessionStatus.COMPLETED.value]
    logs = []
    if completed_ids:
        logs = db.scalars(select(DailyLog).where(DailyLog.session_id.in_(completed_ids))).all()
    logs_by_session = {log.session_id: log for log in logs}
    log_ids = [log.id for log in logs]
    log_transitions = _load_transitions(db, "daily_log", log_ids)
    log_audits = _load_audits(db, "daily_log", log_ids)

    approved = submitted_not_approved = rejected = nothing = submitted_after = 0
    missing_session_ids: list[int] = []
    sessions_by_id = {row.id: row for row in sessions}
    for session_id in completed_ids:
        log = logs_by_session.get(session_id)
        if log is None:
            nothing += 1
            missing_session_ids.append(session_id)
            continue
        if _as_utc(log.submitted_at) is not None and not _before(log.submitted_at, end):
            submitted_after += 1
        approval = _approval_at(log, log_transitions.get(log.id, []), log_audits.get(log.id, []), end)
        if approval == "APPROVED":
            approved += 1
        elif approval == "REJECTED":
            rejected += 1
        elif approval == "PENDING":
            submitted_not_approved += 1
        else:
            nothing += 1
            missing_session_ids.append(session_id)

    case_ids = {sessions_by_id[sid].case_id for sid in missing_session_ids}
    therapist_ids = {sessions_by_id[sid].therapist_user_id for sid in missing_session_ids}
    case_codes = {}
    if case_ids:
        case_codes = dict(
            db.execute(select(Case.id, Case.case_code).where(Case.id.in_(case_ids))).all()
        )
    therapist_names = _names(db, therapist_ids)
    missing_by_therapist: dict[str, set[str]] = defaultdict(set)
    for session_id in missing_session_ids:
        session = sessions_by_id[session_id]
        name = therapist_names.get(session.therapist_user_id) or "Unknown therapist"
        code = case_codes.get(session.case_id)
        if code:
            missing_by_therapist[name].add(code)
    still_missing = [
        {"therapist_name": name, "case_codes": sorted(codes)}
        for name, codes in sorted(missing_by_therapist.items())
    ]

    tickets = [row for row in db.scalars(select(SupportTicket)).all() if _before(row.created_at, end)]
    ticket_ids = [row.id for row in tickets]
    ticket_transitions = _load_transitions(db, "support_ticket", ticket_ids)
    tickets_missing_history = [
        row.id for row in tickets if "status" not in {item.field_name for item in ticket_transitions.get(row.id, [])}
    ]
    ticket_audits = _load_audits(db, "support_ticket", tickets_missing_history)
    ticket_messages: dict[int, list[TicketMessage]] = defaultdict(list)
    if tickets_missing_history:
        for chunk in _chunks(tickets_missing_history):
            for message in db.scalars(
                select(TicketMessage)
                .where(TicketMessage.ticket_id.in_(chunk))
                .order_by(TicketMessage.created_at, TicketMessage.id)
            ).all():
                ticket_messages[message.ticket_id].append(message)

    not_closed: Counter[str] = Counter({status: 0 for status in _TICKET_OPEN})
    unassigned = 0
    assignee_counts: Counter[int] = Counter()
    created_on_day = 0
    closed_after = 0
    for ticket in tickets:
        if _in_window(ticket.created_at, start, end):
            created_on_day += 1
        rows = ticket_transitions.get(ticket.id, [])
        status = _ticket_status_at(
            ticket,
            rows,
            end,
            ticket_audits.get(ticket.id, []),
            ticket_messages.get(ticket.id, []),
        )
        if status is None:
            continue
        if status not in _TICKET_TERMINAL:
            not_closed[status] += 1
            assignee = _ticket_assignee_at(ticket, rows, end)
            if assignee is None:
                unassigned += 1
            else:
                assignee_counts[assignee] += 1
        became_terminal = any(
            row.field_name == "status"
            and not _before(row.occurred_at, end)
            and row.new_value in _TICKET_TERMINAL
            for row in rows
        )
        if status not in _TICKET_TERMINAL and (
            became_terminal or (_norm(ticket.status) in _TICKET_TERMINAL and not _before(ticket.updated_at, end))
        ):
            closed_after += 1

    assignee_names = _names(db, set(assignee_counts))
    by_assignee = [
        {"name": assignee_names.get(user_id) or "Unknown staff", "count": count}
        for user_id, count in sorted(
            assignee_counts.items(),
            key=lambda item: (-item[1], assignee_names.get(item[0]) or ""),
        )
    ]

    incidents = [row for row in db.scalars(select(Incident)).all() if _before(row.created_at, end)]
    incident_ids = [row.id for row in incidents]
    incident_transitions = _load_transitions(db, "incident", incident_ids)
    incidents_missing_history = [
        row.id
        for row in incidents
        if "status" not in {item.field_name for item in incident_transitions.get(row.id, [])}
    ]
    incident_audits = _load_audits(db, "incident", incidents_missing_history)
    incident_messages: dict[int, list[IncidentMessage]] = defaultdict(list)
    if incidents_missing_history:
        for chunk in _chunks(incidents_missing_history):
            for message in db.scalars(
                select(IncidentMessage)
                .where(IncidentMessage.incident_id.in_(chunk))
                .order_by(IncidentMessage.created_at, IncidentMessage.id)
            ).all():
                incident_messages[message.incident_id].append(message)
    incident_split: Counter[str] = Counter({status: 0 for status in _INCIDENT_OPEN})
    for incident in incidents:
        status = _incident_status_at(
            incident,
            incident_transitions.get(incident.id, []),
            end,
            incident_audits.get(incident.id, []),
            incident_messages.get(incident.id, []),
        )
        if status in incident_split:
            incident_split[status] += 1

    absences = db.scalars(select(SessionAbsenceRequest)).all()
    child_absence_pending = sum(1 for row in absences if _pending_absence(row, end))

    leaves = db.scalars(select(TherapistLeave)).all()
    pending_leaves = [row for row in leaves if _pending_leave(row, end)]
    leave_names = _names(db, {row.therapist_user_id for row in pending_leaves})
    leave_name_list = sorted({leave_names.get(row.therapist_user_id) or "Unknown therapist" for row in pending_leaves})

    approvals = db.scalars(select(BillingApprovalRequest)).all()
    pending_approvals = [row for row in approvals if _pending_billing(row, end)]
    approval_case_ids = {row.case_id for row in pending_approvals}
    approval_codes = {}
    if approval_case_ids:
        approval_codes = dict(
            db.execute(select(Case.id, Case.case_code).where(Case.id.in_(approval_case_ids))).all()
        )

    cases = [row for row in db.scalars(select(Case)).all() if _before(row.created_at, end)]
    created_codes = sorted(row.case_code for row in cases if _in_window(row.created_at, start, end))
    case_id_list = [row.id for row in cases]
    status_audits: dict[int, list[CaseClientStatusAudit]] = defaultdict(list)
    if case_id_list:
        for chunk in _chunks(case_id_list):
            for audit in db.scalars(
                select(CaseClientStatusAudit).where(
                    CaseClientStatusAudit.case_id.in_(chunk),
                    CaseClientStatusAudit.changed_at >= end,
                )
            ).all():
                status_audits[audit.case_id].append(audit)
    active_ids = {
        row.id
        for row in cases
        if _case_status_at_eod(row, status_audits.get(row.id, []), end) == CaseStatus.ACTIVE.value
    }
    submitted_case_ids: set[int] = set()
    if active_ids:
        for chunk in _chunks(list(active_ids)):
            log_rows = db.execute(
                select(TherapySession.case_id, DailyLog.submitted_at)
                .join(DailyLog, DailyLog.session_id == TherapySession.id)
                .where(
                    TherapySession.case_id.in_(chunk),
                    TherapySession.scheduled_date >= window_from,
                    TherapySession.scheduled_date <= day,
                    DailyLog.submitted_at.is_not(None),
                )
            ).all()
            for case_id, submitted_at in log_rows:
                if _before(submitted_at, end):
                    submitted_case_ids.add(case_id)

    return {
        "date": day.isoformat(),
        "timezone": "Asia/Kolkata",
        "window_start": start.isoformat(),
        "window_end_exclusive": end.isoformat(),
        "sessions": {"by_status": by_status},
        "session_logs": {
            "completed_sessions": len(completed_ids),
            "approved": approved,
            "submitted_not_approved": submitted_not_approved,
            "rejected": rejected,
            "nothing_submitted": nothing,
            "nothing_submitted_at_eod": nothing,
            "submitted_after_eod": submitted_after,
            "still_missing_at_eod": still_missing,
        },
        "tickets": {
            "not_closed_by_status": dict(not_closed),
            "not_closed_total": sum(not_closed.values()),
            "unassigned": unassigned,
            "by_assignee": by_assignee,
            "created_on_day": created_on_day,
            "closed_after_day_end": closed_after,
        },
        "incidents": {
            "not_closed_by_status": dict(incident_split),
            "not_closed_total": sum(incident_split.values()),
        },
        "child_absence_pending": child_absence_pending,
        "leave_pending": {"count": len(pending_leaves), "therapist_names": leave_name_list},
        "billing_change_approvals_pending": {
            "count": len(pending_approvals),
            "case_codes": sorted(code for code in (approval_codes.get(row.case_id) for row in pending_approvals) if code),
        },
        "cases_created": created_codes,
        "active_cases_without_submitted_log": {
            "window_from": window_from.isoformat(),
            "window_to": day.isoformat(),
            "active_cases": len(active_ids),
            "without_submitted_log": len(active_ids - submitted_case_ids),
        },
    }
