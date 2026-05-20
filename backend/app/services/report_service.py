from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.module_access import get_allowed_case_product_modules
from app.core.pagination import paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.models.case import Case
from app.models.report import MonthlyReport, ParentReviewStatus, ReportStatus
from app.models.review import Review, ReviewDecision
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import parent_service


def list_monthly_reports(
    db: Session,
    user: User,
    *,
    status: ReportStatus | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[MonthlyReport], dict]:
    stmt = select(MonthlyReport).join(Case, MonthlyReport.case_id == Case.id).order_by(
        MonthlyReport.created_at.desc()
    )
    if status:
        stmt = stmt.where(MonthlyReport.status == status)
    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(MonthlyReport.therapist_user_id == user.id)
    allowed = get_allowed_case_product_modules(user)
    if allowed is not None and allowed:
        stmt = stmt.where(Case.product_module.in_(allowed))
    elif allowed is not None and not allowed:
        stmt = stmt.where(MonthlyReport.id < 0)

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    scoped = [r for r in rows if case_scope_check(db, user, db.get(Case, r.case_id))]
    meta = paginated_response([], total, page, page_size)
    meta["total"] = len(scoped)  # approximate when post-filter shrinks page
    return scoped, meta


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
        vis = visibility or VisibilityStatus.APPROVED_FOR_PARENT
        report.visibility_status = vis
        if vis in parent_service.PARENT_VISIBLE:
            report.parent_review_status = ParentReviewStatus.PENDING.value
    else:
        report.status = ReportStatus.REJECTED
        report.reviewer_comment = comment
    db.flush()
    return report
