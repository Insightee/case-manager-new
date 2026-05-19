from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.address import ServiceAddressUpdate
from app.schemas.daily_log import ParentSessionLogRead
from app.schemas.notification import NotificationRead
from app.services import address_service, notification_service, parent_service, slot_calendar_service

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


@router.get("/cases")
def parent_cases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    return parent_service.list_parent_cases(db, user)


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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    case_stmt = select(Case).where(Case.child_id.in_(child_ids))
    if case_id is not None:
        _parent_case_or_404(db, user, case_id)
        case_stmt = case_stmt.where(Case.id == case_id)
    cases = {c.id: c for c in db.scalars(case_stmt).all()}
    if not cases:
        return []
    logs = db.scalars(
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
        .order_by(DailyLog.submitted_at.desc())
    ).all()
    result = []
    for log in logs:
        s = log.session
        if not s:
            continue
        case = cases.get(s.case_id)
        therapist = db.get(User, s.therapist_user_id)
        result.append(
            ParentSessionLogRead(
                id=log.id,
                case_id=s.case_id,
                case_code=case.case_code if case else None,
                child_name=case.child.full_name if case and case.child else None,
                therapist_name=therapist.full_name if therapist else None,
                scheduled_date=s.scheduled_date,
                start_time=s.start_time.isoformat() if s.start_time else None,
                end_time=s.end_time.isoformat() if s.end_time else None,
                actual_start_at=s.actual_start_at,
                actual_end_at=s.actual_end_at,
                attendance_status=log.attendance_status,
                activities_done=log.activities_done,
                goals_addressed=log.goals_addressed,
                follow_ups=log.follow_ups,
                parent_notes=log.parent_notes,
                submitted_at=log.submitted_at,
            )
        )
    return result


@router.get("/reports")
def parent_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    cases = db.scalars(select(Case).where(Case.child_id.in_(child_ids))).all() if child_ids else []
    case_ids = [c.id for c in cases]
    reports = db.scalars(
        select(MonthlyReport).where(
            MonthlyReport.case_id.in_(case_ids),
            MonthlyReport.visibility_status.in_(PARENT_VISIBLE),
            MonthlyReport.status == ReportStatus.PUBLISHED,
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "caseId": next((c.case_code for c in cases if c.id == r.case_id), ""),
            "caseDbId": r.case_id,
            "childName": next((c.child.full_name for c in cases if c.id == r.case_id and c.child), ""),
            "month": r.month,
            "status": "approved",
            "summary": r.summary,
        }
        for r in reports
    ]


@router.get("/reports/{report_id}")
def parent_report_detail(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_parent(user)
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = _parent_case_or_404(db, user, report.case_id)
    if report.visibility_status not in PARENT_VISIBLE or report.status != ReportStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": str(report.id),
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "month": report.month,
        "status": "approved",
        "summary": report.summary,
        "createdAt": report.created_at.isoformat() if report.created_at else None,
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
        case = db.get(Case, sl.case_id) if sl.case_id else None
        therapist = db.get(User, sl.therapist_user_id)
        result.append(
            {
                "id": sl.id,
                "caseId": case.case_code if case else None,
                "caseDbId": sl.case_id,
                "childName": case.child.full_name if case and case.child else None,
                "therapistName": therapist.full_name if therapist else None,
                "slotDate": sl.slot_date.isoformat(),
                "startTime": sl.start_time.isoformat(),
                "endTime": sl.end_time.isoformat(),
            }
        )
    return result


@router.post("/appointments/{slot_id}/cancel")
def parent_cancel_appointment(
    slot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    slot = db.get(TherapistSlot, slot_id)
    if not slot or slot.status != SlotStatus.BOOKED or not slot.case_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _parent_case_or_404(db, user, slot.case_id)
    if slot.booked_by_user_id and slot.booked_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot cancel this appointment")
    slot_calendar_service.cancel_booking(db, slot_id, therapist_user_id=slot.therapist_user_id)
    db.commit()
    return {"status": "cancelled"}


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


@router.post("/support-requests")
def parent_support(
    payload: ParentSupportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_parent(user)
    if payload.case_id is not None:
        _parent_case_or_404(db, user, payload.case_id)
    ticket = SupportTicket(
        raised_by_user_id=user.id,
        case_id=payload.case_id,
        subject=payload.subject,
        body=payload.message,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    db.commit()
    return {"id": ticket.id, "status": "open"}
