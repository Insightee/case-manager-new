"""Staff daily attendance — clock in/out, pause/resume, forgot-to-log."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import log_audit
from app.core.timezone import IST, ensure_utc_aware, now_ist, today_ist
from app.models.leave import LeaveStatus
from app.models.staff_attendance import (
    StaffAttendance,
    StaffAttendanceEntryType,
    StaffAttendanceSegment,
    StaffAttendanceSegmentType,
    StaffAttendanceStatus,
)
from app.models.staff_leave import StaffLeave
from app.models.user import User
from app.services.staff_attendance_access import assert_staff_attendance_eligible

MIN_WORK_SUMMARY_LEN = 3
FORGOT_LOOKBACK_DAYS = 1  # today + yesterday = 2 calendar days


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _segment_seconds(segment: StaffAttendanceSegment, end_at: datetime | None = None) -> int:
    start = ensure_utc_aware(segment.started_at)
    end = ensure_utc_aware(segment.ended_at or end_at)
    if not start or not end:
        return 0
    return max(0, int((end - start).total_seconds()))


def _recalculate_totals(attendance: StaffAttendance, now: datetime | None = None) -> None:
    now = now or _utc_now()
    work = 0
    breaks = 0
    for seg in attendance.segments:
        end = seg.ended_at or (now if attendance.status == StaffAttendanceStatus.IN_PROGRESS else None)
        secs = _segment_seconds(seg, end)
        if seg.segment_type == StaffAttendanceSegmentType.WORK:
            work += secs
        else:
            breaks += secs
    attendance.total_work_seconds = work
    attendance.total_break_seconds = breaks


def _open_segment(attendance: StaffAttendance) -> StaffAttendanceSegment | None:
    for seg in reversed(attendance.segments):
        if seg.ended_at is None:
            return seg
    return None


def _get_live_attendance(db: Session, user_id: int, work_date: date, *, for_update: bool = False) -> StaffAttendance | None:
    stmt = (
        select(StaffAttendance)
        .where(
            StaffAttendance.user_id == user_id,
            StaffAttendance.work_date == work_date,
            StaffAttendance.entry_type == StaffAttendanceEntryType.LIVE,
        )
        .options(selectinload(StaffAttendance.segments))
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def _has_approved_leave(db: Session, user_id: int, work_date: date) -> bool:
    row = db.scalars(
        select(StaffLeave).where(
            StaffLeave.staff_user_id == user_id,
            StaffLeave.leave_date == work_date,
            StaffLeave.status == LeaveStatus.APPROVED,
        )
    ).first()
    return row is not None


def _validate_work_summary(text: str | None) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) < MIN_WORK_SUMMARY_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Let's add a few words about what you worked on before saving.",
        )
    return cleaned


def _first_last_times(attendance: StaffAttendance) -> tuple[datetime | None, datetime | None]:
    if attendance.entry_type == StaffAttendanceEntryType.FORGOT:
        return attendance.manual_start_at, attendance.manual_end_at
    if not attendance.segments:
        return None, None
    starts = [ensure_utc_aware(s.started_at) for s in attendance.segments if s.started_at]
    ends = [ensure_utc_aware(s.ended_at) for s in attendance.segments if s.ended_at]
    first = min(starts) if starts else None
    last = max(ends) if ends else None
    if attendance.status == StaffAttendanceStatus.IN_PROGRESS:
        open_seg = _open_segment(attendance)
        if open_seg and open_seg.started_at:
            candidate = ensure_utc_aware(open_seg.started_at)
            if first is None or (candidate and candidate < first):
                first = candidate
    return first, last


def serialize_attendance(attendance: StaffAttendance, db: Session) -> dict:
    now = _utc_now()
    if attendance.status == StaffAttendanceStatus.IN_PROGRESS:
        _recalculate_totals(attendance, now)
    first, last = _first_last_times(attendance)
    open_seg = _open_segment(attendance) if attendance.status == StaffAttendanceStatus.IN_PROGRESS else None
    session_start = None
    if open_seg and open_seg.started_at:
        session_start = ensure_utc_aware(open_seg.started_at)
    user = db.get(User, attendance.user_id)
    return {
        "id": attendance.id,
        "user_id": attendance.user_id,
        "staff_name": user.full_name if user else None,
        "work_date": attendance.work_date.isoformat(),
        "day_name": attendance.work_date.strftime("%A"),
        "entry_type": attendance.entry_type.value,
        "status": attendance.status.value,
        "work_summary": attendance.work_summary,
        "forgot_reason": attendance.forgot_reason,
        "total_work_seconds": attendance.total_work_seconds,
        "total_break_seconds": attendance.total_break_seconds,
        "is_paused": attendance.is_paused,
        "auto_closed": attendance.auto_closed,
        "clock_in_at": first.isoformat() if first else None,
        "clock_out_at": last.isoformat() if last else None,
        "session_start_at": session_start.isoformat() if session_start else None,
        "created_at": attendance.created_at.isoformat() if attendance.created_at else None,
        "updated_at": attendance.updated_at.isoformat() if attendance.updated_at else None,
        "record_kind": "attendance",
    }


def get_today_state(db: Session, user: User) -> dict:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    live = _get_live_attendance(db, user.id, today)
    in_progress = live is not None and live.status == StaffAttendanceStatus.IN_PROGRESS
    return {
        "work_date": today.isoformat(),
        "is_clocked_in": in_progress and not live.is_paused,
        "is_paused": bool(live and live.is_paused),
        "attendance": serialize_attendance(live, db) if live else None,
    }


def clock_in(db: Session, user: User, meta: dict | None = None) -> StaffAttendance:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    now = _utc_now()
    live = _get_live_attendance(db, user.id, today, for_update=True)

    if live and live.status == StaffAttendanceStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already clocked in for today.")

    if not live:
        live = StaffAttendance(
            user_id=user.id,
            work_date=today,
            entry_type=StaffAttendanceEntryType.LIVE,
            status=StaffAttendanceStatus.IN_PROGRESS,
        )
        db.add(live)
        db.flush()
    else:
        live.status = StaffAttendanceStatus.IN_PROGRESS
        live.is_paused = False
        live.auto_closed = False

    db.add(
        StaffAttendanceSegment(
            attendance_id=live.id,
            segment_type=StaffAttendanceSegmentType.WORK,
            started_at=now,
        )
    )
    db.flush()
    db.refresh(live, attribute_names=["segments"])
    _recalculate_totals(live, now)
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_attendance.clock_in",
        entity_type="staff_attendance",
        entity_id=str(live.id),
        new_value={"work_date": today.isoformat()},
        **(meta or {}),
    )
    return live


def pause(db: Session, user: User, meta: dict | None = None) -> StaffAttendance:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    live = _get_live_attendance(db, user.id, today, for_update=True)
    if not live or live.status != StaffAttendanceStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Clock in first to pause your session.")
    if live.is_paused:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your session is already paused.")

    now = _utc_now()
    open_seg = _open_segment(live)
    if not open_seg or open_seg.segment_type != StaffAttendanceSegmentType.WORK:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active work segment to pause.")
    open_seg.ended_at = now
    db.add(
        StaffAttendanceSegment(
            attendance_id=live.id,
            segment_type=StaffAttendanceSegmentType.BREAK,
            started_at=now,
        )
    )
    live.is_paused = True
    db.flush()
    db.refresh(live, attribute_names=["segments"])
    _recalculate_totals(live, now)
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_attendance.pause",
        entity_type="staff_attendance",
        entity_id=str(live.id),
        **(meta or {}),
    )
    return live


def resume(db: Session, user: User, meta: dict | None = None) -> StaffAttendance:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    live = _get_live_attendance(db, user.id, today, for_update=True)
    if not live or live.status != StaffAttendanceStatus.IN_PROGRESS or not live.is_paused:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your session is not paused.")

    now = _utc_now()
    open_seg = _open_segment(live)
    if not open_seg or open_seg.segment_type != StaffAttendanceSegmentType.BREAK:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active break to resume from.")
    open_seg.ended_at = now
    db.add(
        StaffAttendanceSegment(
            attendance_id=live.id,
            segment_type=StaffAttendanceSegmentType.WORK,
            started_at=now,
        )
    )
    live.is_paused = False
    db.flush()
    db.refresh(live, attribute_names=["segments"])
    _recalculate_totals(live, now)
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_attendance.resume",
        entity_type="staff_attendance",
        entity_id=str(live.id),
        **(meta or {}),
    )
    return live


def save_work_summary(db: Session, user: User, work_summary: str, meta: dict | None = None) -> StaffAttendance:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    live = _get_live_attendance(db, user.id, today, for_update=True)
    if not live:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Clock in first to save your work log.")
    live.work_summary = _validate_work_summary(work_summary)
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_attendance.save_summary",
        entity_type="staff_attendance",
        entity_id=str(live.id),
        new_value={"work_summary_len": len(live.work_summary)},
        **(meta or {}),
    )
    return live


def clock_out(db: Session, user: User, work_summary: str | None = None, meta: dict | None = None) -> StaffAttendance:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    live = _get_live_attendance(db, user.id, today, for_update=True)
    if not live or live.status != StaffAttendanceStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are not clocked in.")

    if work_summary is not None:
        live.work_summary = _validate_work_summary(work_summary)
    elif not (live.work_summary or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Let's add a few words about what you worked on before clocking out.",
        )

    now = _utc_now()
    open_seg = _open_segment(live)
    if open_seg:
        open_seg.ended_at = now
    live.status = StaffAttendanceStatus.COMPLETED
    live.is_paused = False
    db.flush()
    db.refresh(live, attribute_names=["segments"])
    _recalculate_totals(live, now)
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_attendance.clock_out",
        entity_type="staff_attendance",
        entity_id=str(live.id),
        **(meta or {}),
    )
    return live


def create_forgot_log(
    db: Session,
    user: User,
    *,
    work_date: date,
    start_at: datetime,
    end_at: datetime,
    work_summary: str,
    reason: str,
    meta: dict | None = None,
) -> StaffAttendance:
    assert_staff_attendance_eligible(user)
    today = today_ist()
    earliest = today - timedelta(days=FORGOT_LOOKBACK_DAYS)
    if work_date < earliest or work_date > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forgot-to-log is available for today and yesterday only.",
        )
    if _has_approved_leave(db, user.id, work_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This date has approved leave — use live attendance instead.",
        )

    start_utc = ensure_utc_aware(start_at)
    end_utc = ensure_utc_aware(end_at)
    if not start_utc or not end_utc or end_utc <= start_utc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time should be after start time.")

    existing_live = db.scalars(
        select(StaffAttendance).where(
            StaffAttendance.user_id == user.id,
            StaffAttendance.work_date == work_date,
            StaffAttendance.entry_type == StaffAttendanceEntryType.LIVE,
        )
    ).first()
    if existing_live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a live attendance record for this date.",
        )

    existing_forgot = db.scalars(
        select(StaffAttendance).where(
            StaffAttendance.user_id == user.id,
            StaffAttendance.work_date == work_date,
            StaffAttendance.entry_type == StaffAttendanceEntryType.FORGOT,
        )
    ).first()
    if existing_forgot:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A forgot-to-log entry already exists for this date.")

    summary = _validate_work_summary(work_summary)
    forgot_reason = (reason or "").strip()
    if len(forgot_reason) < MIN_WORK_SUMMARY_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please share a short reason for the late log.",
        )

    duration = max(0, int((end_utc - start_utc).total_seconds()))
    row = StaffAttendance(
        user_id=user.id,
        work_date=work_date,
        entry_type=StaffAttendanceEntryType.FORGOT,
        status=StaffAttendanceStatus.COMPLETED,
        work_summary=summary,
        forgot_reason=forgot_reason,
        manual_start_at=start_utc,
        manual_end_at=end_utc,
        total_work_seconds=duration,
        total_break_seconds=0,
        is_paused=False,
    )
    db.add(row)
    db.flush()
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_attendance.forgot_log",
        entity_type="staff_attendance",
        entity_id=str(row.id),
        new_value={"work_date": work_date.isoformat()},
        **(meta or {}),
    )
    return row


def list_user_attendance(
    db: Session,
    user_id: int,
    *,
    filter_kind: str = "all",
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    items: list[dict] = []
    if filter_kind in ("all", "completed_logs", "forgot_to_log"):
        stmt = (
            select(StaffAttendance)
            .where(StaffAttendance.user_id == user_id)
            .options(selectinload(StaffAttendance.segments))
            .order_by(StaffAttendance.work_date.desc(), StaffAttendance.id.desc())
        )
        if filter_kind == "completed_logs":
            stmt = stmt.where(
                StaffAttendance.status.in_([StaffAttendanceStatus.COMPLETED, StaffAttendanceStatus.AUTO_CLOSED]),
                StaffAttendance.work_summary.is_not(None),
            )
        elif filter_kind == "forgot_to_log":
            stmt = stmt.where(StaffAttendance.entry_type == StaffAttendanceEntryType.FORGOT)

        if search:
            q = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    StaffAttendance.work_summary.ilike(q),
                    StaffAttendance.forgot_reason.ilike(q),
                )
            )
        rows = db.scalars(stmt).all()
        items.extend(serialize_attendance(r, db) for r in rows)

    if filter_kind in ("all", "leaves"):
        leave_stmt = (
            select(StaffLeave)
            .where(StaffLeave.staff_user_id == user_id)
            .order_by(StaffLeave.leave_date.desc(), StaffLeave.id.desc())
        )
        if search:
            q = f"%{search.strip()}%"
            leave_stmt = leave_stmt.where(or_(StaffLeave.reason.ilike(q)))
        for leave in db.scalars(leave_stmt).all():
            items.append(
                {
                    "id": leave.id,
                    "user_id": leave.staff_user_id,
                    "work_date": leave.leave_date.isoformat(),
                    "day_name": leave.leave_date.strftime("%A"),
                    "entry_type": "LEAVE",
                    "status": leave.status.value,
                    "work_summary": leave.reason,
                    "forgot_reason": None,
                    "total_work_seconds": None,
                    "total_break_seconds": None,
                    "is_paused": False,
                    "auto_closed": False,
                    "clock_in_at": None,
                    "clock_out_at": None,
                    "created_at": leave.created_at.isoformat() if leave.created_at else None,
                    "updated_at": leave.updated_at.isoformat() if leave.updated_at else None,
                    "record_kind": "leave",
                }
            )

    items.sort(key=lambda x: (x.get("work_date") or "", x.get("id") or 0), reverse=True)
    total = len(items)
    page = items[offset : offset + limit]
    return page, total


def hr_update_attendance(
    db: Session,
    actor: User,
    attendance_id: int,
    *,
    work_summary: str | None = None,
    manual_start_at: datetime | None = None,
    manual_end_at: datetime | None = None,
    meta: dict | None = None,
) -> StaffAttendance:
    row = db.scalars(
        select(StaffAttendance)
        .where(StaffAttendance.id == attendance_id)
        .options(selectinload(StaffAttendance.segments))
        .with_for_update()
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found.")

    old = serialize_attendance(row, db)
    if work_summary is not None:
        row.work_summary = _validate_work_summary(work_summary)
    if row.entry_type == StaffAttendanceEntryType.FORGOT:
        if manual_start_at is not None:
            row.manual_start_at = ensure_utc_aware(manual_start_at)
        if manual_end_at is not None:
            row.manual_end_at = ensure_utc_aware(manual_end_at)
        if row.manual_start_at and row.manual_end_at:
            row.total_work_seconds = max(
                0,
                int((row.manual_end_at - row.manual_start_at).total_seconds()),
            )

    db.flush()
    _recalculate_totals(row)
    log_audit(
        db,
        actor_user_id=actor.id,
        action="staff_attendance.hr_update",
        entity_type="staff_attendance",
        entity_id=str(row.id),
        old_value=str(old),
        new_value=str(serialize_attendance(row, db)),
        **(meta or {}),
    )
    return row


def auto_close_open_attendance_at_midnight(db: Session, now_ist_dt: datetime | None = None) -> list[int]:
    """Close IN_PROGRESS staff attendance for the IST day that just ended."""
    now_ist_dt = now_ist_dt or now_ist()
    if now_ist_dt.tzinfo is None:
        now_ist_dt = now_ist_dt.replace(tzinfo=IST)
    else:
        now_ist_dt = now_ist_dt.astimezone(IST)

    closing_date = now_ist_dt.date() - timedelta(days=1)

    rows = list(
        db.scalars(
            select(StaffAttendance)
            .where(
                StaffAttendance.status == StaffAttendanceStatus.IN_PROGRESS,
                StaffAttendance.entry_type == StaffAttendanceEntryType.LIVE,
                StaffAttendance.work_date <= closing_date,
            )
            .options(selectinload(StaffAttendance.segments))
            .with_for_update(skip_locked=True)
        ).all()
    )

    closed_ids: list[int] = []
    for row in rows:
        day_end_ist = datetime.combine(row.work_date + timedelta(days=1), datetime.min.time(), tzinfo=IST)
        end_utc = day_end_ist.astimezone(timezone.utc)
        open_seg = _open_segment(row)
        if open_seg:
            open_seg.ended_at = end_utc
        row.status = StaffAttendanceStatus.AUTO_CLOSED
        row.is_paused = False
        row.auto_closed = True
        _recalculate_totals(row, end_utc)
        closed_ids.append(row.id)

    return closed_ids
