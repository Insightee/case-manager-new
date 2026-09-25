from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.database import get_db
from app.models.leave import LeaveStatus
from app.models.user import User
from app.services.staff_attendance_access import (
    assert_can_view_user_attendance,
    can_manage_staff_attendance,
)
from app.services import staff_attendance_service as attendance_svc
from app.services import staff_leave_service as leave_svc

router = APIRouter(prefix="/staff-attendance", tags=["staff-attendance"])


class WorkSummaryUpdate(BaseModel):
    work_summary: str = Field(..., min_length=1)


class ClockOutBody(BaseModel):
    work_summary: Optional[str] = None


class ForgotLogCreate(BaseModel):
    work_date: date
    start_at: datetime
    end_at: datetime
    work_summary: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class HrAttendanceUpdate(BaseModel):
    work_summary: Optional[str] = None
    manual_start_at: Optional[datetime] = None
    manual_end_at: Optional[datetime] = None


class StaffLeaveCreate(BaseModel):
    leave_date: date
    reason: str = Field(..., min_length=1)


class StaffLeaveReview(BaseModel):
    status: LeaveStatus
    review_note: Optional[str] = None


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    mins = seconds // 60
    hours = mins // 60
    rem = mins % 60
    return f"{hours}h {rem}m"


@router.get("/me/today")
def get_my_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return attendance_svc.get_today_state(db, user)


@router.post("/clock-in")
def clock_in(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    row = attendance_svc.clock_in(db, user, meta)
    db.commit()
    return attendance_svc.serialize_attendance(row, db)


@router.post("/pause")
def pause(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Breaks are no longer tracked. Clock out when you finish, and clock in again when you return.",
    )


@router.post("/resume")
def resume(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Breaks are no longer tracked. Clock out when you finish, and clock in again when you return.",
    )


@router.put("/work-summary")
def save_work_summary(
    body: WorkSummaryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    row = attendance_svc.save_work_summary(db, user, body.work_summary, meta)
    db.commit()
    return attendance_svc.serialize_attendance(row, db)


@router.post("/clock-out")
def clock_out(
    body: ClockOutBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    row = attendance_svc.clock_out(db, user, body.work_summary, meta)
    db.commit()
    return attendance_svc.serialize_attendance(row, db)


@router.post("/forgot")
def forgot_log(
    body: ForgotLogCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del body  # retained for OpenAPI schema compatibility
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forgot-to-log is not available for staff. Contact HR if you need a correction.",
    )


@router.get("/me")
def list_my_attendance(
    filter: str = Query("all", alias="filter"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_can_view_user_attendance(user, user.id)
    items, total = attendance_svc.list_user_attendance(
        db, user.id, filter_kind=filter, search=search, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.get("/users/{user_id}")
def list_user_attendance(
    user_id: int,
    filter: str = Query("all", alias="filter"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_can_view_user_attendance(user, user_id)
    items, total = attendance_svc.list_user_attendance(
        db, user_id, filter_kind=filter, search=search, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.get("/users/{user_id}/export")
def export_user_attendance_csv(
    user_id: int,
    filter: str = Query("all", alias="filter"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_can_view_user_attendance(user, user_id)
    items, _ = attendance_svc.list_user_attendance(db, user_id, filter_kind=filter, search=search, limit=5000, offset=0)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Date",
            "Day",
            "Type",
            "Status",
            "Clock in",
            "Clock out",
            "Total time",
            "Summary",
        ]
    )
    for row in items:
        writer.writerow(
            [
                row.get("work_date"),
                row.get("day_name"),
                row.get("entry_type"),
                row.get("status"),
                row.get("clock_in_at"),
                row.get("clock_out_at"),
                _format_duration(row.get("total_work_seconds")),
                row.get("work_summary") or "",
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="staff-attendance-{user_id}.csv"'},
    )


@router.patch("/records/{attendance_id}")
def hr_update_attendance(
    attendance_id: int,
    body: HrAttendanceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    if not can_manage_staff_attendance(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit attendance.")
    row = attendance_svc.hr_update_attendance(
        db,
        user,
        attendance_id,
        work_summary=body.work_summary,
        manual_start_at=body.manual_start_at,
        manual_end_at=body.manual_end_at,
        meta=meta,
    )
    db.commit()
    return attendance_svc.serialize_attendance(row, db)


@router.post("/leaves")
def create_staff_leave(
    body: StaffLeaveCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    row = leave_svc.create_staff_leave(db, user, leave_date=body.leave_date, reason=body.reason, meta=meta)
    db.commit()
    return leave_svc.serialize_staff_leave(row, db)


@router.get("/me/leave-balance")
def my_staff_leave_balance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services.staff_attendance_access import assert_staff_attendance_eligible
    from app.services import staff_employment_service as employment

    assert_staff_attendance_eligible(user)
    return employment.staff_leave_balance_summary(db, user)


@router.get("/leaves/me")
def list_my_staff_leaves(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services.staff_attendance_access import assert_staff_attendance_eligible

    assert_staff_attendance_eligible(user)
    return leave_svc.list_staff_leaves_for_user(db, user.id)


@router.get("/leaves")
def list_staff_leaves_admin(
    status: str = Query("PENDING"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not can_manage_staff_attendance(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed.")
    items, total, counts = leave_svc.list_staff_leaves_admin(
        db, status_filter=status, search=search, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "status_counts": counts}


@router.patch("/leaves/{leave_id}")
def review_staff_leave(
    leave_id: int,
    body: StaffLeaveReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    row = leave_svc.review_staff_leave(
        db, user, leave_id, status=body.status, review_note=body.review_note, meta=meta
    )
    db.commit()
    return leave_svc.serialize_staff_leave(row, db)


@router.delete("/leaves/{leave_id}")
def cancel_staff_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    meta: dict = Depends(get_request_meta),
):
    row = leave_svc.cancel_staff_leave(db, user, leave_id, meta)
    db.commit()
    return leave_svc.serialize_staff_leave(row, db)
