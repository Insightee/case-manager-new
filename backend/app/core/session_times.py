"""Effective session clock times for billing and family-facing display."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from app.models.daily_log import LogApprovalStatus

if TYPE_CHECKING:
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession


def effective_session_datetimes(
    session: TherapySession,
    log: Optional[DailyLog] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Return billable/display times: approved edits when present, else clock record."""
    edited_start = getattr(session, "edited_start_at", None)
    edited_end = getattr(session, "edited_end_at", None)
    if (
        log is not None
        and log.approval_status == LogApprovalStatus.APPROVED
        and edited_start is not None
        and edited_end is not None
    ):
        return edited_start, edited_end
    return session.actual_start_at, session.actual_end_at
