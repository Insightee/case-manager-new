from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import RoleName, effective_role, has_any_role, user_has_permission
from app.models.calendar_availability import (
    AvailabilityExceptionType,
    CalendarProvider,
    StaffAvailabilityException,
    UserCalendarConnection,
)
from app.models.case import Case
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus
from app.models.session import Session as TherapySession, SessionStatus
from app.models.user import User
from app.services import availability_service
from app.services import parent_service
from app.services.cm_meeting_service import meeting_participant_user_ids, meeting_to_calendar_dict
from app.services.reports_export_helpers import parse_int_list

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _is_admin_calendar_scope(user: User) -> bool:
    return user_has_permission(user, "admin.override") or has_any_role(
        user,
        RoleName.SUPER_ADMIN,
        RoleName.ADMIN,
        RoleName.MODULE_ADMIN,
    )


def _parse_calendar_user_ids(user_ids: str | None, user: User) -> list[int]:
    if user_ids:
        try:
            requested = parse_int_list(user_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Looks like we still need valid user_ids.") from exc
    else:
        requested = [user.id]

    if not requested:
        raise HTTPException(status_code=400, detail="Please choose at least one user.")

    requested = sorted({int(uid) for uid in requested if int(uid) > 0})
    if not requested:
        raise HTTPException(status_code=400, detail="Please choose at least one user.")

    if not _is_admin_calendar_scope(user) and any(uid != user.id for uid in requested):
        raise HTTPException(status_code=403, detail="You can only request your own calendar.")

    return requested


def _event_time(value: time | None) -> str | None:
    return value.strftime("%H:%M:%S") if value else None


def _meeting_event_payload(meeting: CaseManagerMeeting, db: Session) -> dict[str, object]:
    payload = meeting_to_calendar_dict(meeting, db)
    participant_ids = sorted(meeting_participant_user_ids(meeting))
    return {
        "id": f"cm_meeting-{meeting.id}",
        "event_type": "cm_meeting",
        "meeting_id": meeting.id,
        "user_ids": participant_ids,
        "date": payload.get("date"),
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "title": payload.get("title"),
        "case_id": payload.get("case_id"),
        "case_code": payload.get("case_code"),
        "child_name": payload.get("child_name"),
        "meeting_type": payload.get("meeting_type"),
        "status": payload.get("status"),
        "url": None,
    }


def _session_event_payload(session: TherapySession, db: Session) -> dict[str, object]:
    case = db.get(Case, session.case_id)
    child_name = case.child.full_name if case and case.child else None
    title = child_name or (case.case_code if case else f"Session #{session.id}")
    start_time = _event_time(session.start_time)
    end_time = _event_time(session.end_time)
    if not end_time and session.start_time:
        end_dt = datetime.combine(session.scheduled_date, session.start_time) + timedelta(
            minutes=int(session.scheduled_duration_mins or 60)
        )
        end_time = end_dt.time().strftime("%H:%M:%S")
    return {
        "id": f"therapy_session-{session.id}",
        "event_type": "therapy_session",
        "session_id": session.id,
        "user_ids": [session.therapist_user_id],
        "date": session.scheduled_date.isoformat(),
        "start_time": start_time,
        "end_time": end_time,
        "title": title,
        "case_id": session.case_id,
        "status": session.status.value if session.status else None,
        "url": None,
    }


def _availability_block_payload(exc: StaffAvailabilityException) -> dict[str, object]:
    start_time = exc.start_time.strftime("%H:%M:%S") if exc.start_time else "00:00:00"
    end_time = exc.end_time.strftime("%H:%M:%S") if exc.end_time else "23:59:59"
    if exc.type == AvailabilityExceptionType.CLOSED:
        title = exc.reason or "Availability block"
    else:
        title = exc.reason or "Availability block"
    return {
        "id": f"availability_block-{exc.id}",
        "event_type": "availability_block",
        "user_ids": [exc.user_id],
        "date": exc.date.isoformat(),
        "start_time": start_time,
        "end_time": end_time,
        "title": title,
        "case_id": None,
        "status": exc.type.value,
        "url": None,
    }


def _external_busy_payload(user_id: int, start: datetime, end: datetime, index: int) -> dict[str, object]:
    start_local = start.astimezone(availability_service.IST)
    end_local = end.astimezone(availability_service.IST)
    return {
        "id": f"external_busy-{user_id}-{index}",
        "event_type": "external_busy",
        "user_ids": [user_id],
        "date": start_local.date().isoformat(),
        "start_time": start_local.strftime("%H:%M:%S"),
        "end_time": end_local.strftime("%H:%M:%S"),
        "title": None,
        "case_id": None,
        "status": "BUSY",
        "url": None,
    }


@router.get("/availability")
def calendar_availability(
    user_ids: str = Query(..., description="Comma-separated user IDs to intersect"),
    date_from: str = Query(..., alias="date_from"),
    date_to: str = Query(..., alias="date_to"),
    duration_minutes: int = Query(30, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ids = parse_int_list(user_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Looks like we still need valid user_ids.") from exc
    if not ids:
        raise HTTPException(status_code=400, detail="Please choose at least one attendee.")
    try:
        from_dt = date.fromisoformat(date_from)
        to_dt = date.fromisoformat(date_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Please use YYYY-MM-DD for date_from and date_to.") from exc
    return availability_service.free_slots(db, ids, from_dt, to_dt, duration_minutes, user)


@router.get("/events")
def calendar_events(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    user_ids: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to must be on or after from")

    requested_ids = _parse_calendar_user_ids(user_ids, user)
    requested_set = set(requested_ids)
    role = effective_role(user)
    is_parent = role == RoleName.PARENT.value

    events: list[dict[str, object]] = []

    meeting_stmt = (
        select(CaseManagerMeeting)
        .where(
            CaseManagerMeeting.scheduled_date >= from_date,
            CaseManagerMeeting.scheduled_date <= to_date,
            CaseManagerMeeting.status.in_(
                [MeetingStatus.SCHEDULED, MeetingStatus.COMPLETED, MeetingStatus.NO_SHOW]
            ),
        )
        .order_by(CaseManagerMeeting.scheduled_date, CaseManagerMeeting.scheduled_time)
    )
    if is_parent:
        child_ids = parent_service.child_ids_for_parent(db, user.id)
        if not child_ids:
            return {"events": []}
        case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
        if not case_ids:
            return {"events": []}
        meetings = list(db.scalars(meeting_stmt.where(CaseManagerMeeting.case_id.in_(case_ids))).all())
    else:
        meetings = list(
            db.scalars(
                meeting_stmt.where(
                    or_(
                        CaseManagerMeeting.case_manager_user_id.in_(requested_ids),
                        CaseManagerMeeting.parent_user_id.in_(requested_ids),
                        CaseManagerMeeting.therapist_user_id.in_(requested_ids),
                        CaseManagerMeeting.mentor_user_id.in_(requested_ids),
                    )
                )
            ).all()
        )
    for meeting in meetings:
        if is_parent or meeting_participant_user_ids(meeting).intersection(requested_set):
            events.append(_meeting_event_payload(meeting, db))

    if not is_parent:
        session_stmt = (
            select(TherapySession)
            .where(
                TherapySession.scheduled_date >= from_date,
                TherapySession.scheduled_date <= to_date,
                TherapySession.status.in_(
                    [
                        SessionStatus.SCHEDULED,
                        SessionStatus.IN_PROGRESS,
                        SessionStatus.COMPLETED,
                        SessionStatus.NO_SHOW,
                        SessionStatus.CLIENT_ABSENT,
                        SessionStatus.THERAPIST_LEAVE,
                    ]
                ),
                TherapySession.therapist_user_id.in_(requested_ids),
            )
            .order_by(TherapySession.scheduled_date, TherapySession.start_time)
        )
        for session in db.scalars(session_stmt).all():
            events.append(_session_event_payload(session, db))

        exc_stmt = (
            select(StaffAvailabilityException)
            .where(
                StaffAvailabilityException.date >= from_date,
                StaffAvailabilityException.date <= to_date,
                StaffAvailabilityException.user_id.in_(requested_ids),
            )
            .order_by(StaffAvailabilityException.date, StaffAvailabilityException.start_time)
        )
        for exc in db.scalars(exc_stmt).all():
            events.append(_availability_block_payload(exc))

        external_busy = availability_service.external_busy_intervals(db, requested_ids, from_date, to_date)
        for uid, intervals in external_busy.items():
            for index, (busy_start, busy_end) in enumerate(intervals, start=1):
                events.append(_external_busy_payload(uid, busy_start, busy_end, index))

    events.sort(
        key=lambda item: (
            str(item.get("date") or ""),
            str(item.get("start_time") or ""),
            str(item.get("event_type") or ""),
            str(item.get("id") or ""),
        )
    )
    return {"events": events}


@router.get("/connections/google")
def get_google_connection(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = availability_service.serialize_google_connection(
        db.scalars(
            select(UserCalendarConnection).where(
                UserCalendarConnection.user_id == user.id,
                UserCalendarConnection.provider == CalendarProvider.GOOGLE.value,
            )
        ).first()
    )
    return connection


@router.post("/connections/google/authorize")
def authorize_google_connection(
    request: Request,
    user: User = Depends(get_current_user),
):
    if not settings.google_calendar_client_id or not settings.google_calendar_client_secret:
        raise HTTPException(
            status_code=400,
            detail="Google Calendar OAuth is not configured. Set GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET.",
        )
    redirect_uri = str(request.url_for("google_calendar_callback"))
    return {
        "authorization_url": availability_service.build_google_authorization_url(user, redirect_uri=redirect_uri),
    }


@router.get("/connections/google/callback", name="google_calendar_callback")
def google_connection_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google connection failed: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing Google authorization code or state.")
    try:
        availability_service.upsert_google_connection_from_callback(
            db,
            state=state,
            code=code,
            redirect_uri=str(request.url_for("google_calendar_callback")),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    frontend = settings.frontend_url.rstrip("/")
    return RedirectResponse(f"{frontend}/admin/meetings?google_calendar=connected", status_code=302)


@router.delete("/connections/google")
def delete_google_connection(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    availability_service.revoke_google_connection(db, user.id)
    db.commit()
    return {"ok": True}

