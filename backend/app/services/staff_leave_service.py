"""Staff leave requests — full-day, free-text reason, HR approval."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.timezone import today_ist
from app.models.leave import LeaveStatus
from app.models.staff_leave import StaffLeave
from app.models.user import User
from app.services.staff_attendance_access import assert_staff_attendance_eligible, can_manage_staff_attendance


def serialize_staff_leave(row: StaffLeave, db: Session) -> dict:
    staff = db.get(User, row.staff_user_id)
    reviewer = db.get(User, row.reviewed_by_user_id) if row.reviewed_by_user_id else None
    return {
        "id": row.id,
        "staff_user_id": row.staff_user_id,
        "staff_name": staff.full_name if staff else None,
        "leave_date": row.leave_date.isoformat(),
        "day_name": row.leave_date.strftime("%A"),
        "reason": row.reason,
        "status": row.status.value,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "reviewer_name": reviewer.full_name if reviewer else None,
        "review_note": row.review_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_staff_leave(db: Session, user: User, *, leave_date: date, reason: str, meta: dict | None = None) -> StaffLeave:
    assert_staff_attendance_eligible(user)
    cleaned = (reason or "").strip()
    if len(cleaned) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please add a short reason for your leave request.",
        )

    existing = db.scalars(
        select(StaffLeave).where(
            StaffLeave.staff_user_id == user.id,
            StaffLeave.leave_date == leave_date,
            StaffLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a leave request for this date.",
        )

    row = StaffLeave(
        staff_user_id=user.id,
        leave_date=leave_date,
        reason=cleaned,
        status=LeaveStatus.PENDING,
    )
    db.add(row)
    db.flush()
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_leave.create",
        entity_type="staff_leave",
        entity_id=str(row.id),
        new_value={"leave_date": leave_date.isoformat()},
        **(meta or {}),
    )
    return row


def list_staff_leaves_for_user(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(StaffLeave)
        .where(StaffLeave.staff_user_id == user_id)
        .order_by(StaffLeave.leave_date.desc(), StaffLeave.id.desc())
    ).all()
    return [serialize_staff_leave(r, db) for r in rows]


def list_staff_leaves_admin(
    db: Session,
    *,
    status_filter: str = "PENDING",
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int, dict[str, int]]:
    stmt = select(StaffLeave).order_by(StaffLeave.leave_date.desc(), StaffLeave.id.desc())
    if status_filter and status_filter.upper() != "ALL":
        try:
            status_enum = LeaveStatus(status_filter.upper())
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter.") from exc
        stmt = stmt.where(StaffLeave.status == status_enum)

    if search and len(search.strip()) >= 2:
        q = f"%{search.strip()}%"
        stmt = stmt.join(User, User.id == StaffLeave.staff_user_id).where(
            or_(User.full_name.ilike(q), User.email.ilike(q), StaffLeave.reason.ilike(q))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()

    counts_rows = db.execute(select(StaffLeave.status, func.count()).group_by(StaffLeave.status)).all()
    counts = {s.value: int(c) for s, c in counts_rows}
    for key in ("PENDING", "APPROVED", "REJECTED", "CANCELLED"):
        counts.setdefault(key, 0)
    counts["ALL"] = sum(counts.get(k, 0) for k in ("PENDING", "APPROVED", "REJECTED", "CANCELLED"))

    return [serialize_staff_leave(r, db) for r in rows], int(total), counts


def review_staff_leave(
    db: Session,
    actor: User,
    leave_id: int,
    *,
    status: LeaveStatus,
    review_note: str | None = None,
    meta: dict | None = None,
) -> StaffLeave:
    if not can_manage_staff_attendance(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to review staff leave.")

    row = db.get(StaffLeave, leave_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found.")
    if row.status != LeaveStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This leave request was already reviewed.")

    if status not in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use APPROVED or REJECTED.")

    row.status = status
    row.reviewed_by_user_id = actor.id
    row.review_note = (review_note or "").strip() or None
    log_audit(
        db,
        actor_user_id=actor.id,
        action=f"staff_leave.{status.value.lower()}",
        entity_type="staff_leave",
        entity_id=str(row.id),
        new_value={"status": status.value},
        **(meta or {}),
    )
    return row


def cancel_staff_leave(db: Session, user: User, leave_id: int, meta: dict | None = None) -> StaffLeave:
    row = db.get(StaffLeave, leave_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found.")
    if row.staff_user_id != user.id and not can_manage_staff_attendance(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")
    if row.status != LeaveStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending leave can be cancelled.")

    row.status = LeaveStatus.CANCELLED
    log_audit(
        db,
        actor_user_id=user.id,
        action="staff_leave.cancel",
        entity_type="staff_leave",
        entity_id=str(row.id),
        **(meta or {}),
    )
    return row
