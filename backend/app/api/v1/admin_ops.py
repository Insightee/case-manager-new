"""Staff read-only operations snapshot. No writes, escalations, or notifications."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import RoleName, user_has_permission
from app.models.user import User
from app.services.ops_daily_snapshot_service import build_daily_snapshot

router = APIRouter(prefix="/admin/ops", tags=["admin-ops"])


def _ops_reader(user: User = Depends(get_current_user)) -> User:
    """Same staff gate as other admin dashboard reads."""
    roles = set(user.role_names or [])
    if RoleName.SPOT.value in roles:
        return user
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


@router.get("/daily-snapshot")
def daily_snapshot(
    day: str = Query(..., alias="date", description="Asia/Kolkata calendar day, YYYY-MM-DD"),
    _user: User = Depends(_ops_reader),
    db: Session = Depends(get_db),
):
    """End-of-day ops counts for one IST date.

    The window is ``[midnight IST, next midnight IST)``. Calling this after the
    day has ended returns ticket status, incident status, and session-log
    approval as of that exclusive end — not the live row. The handler does not
    commit, escalate incidents, auto-end sessions, or notify anyone.

    Response (staff names and case codes only; no child names, contacts,
    clinical text, bank details, or attachment contents):

    - ``sessions.by_status`` — sessions scheduled that day that already existed
    - ``session_logs`` — approval buckets for sessions that were completed as of
      day end, plus ``nothing_submitted_at_eod`` and ``still_missing_at_eod``
    - ``tickets`` — not-closed status split, unassigned, assignee names,
      created that day, closed after day end
    - ``incidents.not_closed_by_status`` — full open-status split
    - ``child_absence_pending`` — child-absence requests still pending
    - ``leave_pending`` — count and therapist names
    - ``billing_change_approvals_pending`` — count and case codes
    - ``cases_created`` — case codes created that day
    - ``active_cases_without_submitted_log`` — active cases with no submitted
      log on sessions scheduled in the 5 IST days ending that date
    """
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Looks like we still need a valid date (YYYY-MM-DD) before we can build this snapshot.",
        ) from None
    return build_daily_snapshot(db, parsed)
