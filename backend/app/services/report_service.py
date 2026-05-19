from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.report import MonthlyReport, ReportStatus
from app.models.review import Review, ReviewDecision
from app.models.visibility import VisibilityStatus


def list_monthly_reports(db: Session, status: ReportStatus | None = None) -> list[MonthlyReport]:
    stmt = select(MonthlyReport).options(selectinload(MonthlyReport))
    if status:
        stmt = stmt.where(MonthlyReport.status == status)
    return list(db.scalars(stmt.order_by(MonthlyReport.created_at.desc())).all())


def review_monthly_report(
    db: Session,
    report: MonthlyReport,
    reviewer_user_id: int,
    decision: ReviewDecision,
    comment: str | None,
    visibility: VisibilityStatus | None,
) -> MonthlyReport:
    review = Review(
        entity_type="monthly_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=decision,
        comment=comment,
    )
    db.add(review)
    if decision == ReviewDecision.APPROVE:
        report.status = ReportStatus.PUBLISHED
        report.visibility_status = visibility or VisibilityStatus.APPROVED_FOR_PARENT
    else:
        report.status = ReportStatus.REJECTED
        report.reviewer_comment = comment
    db.flush()
    return report
