"""Shared session status / flag filters for admin session analytics and exports."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import String, cast, exists, func, or_, select

from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.support_ticket import SupportTicket, TicketStatus

FLAGGED_STATUS = "FLAGGED"


def session_flagged_clause():
    """Sessions with data-quality flags, edited times, or an open flag ticket."""
    open_flag_ticket = exists(
        select(SupportTicket.id).where(
            SupportTicket.case_id == TherapySession.case_id,
            SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
            SupportTicket.subject.like(
                func.concat("Session #", cast(TherapySession.id, String), " flagged%"),
            ),
        ),
    )
    return or_(
        TherapySession.data_quality_flag.isnot(None),
        TherapySession.data_quality_flag != "",
        TherapySession.actual_times_edited.is_(True),
        open_flag_ticket,
    )


def session_status_filter_clause(session_status: Optional[str]):
    if not session_status:
        return None
    if session_status == FLAGGED_STATUS:
        return session_flagged_clause()
    try:
        return TherapySession.status == SessionStatus(session_status)
    except ValueError:
        return None


def append_session_status_filter(base_filters: list, session_status: Optional[str]) -> None:
    clause = session_status_filter_clause(session_status)
    if clause is not None:
        base_filters.append(clause)
