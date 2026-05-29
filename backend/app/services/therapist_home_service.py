from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import ensure_utc_aware
from app.models.case import Case
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.schemas.session import SessionRead
from app.schemas.therapist_home import (
    SchedulePreviewItem,
    TherapistCaseBoardRow,
    TherapistCaseBoardSection,
    TherapistCaseBoardStat,
    TherapistHomeResponse,
    TherapistHomeStats,
    TherapistPendingAssignment,
    TherapistReportsPipelineResponse,
    TherapistSessionsWorkspaceResponse,
)
from app.services import assignment_acceptance_service as accept_svc
from app.services import parent_service, session_service
from app.services.address_service import case_service_address_read
from app.services import therapist_portal_queries as tpq
from app.services.invite_on_start_service import _pending_intake_invite
from sqlalchemy.orm import Session


def _today_iso() -> str:
    return date.today().isoformat()


def _format_time(t: Any) -> str:
    if not t:
        return ""
    return str(t)[:5]


def _session_read(s: TherapySession, case: Optional[Case] = None) -> SessionRead:
    child_name = None
    if case and case.child:
        child_name = case.child.full_name
    elif getattr(s, "case", None) and s.case.child:
        child_name = s.case.child.full_name
        case = s.case
    return SessionRead(
        id=s.id,
        case_id=s.case_id,
        case_code=case.case_code if case else None,
        child_name=child_name,
        therapist_user_id=s.therapist_user_id,
        scheduled_date=s.scheduled_date,
        start_time=s.start_time,
        end_time=s.end_time,
        actual_start_at=ensure_utc_aware(s.actual_start_at),
        actual_end_at=ensure_utc_aware(s.actual_end_at),
        auto_ended=bool(s.auto_ended),
        slot_duration_minutes=s.slot_duration_minutes,
        mode=s.mode,
        status=s.status,
        has_daily_log=s.daily_log is not None,
        checkin_lat=s.checkin_lat,
        checkin_lng=s.checkin_lng,
        checkout_lat=s.checkout_lat,
        checkout_lng=s.checkout_lng,
    )


def _stage_badge(case_row: Case, needs_log_count: int, report_pending: bool) -> tuple[str, str]:
    if needs_log_count > 0:
        return "observation", "Log due"
    if report_pending:
        return "iep", "Report pending"
    stage = (
        case_row.operational_stage
        or case_row.status.value
        if hasattr(case_row.status, "value")
        else str(case_row.status) or "ACTIVE"
    ).lower()
    if "observation" in stage:
        return "observation", "Observation"
    if "iep" in stage:
        return "iep", "IEP"
    status_val = case_row.status.value if hasattr(case_row.status, "value") else str(case_row.status)
    if status_val == "CLOSED":
        return "completed", "Closed"
    return "active", case_row.operational_stage or "Active"


