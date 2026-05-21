from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.case import Case
from app.models.document_comment import CommentType, DocumentComment, DocumentEntityType
from app.models.report import MonthlyReport, ParentReviewStatus, ReportStatus
from app.models.review import Review, ReviewDecision
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import notification_service, parent_service

PARENT_VISIBLE = parent_service.PARENT_VISIBLE


def _parent_case_ids(db: Session, user_id: int) -> list[int]:
    child_ids = parent_service.child_ids_for_parent(db, user_id)
    if not child_ids:
        return []
    return list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())


def parent_can_see_monthly(report: MonthlyReport) -> bool:
    if report.visibility_status not in PARENT_VISIBLE:
        return False
    if report.parent_review_status:
        return True
    return report.status == ReportStatus.PUBLISHED


def _parent_status_label(report: MonthlyReport) -> str:
    prs = report.parent_review_status
    if prs == ParentReviewStatus.PENDING.value:
        return "pending_review"
    if prs == ParentReviewStatus.APPROVED.value:
        return "approved"
    if prs == ParentReviewStatus.CHANGES_REQUESTED.value:
        return "changes_sent"
    if report.status == ReportStatus.PUBLISHED:
        return "approved"
    return "pending_review"


def _serialize_monthly_list_item(report: MonthlyReport, case: Case | None) -> dict:
    return {
        "kind": "monthly",
        "id": str(report.id),
        "caseId": case.case_code if case else "",
        "caseDbId": report.case_id,
        "childName": case.child.full_name if case and case.child else "",
        "month": report.month,
        "label": report.month,
        "status": _parent_status_label(report),
        "parentReviewStatus": report.parent_review_status,
        "summaryPreview": (report.summary or "")[:120],
        "category": report.category,
    }


def _serialize_iep_list_item(att: Attachment, case: Case | None) -> dict:
    acknowledged = att.visibility_status == VisibilityStatus.SHARED_WITH_PARENT
    return {
        "kind": "iep",
        "id": str(att.id),
        "caseId": case.case_code if case else "",
        "caseDbId": att.case_id,
        "childName": case.child.full_name if case and case.child else "",
        "version": att.version,
        "label": f"Version {att.version}",
        "fileName": att.file_name,
        "status": "acknowledged" if acknowledged else "pending",
        "issuedAt": att.created_at.isoformat() if att.created_at else None,
    }


def list_hub(db: Session, user_id: int) -> dict:
    case_ids = _parent_case_ids(db, user_id)
    if not case_ids:
        return {"monthly": [], "iep": [], "items": []}

    cases = {c.id: c for c in db.scalars(select(Case).where(Case.id.in_(case_ids))).all()}
    monthly_rows = db.scalars(select(MonthlyReport).where(MonthlyReport.case_id.in_(case_ids))).all()
    monthly = [
        _serialize_monthly_list_item(r, cases.get(r.case_id))
        for r in monthly_rows
        if parent_can_see_monthly(r)
    ]
    attachments = db.scalars(
        select(Attachment).where(
            Attachment.case_id.in_(case_ids),
            Attachment.entity_type == "iep",
            Attachment.visibility_status.in_(PARENT_VISIBLE),
        )
    ).all()
    iep = [_serialize_iep_list_item(a, cases.get(a.case_id)) for a in attachments]
    items = sorted(
        monthly + iep,
        key=lambda x: x.get("issuedAt") or x.get("month") or "",
        reverse=True,
    )
    return {"monthly": monthly, "iep": iep, "items": items}


def _comment_rows(db: Session, entity_type: str, entity_id: int) -> list[dict]:
    rows = db.scalars(
        select(DocumentComment)
        .where(
            DocumentComment.entity_type == entity_type,
            DocumentComment.entity_id == entity_id,
        )
        .order_by(DocumentComment.created_at.asc())
    ).all()
    result = []
    for c in rows:
        author = db.get(User, c.author_user_id)
        result.append(
            {
                "id": c.id,
                "commentType": c.comment_type,
                "body": c.body,
                "authorName": author.full_name if author else "Parent",
                "createdAt": c.created_at.isoformat() if c.created_at else None,
            }
        )
    return result


def get_monthly_detail(db: Session, user: User, report_id: int) -> dict:
    report = db.get(MonthlyReport, report_id)
    if not report or not parent_can_see_monthly(report):
        raise ValueError("Report not found")
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        raise ValueError("Report not found")
    return {
        "kind": "monthly",
        "id": str(report.id),
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "month": report.month,
        "summary": report.summary,
        "bodyHtml": report.body_html,
        "planNextMonth": report.plan_next_month,
        "category": report.category,
        "downloadPath": f"/api/v1/reports/monthly/{report.id}/download",
        "status": _parent_status_label(report),
        "parentReviewStatus": report.parent_review_status,
        "parentFeedback": report.parent_feedback,
        "createdAt": report.created_at.isoformat() if report.created_at else None,
        "comments": _comment_rows(db, DocumentEntityType.MONTHLY_REPORT.value, report.id),
    }


