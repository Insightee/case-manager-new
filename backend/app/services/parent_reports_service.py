from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.case import Case
from app.models.document_comment import CommentType, DocumentComment, DocumentEntityType
from app.models.report import MonthlyReport, ObservationReport, ParentReviewStatus, ReportStatus
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


def parent_can_see_observation(report: ObservationReport) -> bool:
    if report.visibility_status not in PARENT_VISIBLE:
        return False
    return report.status == ReportStatus.PUBLISHED


def parent_can_see_monthly(report: MonthlyReport) -> bool:
    if report.visibility_status not in PARENT_VISIBLE:
        return False
    if report.status in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        return False
    if not (report.cm_published_at or report.admin_published_at):
        return False
    if report.parent_review_status:
        return report.status in (ReportStatus.PUBLISHED, ReportStatus.UNDER_REVIEW)
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


def _iep_ack_status(db: Session, att: Attachment) -> str:
    from app.services import iep_plan_service as iep_svc

    plan = iep_svc._plan_for_attachment(db, att)
    if not plan:
        plan = iep_svc.get_latest_plan(db, att.case_id)
    if plan and plan.status == "PARENT_ACKNOWLEDGED":
        return "acknowledged"
    if att.visibility_status == VisibilityStatus.SHARED_WITH_PARENT:
        return "acknowledged"
    return "pending"


def _serialize_iep_list_item(db: Session, att: Attachment, case: Case | None) -> dict:
    acknowledged = _iep_ack_status(db, att) == "acknowledged"
    from app.services import iep_plan_service as iep_svc

    plan = iep_svc._plan_for_attachment(db, att)
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
        "planId": plan.id if plan else None,
        "issuedAt": att.created_at.isoformat() if att.created_at else None,
    }


def _serialize_observation_list_item(report: ObservationReport, case: Case | None) -> dict:
    return {
        "kind": "observation",
        "id": str(report.id),
        "caseId": case.case_code if case else "",
        "caseDbId": report.case_id,
        "childName": case.child.full_name if case and case.child else "",
        "title": report.title,
        "label": report.title,
        "reportDate": report.report_date.isoformat() if report.report_date else None,
        "status": "approved",
        "summaryPreview": (report.content or "")[:120],
        "category": report.category,
    }


def list_observation_for_case(db: Session, user: User, case_id: int) -> list[dict]:
    case = parent_service.get_parent_case(db, user, case_id)
    if not case:
        raise ValueError("Case not found")
    rows = db.scalars(select(ObservationReport).where(ObservationReport.case_id == case_id)).all()
    return [_serialize_observation_list_item(r, case) for r in rows if parent_can_see_observation(r)]


def get_observation_detail(db: Session, user: User, report_id: int) -> dict:
    report = db.get(ObservationReport, report_id)
    if not report or not parent_can_see_observation(report):
        raise ValueError("Report not found")
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        raise ValueError("Report not found")
    return {
        "kind": "observation",
        "id": str(report.id),
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "title": report.title,
        "bodyHtml": report.body_html,
        "content": report.content,
        "planNextMonth": report.plan_next_month,
        "reportDate": report.report_date.isoformat() if report.report_date else None,
        "downloadPath": f"/api/v1/parent/reports/observation/{report.id}/download",
        "status": "approved",
        "createdAt": report.created_at.isoformat() if report.created_at else None,
    }