def build_cases_board(
    db: Session,
    cases: list[Case],
    *,
    needs_log_by_case: dict[int, int],
    upcoming_by_case: dict[int, int],
    reports_by_case: dict[int, list[MonthlyReport]],
    slots: list[TherapistSlot],
) -> dict:
    today = _today_iso()
    booked_slots = [sl for sl in slots if sl.status == SlotStatus.BOOKED and sl.case_id]

    cm_ids = {c.case_manager_user_id for c in cases if c.case_manager_user_id}
    cm_users: dict[int, User] = {}
    if cm_ids:
        for u in db.scalars(select(User).where(User.id.in_(cm_ids))).all():
            cm_users[u.id] = u

    enriched: list[TherapistCaseBoardRow] = []
    for c in cases:
        needs_log_n = needs_log_by_case.get(c.id, 0)
        upcoming_n = upcoming_by_case.get(c.id, 0)
        case_reports = reports_by_case.get(c.id, [])
        draft_report = next(
            (r for r in case_reports if r.status in (ReportStatus.DRAFT, ReportStatus.UNDER_REVIEW)),
            None,
        )
        next_booking = None
        case_bookings = [
            sl
            for sl in booked_slots
            if sl.case_id == c.id and sl.slot_date.isoformat() >= today
        ]
        if case_bookings:
            case_bookings.sort(key=lambda sl: (sl.slot_date.isoformat(), _format_time(sl.start_time)))
            nb = case_bookings[0]
            next_booking = {
                "date": nb.slot_date.isoformat(),
                "startTime": _format_time(nb.start_time),
                "endTime": _format_time(nb.end_time),
            }

        next_due = "—"
        if needs_log_n:
            next_due = f"{needs_log_n} log{'s' if needs_log_n > 1 else ''} due"
        elif draft_report:
            next_due = f"Report: {draft_report.month}"
        elif next_booking:
            next_due = f"Booking {next_booking['date']}"

        badge_variant, badge_label = _stage_badge(c, needs_log_n, bool(draft_report))
        critical = needs_log_n > 0 or (
            draft_report is not None and draft_report.status == ReportStatus.UNDER_REVIEW
        )
        svc = case_service_address_read(c)
        cm = cm_users.get(c.case_manager_user_id) if c.case_manager_user_id else None
        parent_pending = False
        if c.child_id and not parent_service.primary_parent_user_id_for_child(db, c.child_id):
            inv = _pending_intake_invite(db, c)
            parent_pending = inv is not None
        enriched.append(
            TherapistCaseBoardRow(
                id=c.id,
                caseId=c.case_code,
                child=c.child.full_name if c.child else "—",
                service=c.service_type or c.product_module,
                productModule=c.product_module,
                stage=badge_label,
                badgeVariant=badge_variant,
                nextDue=next_due,
                nextBooking=next_booking,
                critical=critical,
                needsLogCount=needs_log_n,
                upcomingCount=upcoming_n,
                status=c.status.value if hasattr(c.status, "value") else str(c.status),
                mapsUrl=svc.maps_url if svc else None,
                serviceAddress=svc.model_dump() if svc else None,
                borderAccent="yellow"
                if critical
                else ("yellow" if needs_log_n else ("teal" if next_booking else "blue")),
                showSubmitReport=bool(draft_report) or len(case_reports) == 0,
                reportStatus=draft_report.status.value
                if draft_report and hasattr(draft_report.status, "value")
                else (draft_report.status if draft_report else (case_reports[0].status.value if case_reports else None)),
                caseManagerName=cm.full_name if cm else None,
                caseManagerEmail=cm.email if cm else None,
                parentSignupPending=parent_pending,
            )
        )

    attention_ids: set[int] = set()
    attention = []
    for row in enriched:
        if row.critical or row.needsLogCount > 0:
            attention_ids.add(row.id)
            attention.append(row)
    in_progress = [r for r in enriched if r.id not in attention_ids and r.status != "CLOSED"]
    completed = [r for r in enriched if r.status == "CLOSED"]

    booking_count = len([sl for sl in booked_slots if sl.slot_date.isoformat() >= today])
    attention_all = [r for r in enriched if r.critical or r.needsLogCount > 0]

    stats = [
        TherapistCaseBoardStat(id="total", label="Total cases", value=len(enriched), variant="indigo"),
        TherapistCaseBoardStat(id="attention", label="Needs attention", value=len(attention_all), variant="yellow"),
        TherapistCaseBoardStat(
            id="logs",
            label="Logs due",
            value=sum(r.needsLogCount for r in enriched),
            variant="purple",
        ),
        TherapistCaseBoardStat(id="bookings", label="Upcoming bookings", value=booking_count, variant="teal"),
    ]
    sections = [
        TherapistCaseBoardSection(
            id="attention", title="Attention required", tone="danger", count=len(attention), cases=attention
        ),
        TherapistCaseBoardSection(
            id="in_progress", title="In progress", tone="warning", count=len(in_progress), cases=in_progress
        ),
        TherapistCaseBoardSection(
            id="completed", title="Closed", tone="success", count=len(completed), cases=completed
        ),
    ]
    return {
        "stats": [s.model_dump() for s in stats],
        "sections": [s.model_dump() for s in sections],
        "allCases": [r.model_dump() for r in enriched],
    }


def merge_schedule_preview(
    sessions: list[SessionRead],
    slots: list[dict],
    cm_meetings: list[dict] | None = None,
) -> list[SchedulePreviewItem]:
    today = _today_iso()
    items: list[SchedulePreviewItem] = []
    for s in sessions:
        if s.status != SessionStatus.SCHEDULED or s.scheduled_date.isoformat() < today:
            continue
        items.append(
            SchedulePreviewItem(
                kind="session",
                key=f"session-{s.id}",
                sessionId=s.id,
                caseId=s.case_id,
                childName=s.child_name,
                caseCode=s.case_code,
                date=s.scheduled_date.isoformat(),
                startTime=_format_time(s.start_time),
                endTime=_format_time(s.end_time),
                mode=s.mode.value if hasattr(s.mode, "value") else str(s.mode) if s.mode else None,
                subtitle="Scheduled session",
            )
        )
    for sl in slots:
        if sl.get("status") != "BOOKED" or not sl.get("case_id"):
            continue
        slot_date = sl.get("slot_date") or sl.get("slotDate")
        if isinstance(slot_date, date):
            slot_date = slot_date.isoformat()
        if not slot_date or slot_date < today:
            continue
        st = _format_time(sl.get("start_time") or sl.get("startTime"))
        dup = any(
            i.caseId == sl.get("case_id") and i.date == slot_date and i.startTime == st for i in items
        )
        if dup:
            continue
        src = sl.get("booking_source") or sl.get("bookingSource")
        items.append(
            SchedulePreviewItem(
                kind="booking",
                key=f"slot-{sl.get('id')}",
                slotId=sl.get("id"),
                caseId=sl.get("case_id"),
                childName=sl.get("child_name") or sl.get("childName"),
                caseCode=sl.get("case_code") or sl.get("caseCode"),
                date=slot_date,
                startTime=st,
                endTime=_format_time(sl.get("end_time") or sl.get("endTime")),
                bookingSource=src,
                subtitle="Parent booking" if src == "PARENT" else "Calendar booking",
            )
        )
    for m in cm_meetings or []:
        m_date = m.get("date")
        if not m_date or m_date < today:
            continue
        st = m.get("start_time") or "09:00"
        items.append(
            SchedulePreviewItem(
                kind="cm_meeting",
                key=f"cm-meeting-{m.get('id')}",
                meetingId=m.get("id"),
                caseId=m.get("case_id"),
                childName=m.get("child_name"),
                caseCode=m.get("case_code"),
                date=m_date,
                startTime=st,
                endTime=m.get("end_time") or st,
                subtitle=m.get("title") or "CM meeting",
            )
        )
    items.sort(key=lambda i: f"{i.date}{i.startTime}")
    return items[:20]


