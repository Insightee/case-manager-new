from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.module_access import get_allowed_case_product_modules
from app.core.pagination import paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.models.case import Case
from app.models.child import Child
from app.models.report import MonthlyReport, ObservationReport, ParentReviewStatus, ReportStatus
from app.models.review import Review, ReviewDecision
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import notification_service, parent_service

ADMIN_OVERRIDE_DAYS = 10
PARENT_PUBLISH_VISIBILITY = frozenset(
    {VisibilityStatus.APPROVED_FOR_PARENT, VisibilityStatus.SHARED_WITH_PARENT}
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def mark_submitted_for_review(report: MonthlyReport) -> None:
    if report.status == ReportStatus.UNDER_REVIEW and not report.submitted_for_review_at:
        report.submitted_for_review_at = _utc_now()


def sync_published_status(report: MonthlyReport) -> bool:
    """Repair legacy rows that have publish timestamps but stale status. Returns True if updated."""
    if (report.cm_published_at or report.admin_published_at) and report.status == ReportStatus.UNDER_REVIEW:
        report.status = ReportStatus.PUBLISHED
        return True
    return False


def can_cm_publish(report: MonthlyReport) -> bool:
    return (
        report.status == ReportStatus.UNDER_REVIEW
        and not report.cm_published_at
        and not report.admin_published_at
    )


def can_admin_override_publish(report: MonthlyReport, now: datetime | None = None) -> bool:
    if report.cm_published_at or report.admin_published_at:
        return False
    if report.status != ReportStatus.UNDER_REVIEW:
        return False
    submitted = _aware(report.submitted_for_review_at)
    if not submitted:
        return False
    now = now or _utc_now()
    return (now - submitted) >= timedelta(days=ADMIN_OVERRIDE_DAYS)


def days_until_admin_override(report: MonthlyReport, now: datetime | None = None) -> int | None:
    if report.cm_published_at or not report.submitted_for_review_at:
        return None
    submitted = _aware(report.submitted_for_review_at)
    if not submitted:
        return None
    now = now or _utc_now()
    remaining = ADMIN_OVERRIDE_DAYS - (now - submitted).days
    return max(0, remaining)


def user_can_cm_publish(user: User) -> bool:
    roles = set(user.role_names or [])
    return "CASE_MANAGER" in roles and user_has_permission(user, "monthly_report.approve")


def user_can_admin_override_publish(user: User) -> bool:
    return user_has_permission(user, "case.read.all")


def publish_workflow_flags(db: Session, user: User, report: MonthlyReport, case: Case | None) -> dict:
    now = _utc_now()
    scoped = case is not None and case_scope_check(db, user, case)
    return {
        "submitted_for_review_at": report.submitted_for_review_at,
        "cm_published_at": report.cm_published_at,
        "admin_published_at": report.admin_published_at,
        "can_cm_publish": scoped and user_can_cm_publish(user) and can_cm_publish(report),
        "can_admin_override_publish": scoped
        and user_can_admin_override_publish(user)
        and can_admin_override_publish(report, now),
        "days_until_admin_override": days_until_admin_override(report, now),
    }


def publish_monthly_to_parent(
    db: Session,
    report: MonthlyReport,
    user: User,
    *,
    override: bool,
    comment: str | None = None,
) -> MonthlyReport:
    now = _utc_now()
    note = (comment or "").strip()
    if override:
        if not user_can_admin_override_publish(user):
            raise PermissionError("Admin override permission required")
        if not can_admin_override_publish(report, now):
            raise ValueError(
                f"Admin override is available {ADMIN_OVERRIDE_DAYS} days after submit if case manager has not published"
            )
        report.admin_published_at = now
        report.admin_published_by_user_id = user.id
        review_note = note or "Published to parents (admin override)"
    else:
        if not user_can_cm_publish(user):
            raise PermissionError("Case manager publish permission required")
        if not can_cm_publish(report):
            raise ValueError("Report is not ready for case manager publish")
        report.cm_published_at = now
        report.cm_published_by_user_id = user.id
        review_note = note or "Published to parents (case manager)"
    report.status = ReportStatus.PUBLISHED
    report.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
    report.parent_review_status = ParentReviewStatus.PENDING.value
    _record_review(
        db,
        entity_type="monthly_report",
        entity_id=report.id,
        reviewer_user_id=user.id,
        decision=ReviewDecision.APPROVE,
        comment=review_note,
    )
    db.flush()
    return report


def notify_parents_monthly_report_published(
    db: Session,
    background_tasks: BackgroundTasks | None,
    *,
    report: MonthlyReport,
    case: Case,
) -> list[int]:
    """Email linked parents when a monthly report is published (non-blocking when tasks provided)."""
    if not case.child_id:
        return []
    from app.models.parent import ParentGuardian, parent_child_link
    from app.models.user import User
    from app.services.email.service import enqueue_report_published_email

    rows = db.execute(
        select(User.email, User.full_name)
        .select_from(parent_child_link)
        .join(ParentGuardian, parent_child_link.c.parent_guardian_id == ParentGuardian.id)
        .join(User, ParentGuardian.user_id == User.id)
        .where(parent_child_link.c.child_id == case.child_id)
    ).all()
    child_name = case.child.full_name if case.child else "your child"
    report_label = report.month or f"Report #{report.id}"
    portal_url = f"{settings.frontend_url.rstrip('/')}/parent/reports"
    log_ids: list[int] = []
    for email, full_name in rows:
        if not email:
            continue
        payload = {
            "parent_name": full_name or "there",
            "child_name": child_name,
            "report_label": report_label,
            "portal_url": portal_url,
        }
        if background_tasks is not None:
            lid = enqueue_report_published_email(
                background_tasks,
                db,
                to=email,
                parent_name=payload["parent_name"],
                child_name=child_name,
                report_label=report_label,
                portal_url=portal_url,
            )
            if lid is not None:
                log_ids.append(lid)
        else:
            from app.services.email.service import send_email
            from app.services.email.templates import render_template as rt

            subject, body_text, body_html = rt("report_published", payload)
            send_email(to=email, subject=subject, body_text=body_text, body_html=body_html)
    return log_ids


def _notify_send_for_review(
    db: Session,
    report: MonthlyReport,
    case: Case,
    *,
    target: str,
    comment: str,
) -> None:
    recipient_id: int | None = None
    if target == "case_manager":
        recipient_id = case.case_manager_user_id
    elif target == "therapist":
        recipient_id = report.therapist_user_id
    if not recipient_id:
        return
    label = report.month or f"Report #{report.id}"
    child = case.child.full_name if case.child else "case"
    notification_service.create_notification(
        db,
        user_id=recipient_id,
        title="Monthly report sent for your review",
        body=f"{child} — {label}: {comment[:400]}",
        entity_type="monthly_report",
        entity_id=report.id,
    )


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


def _record_review(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    reviewer_user_id: int,
    decision: ReviewDecision,
    comment: str,
) -> Review:
    review = Review(
        entity_type=entity_type,
        entity_id=entity_id,
        reviewer_user_id=reviewer_user_id,
        decision=decision,
        comment=comment.strip(),
    )
    db.add(review)
    db.flush()
    return review


def send_monthly_for_review(
    db: Session,
    report: MonthlyReport,
    reviewer_user_id: int,
    *,
    target: str,
    comment: str,
    case: Case | None = None,
) -> MonthlyReport:
    label = "case manager" if target == "case_manager" else "therapist"
    _record_review(
        db,
        entity_type="monthly_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=ReviewDecision.REQUEST_REVIEW,
        comment=f"[To {label}] {comment.strip()}",
    )
    report.reviewer_comment = comment.strip()
    report.status = ReportStatus.UNDER_REVIEW
    mark_submitted_for_review(report)
    if case is not None:
        _notify_send_for_review(db, report, case, target=target, comment=comment.strip())
    db.flush()
    return report


def send_observation_for_review(
    db: Session,
    report: ObservationReport,
    reviewer_user_id: int,
    *,
    target: str,
    comment: str,
) -> ObservationReport:
    label = "case manager" if target == "case_manager" else "therapist"
    _record_review(
        db,
        entity_type="observation_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=ReviewDecision.REQUEST_REVIEW,
        comment=f"[To {label}] {comment.strip()}",
    )
    report.status = ReportStatus.UNDER_REVIEW
    db.flush()
    return report


def add_monthly_review_note(
    db: Session,
    report: MonthlyReport,
    reviewer_user_id: int,
    comment: str,
) -> MonthlyReport:
    _record_review(
        db,
        entity_type="monthly_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=ReviewDecision.NOTE,
        comment=comment.strip(),
    )
    report.reviewer_comment = comment.strip()
    db.flush()
    return report


def add_observation_review_note(
    db: Session,
    report: ObservationReport,
    reviewer_user_id: int,
    comment: str,
) -> ObservationReport:
    _record_review(
        db,
        entity_type="observation_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=ReviewDecision.NOTE,
        comment=comment.strip(),
    )
    db.flush()
    return report


def cm_review_observation_report(
    db: Session,
    report: ObservationReport,
    reviewer_user_id: int,
    *,
    comment: str,
    request_changes: bool,
) -> ObservationReport:
    if request_changes:
        return review_observation_report(
            db, report, reviewer_user_id, ReviewDecision.REJECT, comment, None
        )
    _record_review(
        db,
        entity_type="observation_report",
        entity_id=report.id,
        reviewer_user_id=reviewer_user_id,
        decision=ReviewDecision.APPROVE,
        comment=f"[CM reviewed] {comment.strip()}",
    )
    db.flush()
    return report


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
        vis = visibility or VisibilityStatus.APPROVED_FOR_PARENT
        if vis in PARENT_PUBLISH_VISIBILITY:
            raise ValueError("Use publish-to-parent workflow for parent-visible approval")
        report.status = ReportStatus.PUBLISHED
        report.visibility_status = vis
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
