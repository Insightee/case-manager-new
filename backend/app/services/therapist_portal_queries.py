"""Bounded SQL helpers for therapist portal home/workspace/pipeline APIs."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import get_allowed_case_product_modules
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User

UPCOMING_LIMIT = 50
NEEDS_LOG_LIMIT = 50
HOME_UPCOMING_CAP = 10
HOME_NEEDS_LOG_CAP = 10
SLOT_FORWARD_DAYS = 90

ACTIVE_REPORT_STATUSES = (
    ReportStatus.DRAFT,
    ReportStatus.UNDER_REVIEW,
    ReportStatus.REJECTED,
)


def current_month_label() -> str:
    return date.today().strftime("%b %Y")


def assigned_cases(db: Session, user: User) -> list[Case]:
    """Active therapist assignments; product-module filter only (no per-case scope N+1)."""
    allowed = get_allowed_case_product_modules(user)
    if allowed is not None and not allowed:
        return []
    stmt = (
        select(Case)
        .join(
            CaseAssignment,
            (CaseAssignment.case_id == Case.id)
            & (CaseAssignment.therapist_user_id == user.id)
            & (CaseAssignment.status == CaseAssignmentStatus.ACTIVE),
        )
        .options(selectinload(Case.child))
        .distinct()
        .order_by(Case.case_code)
    )
    if allowed is not None:
        stmt = stmt.where(Case.product_module.in_(allowed))
    return list(db.scalars(stmt).all())


def _session_options():
    return (
        selectinload(TherapySession.daily_log),
        selectinload(TherapySession.case).selectinload(Case.child),
    )


def fetch_calendar_sessions(
    db: Session,
    therapist_user_id: int,
    from_date: date,
    to_date: date,
    *,
    case_id: int | None = None,
) -> list[TherapySession]:
    """Scheduled / in-progress visits for calendar overlay (not slot inventory)."""
    stmt = (
        select(TherapySession)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date >= from_date,
            TherapySession.scheduled_date <= to_date,
            TherapySession.status.in_((SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS)),
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date.asc(), TherapySession.start_time.asc())
    )
    if case_id is not None:
        stmt = stmt.where(TherapySession.case_id == case_id)
    return list(db.scalars(stmt).all())


def fetch_upcoming_sessions(
    db: Session,
    user: User,
    case_ids: list[int],
    *,
    days: int = 7,
    limit: int = UPCOMING_LIMIT,
) -> list[TherapySession]:
    if not case_ids:
        return []
    today = date.today()
    end = today + timedelta(days=days)
    return list(
        db.scalars(
            select(TherapySession)
            .where(
                TherapySession.therapist_user_id == user.id,
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.SCHEDULED,
                TherapySession.scheduled_date >= today,
                TherapySession.scheduled_date <= end,
            )
            .options(*_session_options())
            .order_by(TherapySession.scheduled_date.asc(), TherapySession.start_time.asc())
            .limit(limit)
        ).all()
    )


def fetch_needs_log_sessions(
    db: Session,
    user: User,
    case_ids: list[int],
    *,
    limit: int = NEEDS_LOG_LIMIT,
) -> list[TherapySession]:
    if not case_ids:
        return []
    return list(
        db.scalars(
            select(TherapySession)
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id == user.id,
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.COMPLETED,
                DailyLog.id.is_(None),
            )
            .options(*_session_options())
            .order_by(TherapySession.scheduled_date.desc(), TherapySession.id.desc())
            .limit(limit)
        ).all()
    )


def needs_log_count_by_case(db: Session, user: User, case_ids: list[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    rows = db.execute(
        select(TherapySession.case_id, func.count(TherapySession.id))
        .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id == user.id,
            TherapySession.case_id.in_(case_ids),
            TherapySession.status == SessionStatus.COMPLETED,
            DailyLog.id.is_(None),
        )
        .group_by(TherapySession.case_id)
    ).all()
    return {int(cid): int(cnt) for cid, cnt in rows}


def upcoming_count_by_case(
    db: Session, user: User, case_ids: list[int], *, days: int = 7
) -> dict[int, int]:
    if not case_ids:
        return {}
    today = date.today()
    end = today + timedelta(days=days)
    rows = db.execute(
        select(TherapySession.case_id, func.count(TherapySession.id))
        .where(
            TherapySession.therapist_user_id == user.id,
            TherapySession.case_id.in_(case_ids),
            TherapySession.status == SessionStatus.SCHEDULED,
            TherapySession.scheduled_date >= today,
            TherapySession.scheduled_date <= end,
        )
        .group_by(TherapySession.case_id)
    ).all()
    return {int(cid): int(cnt) for cid, cnt in rows}


def fetch_home_reports(
    db: Session, user: User, case_ids: list[int], month_label: str
) -> list[MonthlyReport]:
    if not case_ids:
        return []
    return list(
        db.scalars(
            select(MonthlyReport)
            .where(
                MonthlyReport.therapist_user_id == user.id,
                MonthlyReport.case_id.in_(case_ids),
                or_(
                    MonthlyReport.status.in_(ACTIVE_REPORT_STATUSES),
                    and_(
                        MonthlyReport.status == ReportStatus.PUBLISHED,
                        MonthlyReport.month == month_label,
                    ),
                ),
            )
            .order_by(MonthlyReport.updated_at.desc())
        ).all()
    )


def fetch_pipeline_reports(
    db: Session, user: User, case_ids: list[int], month_label: str
) -> list[MonthlyReport]:
    return fetch_home_reports(db, user, case_ids, month_label)


def case_ids_with_report_month(
    db: Session, user: User, case_ids: list[int], month_label: str
) -> set[int]:
    if not case_ids:
        return set()
    rows = db.scalars(
        select(MonthlyReport.case_id)
        .where(
            MonthlyReport.therapist_user_id == user.id,
            MonthlyReport.case_id.in_(case_ids),
            MonthlyReport.month == month_label,
        )
        .distinct()
    ).all()
    return {int(r) for r in rows}


def count_pending_log_approvals(db: Session, user: User, case_ids: list[int]) -> int:
    if not case_ids:
        return 0
    return int(
        db.scalar(
            select(func.count(DailyLog.id))
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id == user.id,
                TherapySession.case_id.in_(case_ids),
                DailyLog.approval_status == LogApprovalStatus.PENDING,
            )
        )
        or 0
    )


def count_reports_by_status(
    db: Session, user: User, case_ids: list[int]
) -> tuple[int, int]:
    """Returns (draft_or_rejected_count, under_review_count)."""
    if not case_ids:
        return 0, 0
    draft_rej = int(
        db.scalar(
            select(func.count(MonthlyReport.id)).where(
                MonthlyReport.therapist_user_id == user.id,
                MonthlyReport.case_id.in_(case_ids),
                MonthlyReport.status.in_((ReportStatus.DRAFT, ReportStatus.REJECTED)),
            )
        )
        or 0
    )
    under = int(
        db.scalar(
            select(func.count(MonthlyReport.id)).where(
                MonthlyReport.therapist_user_id == user.id,
                MonthlyReport.case_id.in_(case_ids),
                MonthlyReport.status == ReportStatus.UNDER_REVIEW,
            )
        )
        or 0
    )
    return draft_rej, under


def fetch_booked_slots(
    db: Session, user: User, *, from_date: date, to_date: date
) -> list[TherapistSlot]:
    return list(
        db.scalars(
            select(TherapistSlot)
            .where(
                TherapistSlot.therapist_user_id == user.id,
                TherapistSlot.slot_date >= from_date,
                TherapistSlot.slot_date <= to_date,
                TherapistSlot.status == SlotStatus.BOOKED,
            )
            .order_by(TherapistSlot.slot_date, TherapistSlot.start_time)
        ).all()
    )
