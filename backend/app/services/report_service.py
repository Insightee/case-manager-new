from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.module_access import get_allowed_case_product_modules
from app.core.pagination import paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.models.case import Case
from app.models.child import Child
from app.models.report import MonthlyReport, ObservationReport, ParentReviewStatus, ReportStatus
from app.models.review import Review, ReviewDecision
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import parent_service


def list_monthly_reports(
    db: Session,
    user: User,
    *,
    status: ReportStatus | None = None,
    case_id: int | None = None,
    month: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    skip_scope_filter: bool = False,
) -> tuple[list[MonthlyReport], dict]:
    stmt = select(MonthlyReport).join(Case, MonthlyReport.case_id == Case.id).order_by(
        MonthlyReport.updated_at.desc().nullslast(),
        MonthlyReport.created_at.desc(),
    )
    if status:
        stmt = stmt.where(MonthlyReport.status == status)
    if case_id is not None:
        stmt = stmt.where(MonthlyReport.case_id == case_id)
    if month:
        stmt = stmt.where(MonthlyReport.month.ilike(f"%{month.strip()}%"))
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.join(Child, Case.child_id == Child.id).where(
            or_(
                Case.case_code.ilike(q),
                Child.first_name.ilike(q),
                Child.last_name.ilike(q),
                MonthlyReport.month.ilike(q),
                MonthlyReport.summary.ilike(q),
            )
        )
    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(MonthlyReport.therapist_user_id == user.id)
    allowed = get_allowed_case_product_modules(user)
    if allowed is not None and allowed:
        stmt = stmt.where(Case.product_module.in_(allowed))
    elif allowed is not None and not allowed:
        stmt = stmt.where(MonthlyReport.id < 0)

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    if skip_scope_filter:
        return rows, paginated_response(rows, total, page, page_size)
    scoped = [r for r in rows if case_scope_check(db, user, db.get(Case, r.case_id))]
    meta = paginated_response(scoped, total, page, page_size)
    if len(scoped) != len(rows):
        meta["total"] = len(scoped)
    return scoped, meta


def list_observation_reports(
    db: Session,
    user: User,
    *,
    status: ReportStatus | None = None,
    case_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ObservationReport], dict]:
    stmt = select(ObservationReport).join(Case, ObservationReport.case_id == Case.id).order_by(
        ObservationReport.created_at.desc()
    )
    if status:
        stmt = stmt.where(ObservationReport.status == status)
    if case_id is not None:
        stmt = stmt.where(ObservationReport.case_id == case_id)
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.join(Child, Case.child_id == Child.id).where(
            or_(
                Case.case_code.ilike(q),
                Child.first_name.ilike(q),
                Child.last_name.ilike(q),
                ObservationReport.title.ilike(q),
                ObservationReport.content.ilike(q),
            )
        )
    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(ObservationReport.therapist_user_id == user.id)
    allowed = get_allowed_case_product_modules(user)
    if allowed is not None and allowed:
        stmt = stmt.where(Case.product_module.in_(allowed))
    elif allowed is not None and not allowed:
        stmt = stmt.where(ObservationReport.id < 0)

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    scoped = [r for r in rows if case_scope_check(db, user, db.get(Case, r.case_id))]
    meta = paginated_response(scoped, total, page, page_size)
    if len(scoped) != len(rows):
        meta["total"] = len(scoped)
    return scoped, meta


def cm_review_monthly_report(
    db: Session,
    report: MonthlyReport,
    reviewer_user_id: int,
    *,
    comment: str,
    request_changes: bool,
) -> MonthlyReport:
    """Case manager internal note or correction request without publishing to parents."""
    if request_changes:
        return review_monthly_report(
            db, report, reviewer_user_id, ReviewDecision.REJECT, comment, None
        )
    review = Review(
        entity_type="monthly_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=ReviewDecision.APPROVE,
        comment=f"[CM reviewed] {comment.strip()}",
    )
    db.add(review)
    db.flush()
    return report


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


def review_observation_report(
    db: Session,
    report: ObservationReport,
    reviewer_user_id: int,
    decision: ReviewDecision,
    comment: str | None,
    visibility: VisibilityStatus | None,
) -> ObservationReport:
    review = Review(
        entity_type="observation_report",
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
    db.flush()
    return report