def _prepare_session_reads(db: Session, sessions: list[TherapySession]) -> list[SessionRead]:
    out: list[SessionRead] = []
    for s in sessions:
        if s.status == SessionStatus.IN_PROGRESS:
            s = session_service.auto_end_if_stale(db, s)
        out.append(_session_read(s, s.case))
    return out


def build_therapist_home(db: Session, user: User) -> TherapistHomeResponse:
    cases = tpq.assigned_cases(db, user)
    case_ids = [c.id for c in cases]
    today = date.today()
    month_label = tpq.current_month_label()

    upcoming_raw = tpq.fetch_upcoming_sessions(
        db, user, case_ids, days=tpq.SLOT_FORWARD_DAYS, limit=tpq.UPCOMING_LIMIT
    )
    needs_log_raw = tpq.fetch_needs_log_sessions(db, user, case_ids, limit=tpq.NEEDS_LOG_LIMIT)

    reports = tpq.fetch_home_reports(db, user, case_ids, month_label)
    reports_by_case: dict[int, list[MonthlyReport]] = {}
    for r in reports:
        reports_by_case.setdefault(r.case_id, []).append(r)

    slot_end = today + timedelta(days=tpq.SLOT_FORWARD_DAYS)
    slots = tpq.fetch_booked_slots(db, user, from_date=today, to_date=slot_end)
    from app.services import slot_calendar_service as cal

    slot_dicts = [cal._slot_to_dict(sl) for sl in slots]

    upcoming_reads = _prepare_session_reads(db, upcoming_raw)[: tpq.HOME_UPCOMING_CAP]
    needs_log_reads = _prepare_session_reads(db, needs_log_raw)[: tpq.HOME_NEEDS_LOG_CAP]

    active = session_service.get_active_session(db, user.id)
    active_read = _session_read(active, active.case) if active and active.case else None
    active_id = active.id if active else None

    draft_reports, under_review = tpq.count_reports_by_status(db, user, case_ids)
    pending_logs = tpq.count_pending_log_approvals(db, user, case_ids)

    greeting = None
    if upcoming_reads:
        greeting = upcoming_reads[0].child_name
    elif needs_log_reads:
        greeting = needs_log_reads[0].child_name

    board = build_cases_board(
        db,
        cases,
        needs_log_by_case=tpq.needs_log_count_by_case(db, user, case_ids),
        upcoming_by_case=tpq.upcoming_count_by_case(db, user, case_ids),
        reports_by_case=reports_by_case,
        slots=slots,
    )
    from app.services.cm_meeting_service import fetch_cm_meetings_for_user, meeting_to_calendar_dict

    cm_rows = fetch_cm_meetings_for_user(
        db, user.id, from_date=today, to_date=slot_end
    )
    cm_dicts = [meeting_to_calendar_dict(m, db) for m in cm_rows]
    schedule = merge_schedule_preview(upcoming_reads, slot_dicts, cm_dicts)

    pending_assignments = [
        TherapistPendingAssignment(**row)
        for row in accept_svc.pending_acceptance_for_therapist(db, user.id)
    ]

    return TherapistHomeResponse(
        greeting_context=greeting,
        stats=TherapistHomeStats(
            case_count=len(cases),
            needs_log=len(needs_log_reads),
            pending_logs=pending_logs,
            draft_reports=draft_reports,
            under_review_reports=under_review,
            active_session_id=active_id,
        ),
        active_session=active_read,
        upcoming_sessions=upcoming_reads,
        needs_log_sessions=needs_log_reads,
        cases_board=board,
        schedule_preview=schedule,
        pending_assignment_acceptance=pending_assignments,
    )


