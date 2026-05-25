from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName
from app.models.attachment import Attachment
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.notification import Notification
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.slot import SlotStatus, TherapistSlot
from app.models.support_ticket import SupportTicket, TicketMessage, TicketStatus, TicketTopic
from app.models.incident import Incident, IncidentMessage, IncidentStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.address import ServiceAddressUpdate
from app.schemas.daily_log import ParentSessionFeedbackUpdate, ParentSessionLogRead
from app.schemas.parent_profile import ParentChildCreate, ParentProfileRead, ParentProfileUpdate
from app.schemas.notification import NotificationRead
from app.schemas.parent_reports import ParentMonthlyFeedback, ParentReportCommentCreate
from app.core.config import settings
from app.schemas.parent_home import ParentHomeResponse
from app.services import (
    address_service,
    appointment_booking_service as appt_booking,
    appointment_policy,
    notification_service,
    parent_home_service,
    parent_reports_service,
    parent_service,
    parent_ticket_service,
    slot_calendar_service,
    ticket_attachment_service as att_svc,
    ticket_escalation_service as ticket_esc,
)

router = APIRouter(prefix="/parent", tags=["parent"])

PARENT_VISIBLE = parent_service.PARENT_VISIBLE


def _require_parent(user: User):
    if RoleName.PARENT.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Parent access only")