def get_iep_detail(db: Session, user: User, attachment_id: int) -> dict:
    att = db.get(Attachment, attachment_id)
    if not att or att.entity_type != "iep" or att.visibility_status not in PARENT_VISIBLE:
        raise ValueError("IEP document not found")
    case = parent_service.get_parent_case(db, user, att.case_id)
    if not case:
        raise ValueError("IEP document not found")
    return {
        "kind": "iep",
        "id": str(att.id),
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "version": att.version,
        "fileName": att.file_name,
        "downloadPath": f"/api/v1/parent/attachments/{att.id}/download",
        "status": "acknowledged" if att.visibility_status == VisibilityStatus.SHARED_WITH_PARENT else "pending",
        "issuedAt": att.created_at.isoformat() if att.created_at else None,
        "comments": _comment_rows(db, DocumentEntityType.IEP.value, att.id),
    }


def _notify_case_team(
    db: Session,
    case: Case,
    *,
    title: str,
    body: str,
    entity_type: str,
    entity_id: int,
    extra_user_ids: list[int] | None = None,
) -> None:
    user_ids: set[int] = set(extra_user_ids or [])
    if case.case_manager_user_id:
        user_ids.add(case.case_manager_user_id)
    for uid in user_ids:
        notification_service.create_notification(
            db,
            user_id=uid,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
        )


def approve_monthly(db: Session, user: User, report_id: int) -> dict:
    report = db.get(MonthlyReport, report_id)
    if not report or not parent_can_see_monthly(report):
        raise ValueError("Report not found")
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        raise ValueError("Report not found")
    now = datetime.now(timezone.utc)
    report.parent_review_status = ParentReviewStatus.APPROVED.value
    report.parent_reviewed_at = now
    report.status = ReportStatus.PUBLISHED
    db.flush()
    _notify_case_team(
        db,
        case,
        title="Parent approved monthly report",
        body=f"{case.child.full_name if case.child else 'Child'} — {report.month}",
        entity_type="monthly_report",
        entity_id=report.id,
        extra_user_ids=[report.therapist_user_id] if report.therapist_user_id else None,
    )
    return {"status": "approved", "parentReviewStatus": report.parent_review_status}


def feedback_monthly(db: Session, user: User, report_id: int, message: str) -> dict:
    report = db.get(MonthlyReport, report_id)
    if not report or not parent_can_see_monthly(report):
        raise ValueError("Report not found")
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        raise ValueError("Report not found")
    report.parent_review_status = ParentReviewStatus.CHANGES_REQUESTED.value
    report.parent_feedback = message
    report.parent_reviewed_at = datetime.now(timezone.utc)
    report.status = ReportStatus.UNDER_REVIEW
    review = Review(
        entity_type="monthly_report",
        entity_id=report.id,
        reviewer_user_id=user.id,
        decision=ReviewDecision.REJECT,
        comment=message,
    )
    db.add(review)
    db.flush()
    _notify_case_team(
        db,
        case,
        title="Parent requested report changes",
        body=message[:500],
        entity_type="monthly_report",
        entity_id=report.id,
        extra_user_ids=[report.therapist_user_id] if report.therapist_user_id else None,
    )
    return {"status": "changes_requested", "parentReviewStatus": report.parent_review_status}


def add_iep_comment(
    db: Session,
    user: User,
    attachment_id: int,
    body: str,
    comment_type: str,
) -> dict:
    att = db.get(Attachment, attachment_id)
    if not att or att.entity_type != "iep" or att.visibility_status not in PARENT_VISIBLE:
        raise ValueError("IEP document not found")
    case = parent_service.get_parent_case(db, user, att.case_id)
    if not case:
        raise ValueError("IEP document not found")
    comment = DocumentComment(
        entity_type=DocumentEntityType.IEP.value,
        entity_id=att.id,
        case_id=att.case_id,
        author_user_id=user.id,
        comment_type=comment_type,
        body=body,
    )
    db.add(comment)
    db.flush()
    _notify_case_team(
        db,
        case,
        title="New IEP comment from parent",
        body=body[:500],
        entity_type="iep",
        entity_id=att.id,
    )
    return {
        "id": comment.id,
        "commentType": comment.comment_type,
        "body": comment.body,
        "createdAt": comment.created_at.isoformat() if comment.created_at else None,
    }


def acknowledge_iep(db: Session, att: Attachment) -> None:
    att.visibility_status = VisibilityStatus.SHARED_WITH_PARENT


def resend_to_parent(db: Session, report: MonthlyReport) -> MonthlyReport:
    if report.visibility_status not in PARENT_VISIBLE:
        report.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
    report.parent_review_status = ParentReviewStatus.PENDING.value
    report.parent_feedback = None
    report.status = ReportStatus.PUBLISHED
    db.flush()
    return report