def build_sessions_workspace(db: Session, user: User) -> TherapistSessionsWorkspaceResponse:
    cases = tpq.assigned_cases(db, user)
    case_ids = [c.id for c in cases]
    today = date.today()

    upcoming_raw = tpq.fetch_upcoming_sessions(db, user, case_ids, days=7, limit=tpq.UPCOMING_LIMIT)
    needs_log_raw = tpq.fetch_needs_log_sessions(db, user, case_ids, limit=tpq.NEEDS_LOG_LIMIT)

    upcoming_reads = _prepare_session_reads(db, upcoming_raw)
    needs_log_reads = _prepare_session_reads(db, needs_log_raw)

    active = session_service.get_active_session(db, user.id)
    active_read = _session_read(active, active.case) if active and active.case else None

    slot_end = today + timedelta(days=tpq.SLOT_FORWARD_DAYS)
    slots = tpq.fetch_booked_slots(db, user, from_date=today, to_date=slot_end)
    from app.services import slot_calendar_service as cal

    return TherapistSessionsWorkspaceResponse(
        upcoming=upcoming_reads[: tpq.UPCOMING_LIMIT],
        active_session=active_read,
        needs_log=needs_log_reads[: tpq.NEEDS_LOG_LIMIT],
        booked_slots=[cal._slot_to_dict(sl) for sl in slots],
    )


def _format_relative(iso: Any) -> str:
    if not iso:
        return ""
    from datetime import datetime, timezone

    d = iso if isinstance(iso, datetime) else datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - d
    mins = int(diff.total_seconds() / 60)
    if mins < 60:
        return f"{mins or 1} min ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs} hour{'s' if hrs > 1 else ''}"
    days = hrs // 24
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return d.strftime("%Y-%m-%d")


def build_reports_pipeline(db: Session, user: User) -> TherapistReportsPipelineResponse:
    cases = tpq.assigned_cases(db, user)
    case_ids = [c.id for c in cases]
    month_label = tpq.current_month_label()
    reports = tpq.fetch_pipeline_reports(db, user, case_ids, month_label)
    months_present = tpq.case_ids_with_report_month(db, user, case_ids, month_label)

    def to_card(report: MonthlyReport) -> dict:
        case = next((c for c in cases if c.id == report.case_id), None)
        st = report.status.value if hasattr(report.status, "value") else str(report.status)
        status_map = {
            "UNDER_REVIEW": "under_review",
            "PUBLISHED": "published",
            "DRAFT": "draft",
            "REJECTED": "rejected",
        }
        return {
            "id": report.id,
            "caseId": case.case_code if case else f"Case #{report.case_id}",
            "caseDbId": report.case_id,
            "child": case.child.full_name if case and case.child else "—",
            "month": report.month,
            "status": status_map.get(st, st.lower()),
            "apiStatus": st,
            "summary": report.summary,
            "reviewerComment": report.reviewer_comment,
            "lastUpdated": _format_relative(report.updated_at or report.created_at),
            "dueInfo": report.reviewer_comment
            if report.reviewer_comment
            else ("Resubmit after edits" if st == "REJECTED" else None),
        }

    attention: list[dict] = []
    in_progress: list[dict] = []
    published: list[dict] = []

    for r in reports:
        card = to_card(r)
        st = r.status
        if st == ReportStatus.REJECTED:
            attention.append({**card, "attentionType": "rejected", "statusLabel": "Rejected"})
        elif st in (ReportStatus.DRAFT, ReportStatus.UNDER_REVIEW):
            in_progress.append(card)
        elif st in (ReportStatus.PUBLISHED, ReportStatus.APPROVED) and r.month == month_label:
            published.append(card)

    for c in cases:
        if c.id not in months_present:
            attention.append(
                {
                    "id": f"missing-{c.id}",
                    "caseId": c.case_code,
                    "caseDbId": c.id,
                    "child": c.child.full_name if c.child else "—",
                    "month": month_label,
                    "attentionType": "not_started",
                    "statusLabel": "Not started",
                    "dueInfo": "No report started for this month",
                    "isPlaceholder": True,
                }
            )

    pipeline = {
        "draft": sum(1 for r in in_progress if r.get("status") == "draft"),
        "underReview": sum(1 for r in in_progress if r.get("status") == "under_review"),
        "published": len(published),
        "overdue": sum(1 for a in attention if a.get("attentionType") == "overdue"),
    }
    return TherapistReportsPipelineResponse(
        attention=attention,
        in_progress=in_progress,
        published=published,
        pipeline=pipeline,
        month_label=month_label,
    )