def case_reports_summary(db: Session, user: User, case_id: int) -> dict:
    case = parent_service.get_parent_case(db, user, case_id)
    if not case:
        raise ValueError("Case not found")
    monthly_rows = db.scalars(select(MonthlyReport).where(MonthlyReport.case_id == case_id)).all()
    monthly_count = sum(1 for r in monthly_rows if parent_can_see_monthly(r))
    obs_count = len(list_observation_for_case(db, user, case_id))
    iep_count = len(
        db.scalars(
            select(Attachment).where(
                Attachment.case_id == case_id,
                Attachment.entity_type == "iep",
                Attachment.visibility_status.in_(PARENT_VISIBLE),
            )
        ).all()
    )
    from app.services import case_document_service as case_doc_svc

    doc_count = sum(1 for d in case_doc_svc.list_for_parent(db, user.id) if d.get("caseDbId") == case_id)
    return {
        "monthlyCount": monthly_count,
        "observationCount": obs_count,
        "iepCount": iep_count,
        "documentsCount": doc_count,
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
    iep = [_serialize_iep_list_item(db, a, cases.get(a.case_id)) for a in attachments]
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


def _parent_visible_iep_plan(db: Session, att: Attachment) -> "IepPlan | None":
    from app.models.iep_plan import IepPlan, IepPlanStatus
    from app.services import iep_plan_service as iep_svc

    visible = {
        IepPlanStatus.SHARED_WITH_PARENT.value,
        IepPlanStatus.PARENT_ACKNOWLEDGED.value,
    }
    plan = iep_svc._plan_for_attachment(db, att)
    if plan and plan.status in visible:
        return plan
    latest = iep_svc.get_latest_plan(db, att.case_id)
    if latest and latest.status in visible:
        return latest
    return None


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
        "downloadPath": f"/api/v1/parent/reports/monthly/{report.id}/download",
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
    from app.services import iep_plan_service as iep_svc

    plan = _parent_visible_iep_plan(db, att)
    ack_status = _iep_ack_status(db, att)
    can_acknowledge = bool(plan and plan.status == "SHARED_WITH_PARENT")
    can_suggest_goals = bool(plan and plan.status in ("SHARED_WITH_PARENT", "PARENT_ACKNOWLEDGED"))
    preview_html = iep_svc.sections_to_preview_html(db, plan) if plan else None
    plan_version = plan.version if plan else att.version
    title = f"IEP {plan_version}" if plan else (att.file_name or "IEP document")
    download_path = (
        f"/api/v1/parent/reports/iep/{att.id}/download"
        if plan
        else f"/api/v1/parent/attachments/{att.id}/download"
    )
    return {
        "kind": "iep",
        "id": str(att.id),
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "version": plan_version,
        "fileName": att.file_name,
        "title": title,
        "downloadPath": download_path,
        "status": ack_status,
        "planId": plan.id if plan else None,
        "canAcknowledge": can_acknowledge,
        "canSuggestGoals": can_suggest_goals,
        "bodyHtml": preview_html,
        "issuedAt": att.created_at.isoformat() if att.created_at else None,
        "comments": _comment_rows(db, DocumentEntityType.IEP.value, att.id),
    }


def monthly_report_pdf_bytes(db: Session, user: User, report_id: int) -> tuple[bytes, str]:
    from app.services import report_pdf_service
    from app.services.export_document_service import export_meta

    report = db.get(MonthlyReport, report_id)
    if not report or not parent_can_see_monthly(report):
        raise ValueError("Report not found")
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        raise ValueError("Report not found")
    child_name = case.child.full_name if case.child else ""
    meta = export_meta(user)
    pdf = report_pdf_service.monthly_report_pdf(
        report,
        case.case_code,
        child_name,
        generated_by=meta["generated_by"],
        generated_at=meta["generated_at"],
    )
    safe = (report.month or "report").replace(" ", "_")[:40]
    return pdf, f"report_{safe}.pdf"


def iep_report_pdf_bytes(db: Session, user: User, attachment_id: int) -> tuple[bytes, str]:
    from app.services import iep_plan_service as iep_svc

    att = db.get(Attachment, attachment_id)
    if not att or att.entity_type != "iep" or att.visibility_status not in PARENT_VISIBLE:
        raise ValueError("IEP document not found")
    case = parent_service.get_parent_case(db, user, att.case_id)
    if not case:
        raise ValueError("IEP document not found")
    plan = _parent_visible_iep_plan(db, att)
    if plan:
        pdf = iep_svc.sections_to_pdf_bytes(db, plan)
        safe = f"IEP_{case.case_code}_{plan.version}".replace(" ", "_")[:60]
        return pdf, f"{safe}.pdf"
    from app.storage.object_io import read_stored_bytes

    data = read_stored_bytes(att.file_path)
    name = att.file_name or f"iep_{att.id}.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name.rsplit('.', 1)[0]}.pdf" if "." in name else f"{name}.pdf"
    return data, name


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


def acknowledge_iep(db: Session, att: Attachment, parent_user: User | None = None) -> None:
    att.visibility_status = VisibilityStatus.SHARED_WITH_PARENT
    from app.services import iep_plan_service as iep_svc

    plan = iep_svc._plan_for_attachment(db, att)
    if not plan:
        plan = iep_svc.get_latest_plan(db, att.case_id)
    if plan and parent_user and plan.status == "SHARED_WITH_PARENT":
        iep_svc.parent_acknowledge_plan(db, plan, parent_user)


def resend_to_parent(db: Session, report: MonthlyReport) -> MonthlyReport:
    if report.visibility_status not in PARENT_VISIBLE:
        report.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
    report.parent_review_status = ParentReviewStatus.PENDING.value
    report.parent_feedback = None
    report.status = ReportStatus.PUBLISHED
    db.flush()
    return report