def _parent_case_or_404(db: Session, user: User, case_id: int) -> Case:
    case = parent_service.get_parent_case(db, user, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


class ParentSupportRequest(BaseModel):
    subject: str = "Support request"
    message: str = ""
    case_id: Optional[int] = None
    topic: str = "OTHER"


class ParentTicketMessageCreate(BaseModel):
    body: str


class ParentTicketRateRequest(BaseModel):
    rating: int
    feedback: Optional[str] = None


class ParentTicketAcceptRequest(BaseModel):
    feedback: Optional[str] = None


class ParentRescheduleRequest(BaseModel):
    new_slot_id: int


@router.get("/profile", response_model=ParentProfileRead)
def parent_profile_get(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_service.get_parent_profile(db, user)


@router.post("/children", response_model=ParentProfileRead, status_code=201)
def parent_add_child(
    payload: ParentChildCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    result = parent_service.add_child_to_parent(
        db, user, payload.first_name, payload.last_name or ""
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="add_child", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    return result


@router.patch("/profile", response_model=ParentProfileRead)
def parent_profile_update(
    payload: ParentProfileUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    data = payload.model_dump(exclude_unset=True)
    if payload.service_address is not None:
        data["service_address"] = {
            "case_id": payload.service_address.case_id,
            "address": payload.service_address.address.model_dump(exclude_unset=True),
        }
    result = parent_service.update_parent_profile(db, user, data)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update_parent_profile", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    return result


@router.get("/home", response_model=ParentHomeResponse)
def parent_home(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_home_service.build_parent_home(db, user)


@router.get("/cases")
def parent_cases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_service.list_parent_cases(db, user)


def _parent_session_log_read(log: DailyLog, case: Case | None, therapist: User | None) -> ParentSessionLogRead:
    fields = parent_home_service.parent_log_card_fields(
        log, case=case, therapist_name=therapist.full_name if therapist else None
    )
    s = log.session
    return ParentSessionLogRead(
        id=log.id,
        case_id=s.case_id if s else 0,
        case_code=case.case_code if case else None,
        child_name=case.child.full_name if case and case.child else None,
        therapist_name=fields.get("therapist_name"),
        scheduled_date=s.scheduled_date if s else log.created_at.date(),
        start_time=s.start_time.isoformat() if s and s.start_time else None,
        end_time=s.end_time.isoformat() if s and s.end_time else None,
        actual_start_at=s.actual_start_at if s else None,
        actual_end_at=s.actual_end_at if s else None,
        attendance_status=log.attendance_status,
        activities_done=log.activities_done,
        goals_addressed=log.goals_addressed,
        follow_ups=log.follow_ups,
        parent_notes=log.parent_notes,
        parent_session_rating=log.parent_session_rating,
        parent_feedback=log.parent_feedback,
        parent_feedback_at=log.parent_feedback_at,
        parent_feedback_public=bool(log.parent_feedback_public),
        submitted_at=log.submitted_at,
        headline=fields.get("headline"),
        summary_paragraph=fields.get("summary_paragraph"),
        attendance_label=fields.get("attendance_label"),
        what_we_did=fields.get("what_we_did"),
        what_is_next=fields.get("what_is_next"),
    )


@router.get("/cases/{case_id}")
def parent_case_detail(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    case = _parent_case_or_404(db, user, case_id)
    if not case.child:
        db.refresh(case, ["child"])
    return parent_service.parent_case_payload(db, case)


@router.patch("/cases/{case_id}/service-address")
def parent_update_service_address(
    case_id: int,
    payload: ServiceAddressUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    case = _parent_case_or_404(db, user, case_id)
    if not address_service.is_homecare_case(case):
        raise HTTPException(status_code=400, detail="Service address applies to homecare cases only")
    service_data = address_service.service_address_from_payload(payload.model_dump(exclude_unset=True))
    if not service_data:
        raise HTTPException(status_code=400, detail="No address fields provided")
    address_service.validate_service_address_payload(service_data, case)
    address_service.apply_service_address_to_case(case, service_data)
    db.commit()
    db.refresh(case)
    svc = address_service.case_service_address_read(case)
    return {
        "id": case.id,
        "serviceAddress": svc.model_dump() if svc else None,
        "serviceAddressSummary": address_service.service_address_summary(case),
    }


@router.get("/session-logs", response_model=list[ParentSessionLogRead])
def parent_session_logs(
    case_id: Optional[int] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    if case_id is not None:
        _parent_case_or_404(db, user, case_id)
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    case_stmt = select(Case).where(Case.child_id.in_(child_ids))
    if case_id is not None:
        case_stmt = case_stmt.where(Case.id == case_id)
    cases = {c.id: c for c in db.scalars(case_stmt).all()}
    if not cases:
        return []
    log_stmt = (
        select(DailyLog)
        .join(TherapySession)
        .where(
            TherapySession.case_id.in_(cases.keys()),
            DailyLog.submitted_at.isnot(None),
            DailyLog.visibility_status.in_(PARENT_VISIBLE),
            DailyLog.approval_status == LogApprovalStatus.APPROVED,
        )
        .options(
            selectinload(DailyLog.session).selectinload(TherapySession.case).selectinload(Case.child),
        )
        .order_by(TherapySession.scheduled_date.desc())
    )
    if year is not None:
        from sqlalchemy import extract
        log_stmt = log_stmt.where(extract("year", TherapySession.scheduled_date) == year)
    if month is not None:
        from sqlalchemy import extract as _extract
        log_stmt = log_stmt.where(_extract("month", TherapySession.scheduled_date) == month)
    logs = db.scalars(log_stmt).all()
    result = []
    for log in logs:
        s = log.session
        if not s:
            continue
        case = cases.get(s.case_id)
        therapist = db.get(User, s.therapist_user_id)
        result.append(_parent_session_log_read(log, case, therapist))
    return result


@router.patch("/session-logs/{log_id}/feedback", response_model=ParentSessionLogRead)
def parent_session_log_feedback(
    log_id: int,
    payload: ParentSessionFeedbackUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    log = db.scalars(
        select(DailyLog)
        .join(TherapySession)
        .where(DailyLog.id == log_id)
        .options(selectinload(DailyLog.session).selectinload(TherapySession.case).selectinload(Case.child))
    ).first()
    if not log or not log.session:
        raise HTTPException(status_code=404, detail="Session log not found")
    case = log.session.case
    if not case or case.child_id not in child_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    if log.visibility_status not in PARENT_VISIBLE:
        raise HTTPException(status_code=404, detail="Session log not found")
    if not log.submitted_at:
        raise HTTPException(status_code=404, detail="Session log not found")
    if log.approval_status != LogApprovalStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Feedback only on approved session updates")
    if payload.rating is not None:
        if payload.rating < 1 or payload.rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        log.parent_session_rating = payload.rating
    if payload.feedback is not None:
        log.parent_feedback = payload.feedback.strip() or None
    if payload.share_publicly is not None:
        log.parent_feedback_public = payload.share_publicly
    if not log.parent_session_rating and not log.parent_feedback:
        raise HTTPException(status_code=400, detail="Add a star rating or written review")
    log.parent_feedback_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(log)
    s = log.session
    therapist = db.get(User, s.therapist_user_id)
    return _parent_session_log_read(log, case, therapist)


@router.get("/documents")
def parent_documents_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    from app.services import case_document_service as case_doc_svc

    return {"items": case_doc_svc.list_for_parent(db, user.id)}


@router.get("/documents/{document_id}")
def parent_document_detail(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    from app.models.case_document import CaseDocument
    from app.services import case_document_service as case_doc_svc

    doc = db.scalars(
        select(CaseDocument)
        .where(CaseDocument.id == document_id)
        .options(selectinload(CaseDocument.versions))
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    case_doc_svc.require_read(db, user, doc)
    return case_doc_svc._serialize_detail(db, user, doc)


@router.get("/documents/{document_id}/comments")
def parent_document_comments_list(
    document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    from app.models.case_document import CaseDocument
    from app.services import case_document_service as case_doc_svc

    doc = db.get(CaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return case_doc_svc.list_comments(db, user, doc)


@router.post("/documents/{document_id}/comments")
def parent_document_comment(
    document_id: int,
    payload: ParentReportCommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    from app.models.case_document import CaseDocument
    from app.services import case_document_service as case_doc_svc

    doc = db.get(CaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    row = case_doc_svc.add_comment(
        db, user, doc, body=payload.body.strip(), comment_type=payload.comment_type
    )
    db.commit()
    return row


@router.post("/documents/{document_id}/approve")
def parent_document_approve(
    document_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    from app.models.case_document import CaseDocument
    from app.services import case_document_service as case_doc_svc

    doc = db.scalars(
        select(CaseDocument)
        .where(CaseDocument.id == document_id)
        .options(selectinload(CaseDocument.versions))
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    detail = case_doc_svc.run_workflow(db, user, doc, "parent_approve")
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="parent_approve",
        entity_type="case_document",
        entity_id=document_id,
        case_id=doc.case_id,
        **meta,
    )
    db.commit()
    return detail


@router.post("/documents/{document_id}/feedback")
def parent_document_feedback(
    document_id: int,
    payload: ParentMonthlyFeedback,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    from app.models.case_document import CaseDocument
    from app.services import case_document_service as case_doc_svc

    doc = db.scalars(
        select(CaseDocument)
        .where(CaseDocument.id == document_id)
        .options(selectinload(CaseDocument.versions))
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    detail = case_doc_svc.run_workflow(db, user, doc, "parent_feedback", comment=payload.message.strip())
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="parent_feedback",
        entity_type="case_document",
        entity_id=document_id,
        case_id=doc.case_id,
        **meta,
    )
    db.commit()
    return detail


@router.get("/reports/hub")
def parent_reports_hub(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_reports_service.list_hub(db, user.id)


@router.get("/cases/{case_id}/reports-summary")
def parent_case_reports_summary(
    case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    _parent_case_or_404(db, user, case_id)
    try:
        return parent_reports_service.case_reports_summary(db, user, case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.get("/cases/{case_id}/observation-reports")
def parent_case_observation_reports(
    case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    _parent_case_or_404(db, user, case_id)
    try:
        return parent_reports_service.list_observation_for_case(db, user, case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.get("/reports/observation/{report_id}")
def parent_observation_report_detail(
    report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        return parent_reports_service.get_observation_detail(db, user, report_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")


@router.get("/reports/observation/{report_id}/download")
def parent_observation_report_download(
    report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from fastapi.responses import Response

    from app.models.report import ObservationReport
    from app.services import parent_reports_service, report_pdf_service
    from app.services.parent_service import get_parent_case

    _require_parent(user)
    report = db.get(ObservationReport, report_id)
    if not report or not parent_reports_service.parent_can_see_observation(report):
        raise HTTPException(status_code=404, detail="Report not found")
    case = get_parent_case(db, user, report.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Report not found")
    child_name = case.child.full_name if case.child else ""
    pdf = report_pdf_service.observation_report_pdf(report, case.case_code, child_name)
    safe = (report.title or "observation").replace(" ", "_")[:40]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="observation_{safe}.pdf"'},
    )


@router.get("/reports/monthly/{report_id}")
def parent_monthly_report_detail(
    report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        return parent_reports_service.get_monthly_detail(db, user, report_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")


@router.post("/reports/monthly/{report_id}/approve")
def parent_approve_monthly_report(
    report_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    try:
        result = parent_reports_service.approve_monthly(db, user, report_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="parent_approve", entity_type="monthly_report", entity_id=report_id, **meta)
    db.commit()
    return result


@router.post("/reports/monthly/{report_id}/feedback")
def parent_feedback_monthly_report(
    report_id: int,
    payload: ParentMonthlyFeedback,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    try:
        result = parent_reports_service.feedback_monthly(db, user, report_id, payload.message.strip())
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="parent_feedback", entity_type="monthly_report", entity_id=report_id, **meta)
    db.commit()
    return result


@router.get("/reports/iep/{attachment_id}")
def parent_iep_report_detail(
    attachment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_parent(user)
    try:
        return parent_reports_service.get_iep_detail(db, user, attachment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="IEP document not found")


@router.post("/reports/iep/{attachment_id}/comments")
def parent_iep_comment(
    attachment_id: int,
    payload: ParentReportCommentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    try:
        result = parent_reports_service.add_iep_comment(
            db, user, attachment_id, payload.body.strip(), payload.comment_type
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="IEP document not found")
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="iep_comment", entity_type="iep", entity_id=attachment_id, **meta)
    db.commit()
    return result


@router.post("/reports/iep/{attachment_id}/acknowledge")
def parent_acknowledge_iep_via_reports(
    attachment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    att = db.get(Attachment, attachment_id)
    if not att or att.entity_type != "iep":
        raise HTTPException(status_code=404, detail="IEP document not found")
    _parent_case_or_404(db, user, att.case_id)
    if att.visibility_status not in PARENT_VISIBLE:
        raise HTTPException(status_code=404, detail="IEP document not found")
    parent_reports_service.acknowledge_iep(db, att)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="acknowledge", entity_type="iep", entity_id=att.id, **meta)
    db.commit()
    return {"status": "acknowledged"}


@router.get("/reports")
def parent_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    hub = parent_reports_service.list_hub(db, user.id)
    return [
        {
            "id": item["id"],
            "caseId": item["caseId"],
            "caseDbId": item["caseDbId"],
            "childName": item["childName"],
            "month": item.get("month") or item.get("label"),
            "status": item["status"],
            "summary": item.get("summaryPreview", ""),
        }
        for item in hub["monthly"]
    ]


@router.get("/reports/{report_id}")
def parent_report_detail(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    try:
        detail = parent_reports_service.get_monthly_detail(db, user, report_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": detail["id"],
        "caseId": detail["caseId"],
        "caseDbId": detail["caseDbId"],
        "childName": detail["childName"],
        "month": detail["month"],
        "status": detail["status"],
        "summary": detail["summary"],
        "createdAt": detail.get("createdAt"),
        "parentReviewStatus": detail.get("parentReviewStatus"),
    }


@router.get("/billing-summaries")
def parent_billing(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_service.list_billing_summaries(db, user)


@router.get("/iep-status")
def parent_iep(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
    attachments = (
        db.scalars(
            select(Attachment).where(
                Attachment.case_id.in_(case_ids),
                Attachment.entity_type == "iep",
                Attachment.visibility_status.in_(PARENT_VISIBLE),
            )
        ).all()
        if case_ids
        else []
    )
    result = []
    for a in attachments:
        case = db.get(Case, a.case_id)
        result.append(
            {
                "id": str(a.id),
                "caseId": case.case_code if case else "",
                "caseDbId": a.case_id,
                "childName": case.child.full_name if case and case.child else "",
                "version": a.version,
                "fileName": a.file_name,
                "status": "acknowledged" if a.visibility_status == VisibilityStatus.SHARED_WITH_PARENT else "pending",
                "issuedAt": a.created_at.isoformat(),
            }
        )
    return result


@router.post("/iep/{attachment_id}/acknowledge")
def parent_acknowledge_iep(
    attachment_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    att = db.get(Attachment, attachment_id)
    if not att or att.entity_type != "iep":
        raise HTTPException(status_code=404, detail="IEP document not found")
    _parent_case_or_404(db, user, att.case_id)
    if att.visibility_status not in PARENT_VISIBLE:
        raise HTTPException(status_code=404, detail="IEP document not found")
    att.visibility_status = VisibilityStatus.SHARED_WITH_PARENT
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="acknowledge", entity_type="iep", entity_id=att.id, **meta)
    db.commit()
    return {"status": "acknowledged"}


@router.get("/attachments/{attachment_id}/download")
def parent_download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    att = db.get(Attachment, attachment_id)
    if not att or att.visibility_status not in PARENT_VISIBLE:
        raise HTTPException(status_code=404, detail="File not found")
    _parent_case_or_404(db, user, att.case_id)
    path = Path(att.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(path, filename=att.file_name)


@router.get("/booking/calendar")
def parent_booking_calendar(
    case_id: int,
    therapist_id: int,
    from_date: date,
    to_date: date,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    _parent_case_or_404(db, user, case_id)
    return appt_booking.parent_calendar_view(db, case_id, therapist_id, from_date, to_date, user.id)


@router.get("/appointments")
def parent_appointments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
    today = date.today()
    slots = db.scalars(
        select(TherapistSlot)
        .where(
            TherapistSlot.case_id.in_(case_ids),
            TherapistSlot.status == SlotStatus.BOOKED,
            TherapistSlot.slot_date >= today,
        )
        .order_by(TherapistSlot.slot_date.asc(), TherapistSlot.start_time.asc())
    ).all()
    result = []
    for sl in slots:
        if not sl.case_id:
            continue
        _parent_case_or_404(db, user, sl.case_id)
        result.append(appt_booking.serialize_parent_appointment(db, sl, sl.case_id))
    return result


@router.post("/appointments/{slot_id}/cancel")
def parent_cancel_appointment(
    slot_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    slot = db.get(TherapistSlot, slot_id)
    if not slot or slot.status != SlotStatus.BOOKED or not slot.case_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _parent_case_or_404(db, user, slot.case_id)
    check = appointment_policy.can_parent_cancel(slot, slot.case_id, db)
    if not check.allowed:
        raise HTTPException(status_code=400, detail=check.reason)
    appt_booking.cancel_booking_with_session(db, slot_id, therapist_user_id=slot.therapist_user_id)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="cancel_appointment", entity_type="slot", entity_id=slot_id, **meta)
    db.commit()
    return {"status": "cancelled"}


@router.post("/appointments/{slot_id}/reschedule")
def parent_reschedule_appointment(
    slot_id: int,
    payload: ParentRescheduleRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    slot = db.get(TherapistSlot, slot_id)
    if not slot or not slot.case_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    case_id = slot.case_id
    _parent_case_or_404(db, user, case_id)
    try:
        new_slot = appt_booking.parent_reschedule(
            db, slot_id, payload.new_slot_id, case_id, user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="reschedule_appointment",
        entity_type="slot",
        entity_id=new_slot.id,
        **meta,
    )
    db.commit()
    return appt_booking.serialize_parent_appointment(db, new_slot, case_id)


@router.get("/notifications", response_model=list[NotificationRead])
def parent_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    rows = notification_service.list_notifications(db, user.id)
    return [
        NotificationRead(
            id=n.id,
            title=n.title,
            body=n.body,
            is_read=n.is_read,
            created_at=n.created_at,
            entity_type=n.entity_type,
            entity_id=n.entity_id,
        )
        for n in rows
    ]


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"status": "read"}


@router.get("/portal-info")
def parent_portal_info():
    return {
        "support_email": settings.support_contact_email,
        "support_phone": settings.support_phone,
        "office_address": settings.support_office_address,
        "grievance_policy_url": settings.grievance_policy_url,
        "policies_bot_url": settings.policies_bot_url or None,
        "ticket_attachment_max_bytes": settings.ticket_attachment_max_bytes,
        "ticket_attachment_max_files": settings.ticket_attachment_max_files,
        "ticket_topics": [
            {"id": t.value, "label": ticket_esc.TOPIC_LABELS[t]}
            for t in TicketTopic
        ],
        "escalation_matrix": {
            t.value: {"levels": ticket_esc.ESCALATION_MATRIX[t]}
            for t in TicketTopic
        },
    }


@router.get("/support/tickets")
def parent_list_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_ticket_service.list_parent_tickets(db, user)


@router.get("/support/tickets/{ticket_id}")
def parent_ticket_detail(ticket_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_ticket_service.get_parent_ticket(db, user, ticket_id)


@router.post("/support-requests", status_code=201)
async def parent_support(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    content_type = request.headers.get("content-type", "")
    files = []
    if "multipart/form-data" in content_type:
        form = await request.form()
        subject = str(form.get("subject") or "Support request").strip()
        message = str(form.get("message") or "").strip()
        topic_raw = str(form.get("topic") or "OTHER")
        case_id_raw = form.get("case_id")
        case_id = int(case_id_raw) if case_id_raw not in (None, "") else None
        files = att_svc.files_from_form(form)
    else:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        payload = ParentSupportRequest(**data)
        subject = payload.subject.strip()
        message = payload.message.strip()
        topic_raw = payload.topic
        case_id = payload.case_id

    if not message:
        raise HTTPException(status_code=400, detail="Message required")

    case = None
    if case_id is not None:
        case = _parent_case_or_404(db, user, case_id)
    topic = ticket_esc.topic_from_str(topic_raw)
    ticket = SupportTicket(
        raised_by_user_id=user.id,
        case_id=case_id,
        topic=topic,
        subject=subject,
        body=message,
        status=TicketStatus.OPEN,
        product_module=case.product_module if case else None,
    )
    ticket_esc.assign_ticket(db, ticket, case)
    db.add(ticket)
    db.flush()
    msg = TicketMessage(ticket_id=ticket.id, author_user_id=user.id, body=message)
    db.add(msg)
    db.flush()
    try:
        await att_svc.save_attachments(db, ticket, user, files, message_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)


@router.post("/support/tickets/{ticket_id}/messages")
async def parent_ticket_reply(
    ticket_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.raised_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Ticket is closed")

    content_type = request.headers.get("content-type", "")
    files = []
    if "multipart/form-data" in content_type:
        form = await request.form()
        body = str(form.get("body") or "").strip()
        files = att_svc.files_from_form(form)
    else:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        body = ParentTicketMessageCreate(**data).body.strip()

    if not body:
        raise HTTPException(status_code=400, detail="Message required")
    msg = TicketMessage(ticket_id=ticket.id, author_user_id=user.id, body=body)
    db.add(msg)
    db.flush()
    try:
        await att_svc.save_attachments(db, ticket, user, files, message_id=msg.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from app.services import ticket_flow_service as ticket_flow

    ticket_flow.on_ticket_message(db, user, ticket)
    db.commit()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)


@router.post("/support/tickets/{ticket_id}/accept")
def parent_ticket_accept(
    ticket_id: int,
    payload: ParentTicketAcceptRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import ticket_flow_service as ticket_flow

    _require_parent(user)
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.raised_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        ticket_flow.close_ticket(
            db,
            user,
            ticket,
            note=payload.feedback,
            accept_resolution=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)


@router.post("/support/tickets/{ticket_id}/rate")
def parent_ticket_rate(
    ticket_id: int,
    payload: ParentTicketRateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.raised_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1–5")
    ticket.parent_satisfaction_rating = payload.rating
    if payload.feedback:
        ticket.parent_resolution_feedback = payload.feedback.strip()
    db.commit()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)


class ParentTicketEscalateRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/support/tickets/{ticket_id}/escalate")
def parent_ticket_escalate(
    ticket_id: int,
    payload: ParentTicketEscalateRequest = ParentTicketEscalateRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import ticket_flow_service as ticket_flow

    _require_parent(user)
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.raised_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        ticket_flow.escalate_ticket_for_user(db, user, ticket, reason=payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)


# ── Parent incident reporting ─────────────────────────────────────────────


class ParentIncidentCreate(BaseModel):
    case_id: Optional[int] = None
    primary_category: str
    subcategory: str
    what_happened: str
    priority: Optional[str] = None
    service_type: Optional[str] = None
    incident_at: Optional[datetime] = None
    location: Optional[str] = None
    immediate_action: Optional[str] = None
    child_safe: Optional[str] = None
    parent_informed: Optional[str] = None


class ParentIncidentMessageCreate(BaseModel):
    body: str


class ParentIncidentFlowNote(BaseModel):
    note: str = ""


class ParentIncidentEscalate(BaseModel):
    reason: str = ""


@router.get("/incidents")
def parent_list_incidents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_service as inc_svc

    incidents = db.scalars(
        select(Incident)
        .where(Incident.reported_by_user_id == user.id)
        .order_by(Incident.created_at.desc())
    ).all()
    result = []
    for inc in incidents:
        case = case_service.get_case(db, inc.case_id) if inc.case_id else None
        result.append(inc_svc.incident_to_list_dict(inc, case))
    return result


@router.get("/incidents/{incident_id}")
def parent_get_incident(
    incident_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_service as inc_svc

    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident or incident.reported_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(incident, case, user)


@router.post("/incidents", status_code=201)
def parent_create_incident(
    payload: ParentIncidentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_service as inc_svc
    from app.services import notification_service

    if payload.case_id is None:
        raise HTTPException(status_code=400, detail="Please select a child case")
    _parent_case_or_404(db, user, payload.case_id)

    try:
        incident = inc_svc.create_incident(
            db,
            reporter_user_id=user.id,
            reporter_role_names=user.role_names,
            case_id=payload.case_id,
            primary_category=payload.primary_category,
            subcategory=payload.subcategory,
            what_happened=payload.what_happened,
            priority=payload.priority,
            service_type=payload.service_type,
            incident_at=payload.incident_at,
            location=payload.location,
            immediate_action=payload.immediate_action,
            child_safe=payload.child_safe,
            parent_informed=payload.parent_informed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    assignee_name = "our team"
    if incident.assigned_to_user_id:
        u = db.get(User, incident.assigned_to_user_id)
        if u:
            assignee_name = u.full_name
    notification_service.create_notification(
        db,
        user_id=user.id,
        title="Incident submitted",
        body=f"{incident.ticket_code} submitted — {assignee_name} will review.",
        entity_type="incident",
        entity_id=incident.id,
    )
    if incident.assigned_to_user_id:
        notification_service.create_notification(
            db,
            user_id=incident.assigned_to_user_id,
            title=f"New incident: {incident.ticket_code}",
            body=incident.title,
            entity_type="incident",
            entity_id=incident.id,
        )

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    db.refresh(incident)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    detail = inc_svc.incident_to_detail_dict(incident, case)
    detail["confirmation"] = f"Incident {incident.ticket_code} submitted — {assignee_name} will review."
    return detail


@router.post("/incidents/{incident_id}/attachments", status_code=201)
async def parent_upload_incident_attachments(
    incident_id: int,
    request: Request,
    note: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_attachment_service as att_svc

    incident = db.get(Incident, incident_id)
    if not incident or incident.reported_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        saved = await att_svc.save_attachments(db, incident, user, files, note=note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="attach", entity_type="incident", entity_id=incident_id, **meta)
    db.commit()
    return {"attachments": [att_svc.attachment_to_dict(a) for a in saved]}


@router.get("/incidents/attachments/{attachment_id}/download")
def parent_download_incident_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_attachment_service as att_svc

    att = att_svc.get_attachment_or_404(db, attachment_id)
    incident = db.get(Incident, att.incident_id)
    if not incident or incident.reported_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return att_svc.download_response(att)


@router.post("/incidents/{incident_id}/messages", status_code=201)
def parent_add_incident_message(
    incident_id: int,
    payload: ParentIncidentMessageCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_service as inc_svc

    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident or incident.reported_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.add(IncidentMessage(
        incident_id=incident_id,
        author_user_id=user.id,
        body=payload.body.strip(),
    ))
    if incident.status in (IncidentStatus.ACTION_TAKEN, IncidentStatus.CLOSED):
        incident.status = IncidentStatus.IN_REVIEW
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="message", entity_type="incident", entity_id=incident_id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(incident, case, user)


@router.post("/incidents/{incident_id}/close")
def parent_close_incident(
    incident_id: int,
    payload: ParentIncidentFlowNote,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_flow_service as inc_flow
    from app.services import incident_service as inc_svc

    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident or incident.reported_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        inc_flow.close_incident(db, user, incident, note=payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="close", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(incident, case, user)


@router.post("/incidents/{incident_id}/escalate")
def parent_escalate_incident(
    incident_id: int,
    payload: ParentIncidentEscalate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import incident_flow_service as inc_flow
    from app.services import incident_service as inc_svc

    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident or incident.reported_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        inc_flow.escalate_incident(db, user, incident, reason=payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="escalate", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(incident, case, user)
