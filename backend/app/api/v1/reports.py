from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import case_scope_check, require_permission
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.review import ReviewDecision
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.pagination import PaginatedList
from app.schemas.report import (
    MonthlyReportCreate,
    MonthlyReportRead,
    MonthlyReportUpdate,
    ObservationReportCreate,
    ObservationReportRead,
    ObservationReportUpdate,
    ReviewAction,
)
from app.services import case_service, parent_reports_service, report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=PaginatedList[MonthlyReportRead])
def list_monthly_reports(
    status: Optional[ReportStatus] = None,
    case_id: Optional[int] = None,
    month: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports, meta = report_service.list_monthly_reports(
        db,
        user,
        status=status,
        case_id=case_id,
        month=month,
        search=search,
        page=page,
        page_size=page_size,
    )
    items = [_report_read(db, r) for r in reports]
    return PaginatedList[MonthlyReportRead](
        items=items,
        total=meta["total"],
        page=meta["page"],
        page_size=meta["page_size"],
        pages=meta["pages"],
    )


def _report_read(db: Session, report: MonthlyReport) -> MonthlyReportRead:
    case = case_service.get_case(db, report.case_id)
    return MonthlyReportRead(
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code if case else None,
        child_name=case.child.full_name if case and case.child else None,
        therapist_user_id=report.therapist_user_id,
        month=report.month,
        status=report.status,
        summary=report.summary,
        reviewer_comment=report.reviewer_comment,
        visibility_status=report.visibility_status,
        parent_review_status=report.parent_review_status,
        parent_feedback=report.parent_feedback,
        parent_reviewed_at=report.parent_reviewed_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("/monthly/{report_id}", response_model=MonthlyReportRead)
def get_monthly_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_read(db, report)


@router.post("/monthly", response_model=MonthlyReportRead, status_code=status.HTTP_201_CREATED)
def create_monthly_report(
    payload: MonthlyReportCreate,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, payload.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    report = MonthlyReport(case_id=payload.case_id, therapist_user_id=user.id, month=payload.month, summary=payload.summary)
    db.add(report)
    db.commit()
    db.refresh(report)
    return _report_read(db, report)


@router.patch("/monthly/{report_id}", response_model=MonthlyReportRead)
def update_monthly_report(
    report_id: int,
    payload: MonthlyReportUpdate,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case) or report.therapist_user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Only draft or rejected reports can be edited")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(report, key, value)
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.DRAFT
        report.reviewer_comment = None
    db.commit()
    db.refresh(report)
    return _report_read(db, report)


@router.post("/monthly/{report_id}/submit")
def submit_monthly_report(
    report_id: int,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case) or report.therapist_user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Report cannot be submitted in its current state")
    if not (report.summary or "").strip():
        raise HTTPException(status_code=400, detail="Add a summary before submitting")
    report.status = ReportStatus.UNDER_REVIEW
    db.commit()
    return {"status": "under_review"}


@router.post("/monthly/{report_id}/approve")
def approve_report(
    report_id: int,
    payload: ReviewAction,
    request: Request,
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report_service.review_monthly_report(
        db, report, user.id, ReviewDecision.APPROVE, payload.comment, payload.visibility_status
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="approve", entity_type="monthly_report", entity_id=report.id, **meta)
    db.commit()
    return {"status": "approved"}


@router.post("/monthly/{report_id}/reject")
def reject_report(
    report_id: int,
    payload: ReviewAction,
    request: Request,
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report_service.review_monthly_report(db, report, user.id, ReviewDecision.REJECT, payload.comment, None)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="reject", entity_type="monthly_report", entity_id=report.id, **meta)
    db.commit()
    return {"status": "rejected"}


@router.post("/monthly/{report_id}/resend-to-parent")
def resend_report_to_parent(
    report_id: int,
    request: Request,
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    parent_reports_service.resend_to_parent(db, report)
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="resend_to_parent",
        entity_type="monthly_report",
        entity_id=report.id,
        **meta,
    )
    db.commit()
    return {"status": "pending_parent_review"}


def _observation_read(db: Session, report: ObservationReport) -> ObservationReportRead:
    case = case_service.get_case(db, report.case_id)
    return ObservationReportRead(
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code if case else None,
        child_name=case.child.full_name if case and case.child else None,
        therapist_user_id=report.therapist_user_id,
        title=report.title,
        status=report.status,
        content=report.content,
        visibility_status=report.visibility_status,
        created_at=report.created_at,
    )


@router.get("/observation", response_model=PaginatedList[ObservationReportRead])
def list_observation_reports(
    status: Optional[ReportStatus] = None,
    case_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports, meta = report_service.list_observation_reports(
        db,
        user,
        status=status,
        case_id=case_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    items = [_observation_read(db, r) for r in reports]
    return PaginatedList[ObservationReportRead](
        items=items,
        total=meta["total"],
        page=meta["page"],
        page_size=meta["page_size"],
        pages=meta["pages"],
    )


@router.get("/observation/{report_id}", response_model=ObservationReportRead)
def get_observation_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.get(ObservationReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Report not found")
    return _observation_read(db, report)


@router.post("/observation", response_model=ObservationReportRead, status_code=status.HTTP_201_CREATED)
def create_observation_report(
    payload: ObservationReportCreate,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, payload.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    report = ObservationReport(
        case_id=payload.case_id,
        therapist_user_id=user.id,
        title=payload.title.strip(),
        content=payload.content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _observation_read(db, report)


@router.patch("/observation/{report_id}", response_model=ObservationReportRead)
def update_observation_report(
    report_id: int,
    payload: ObservationReportUpdate,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    report = db.get(ObservationReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case) or report.therapist_user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Only draft or rejected reports can be edited")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(report, key, value)
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.DRAFT
    db.commit()
    db.refresh(report)
    return _observation_read(db, report)


@router.post("/observation/{report_id}/submit")
def submit_observation_report(
    report_id: int,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    report = db.get(ObservationReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case) or report.therapist_user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Report cannot be submitted in its current state")
    if not (report.title or "").strip():
        raise HTTPException(status_code=400, detail="Title is required")
    report.status = ReportStatus.UNDER_REVIEW
    db.commit()
    return {"status": "under_review"}
