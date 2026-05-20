from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.services.parent_service import PARENT_VISIBLE


def _has_review(log: DailyLog) -> bool:
    return log.parent_session_rating is not None or bool(log.parent_feedback)


def list_therapist_reviews(
    db: Session,
    therapist_user_id: int,
    *,
    public_only: bool = False,
) -> list[dict]:
    stmt = (
        select(DailyLog)
        .join(TherapySession)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            DailyLog.submitted_at.isnot(None),
            DailyLog.approval_status == LogApprovalStatus.APPROVED,
            DailyLog.visibility_status.in_(PARENT_VISIBLE),
        )
        .options(
            selectinload(DailyLog.session).selectinload(TherapySession.case).selectinload(Case.child),
        )
        .order_by(DailyLog.parent_feedback_at.desc().nullslast(), DailyLog.submitted_at.desc())
    )
    logs = db.scalars(stmt).all()
    out: list[dict] = []
    for log in logs:
        if not _has_review(log):
            continue
        if public_only and not log.parent_feedback_public:
            continue
        s = log.session
        case = s.case if s else None
        child = case.child if case else None
        child_name = child.full_name if child else None
        scheduled: Optional[date] = s.scheduled_date if s else None
        out.append(
            {
                "id": log.id,
                "rating": log.parent_session_rating,
                "feedback": log.parent_feedback,
                "feedback_at": log.parent_feedback_at,
                "is_public": bool(log.parent_feedback_public),
                "scheduled_date": scheduled,
                "child_name": child_name,
                "case_code": case.case_code if case else None,
            }
        )
    return out


def review_summary(db: Session, therapist_user_id: int) -> dict:
    reviews = list_therapist_reviews(db, therapist_user_id)
    public_reviews = [r for r in reviews if r["is_public"]]
    ratings = [r["rating"] for r in reviews if r["rating"] is not None]
    public_ratings = [r["rating"] for r in public_reviews if r["rating"] is not None]

    def avg(nums: list[int]) -> Optional[float]:
        if not nums:
            return None
        return round(sum(nums) / len(nums), 1)

    return {
        "total_count": len(reviews),
        "public_count": len(public_reviews),
        "average_rating": avg(ratings),
        "public_average_rating": avg(public_ratings),
    }
