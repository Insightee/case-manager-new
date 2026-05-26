from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.db_errors import commit_or_http
from app.core.module_write import guard_clinical_case
from app.core.permissions import case_scope_check, require_mutation_permission, require_permission
from app.services import case_service
from app.core.report_constants import PROGRESS_SUB_CATEGORIES, REPORT_CATEGORIES
from app.models.report import MonthlyReport, ObservationReport, ReportCategory, ReportStatus
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
    SessionLogContextItem,
)
from app.services import case_service, parent_reports_service, report_service
from app.services import report_image_service, report_pdf_service, report_session_context_service
from app.services.report_image_service import sync_summary_from_body

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
    visibility = report.visibility_status or VisibilityStatus.INTERNAL_ONLY
    return MonthlyReportRead(
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code if case else None,
        child_name=case.child.full_name if case and case.child else None,
        therapist_user_id=report.therapist_user_id,
        month=report.month,
        status=report.status,
        summary=report.summary,
        body_html=report.body_html,
        plan_next_month=report.plan_next_month,
        category=report.category,
        sub_category=report.sub_category,
        report_date=report.report_date,
        reviewer_comment=report.reviewer_comment,
        visibility_status=visibility,
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
    report = MonthlyReport(
        case_id=payload.case_id,
        therapist_user_id=user.id,
        month=payload.month,
        summary=payload.summary,
        body_html=payload.body_html,
        plan_next_month=payload.plan_next_month,
        category=payload.category or ReportCategory.CLIENT_MONTHLY.value,
        sub_category=payload.sub_category,
        report_date=payload.report_date,
    )
    sync_summary_from_body(report)
    db.add(report)
    commit_or_http(db)
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
    sync_summary_from_body(report)
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.DRAFT
        report.reviewer_comment = None
    commit_or_http(db)
    db.refresh(report)
    return _report_read(db, report)


@router.get("/categories")
def report_categories():
    return {
        "categories": [{"id": k, "label": v} for k, v in REPORT_CATEGORIES],
        "progress_sub_categories": [{"id": k, "label": v} for k, v in PROGRESS_SUB_CATEGORIES],
    }


@router.post("/monthly/{report_id}/images")
async def upload_monthly_report_image(
    report_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    result = await report_image_service.save_report_image(db, user, "monthly", report_id, file)
    commit_or_http(db)
    return result


@router.get("/images/{image_id}")
def download_report_image(
    image_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    img = report_image_service.get_image_for_user(db, user, image_id)
    data, mime, filename = report_image_service.open_report_image_content(img)
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/monthly/{report_id}/session-context", response_model=list[SessionLogContextItem])
def monthly_report_session_context(
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
    rows = report_session_context_service.session_context_for_monthly_report(db, user, report)
    return rows


@router.get("/monthly/{report_id}/download")
def download_monthly_report_pdf(
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
    child_name = case.child.full_name if case.child else ""
    pdf = report_pdf_service.monthly_report_pdf(report, case.case_code, child_name)
    safe = (report.month or "report").replace(" ", "_")[:40]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{safe}.pdf"'},
    )


@router.get("/therapist/session-logs/export")
def therapist_session_logs_export(
    case_id: int = Query(...),
    month: Optional[str] = None,
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    try:
        csv_data = report_session_context_service.export_session_logs_csv(
            db, user, case_id=case_id, month=month
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=session_logs.csv"},
    )


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
    if not (report.month or "").strip():
        raise HTTPException(status_code=400, detail="Set the report month before submitting")
    has_body = (report.body_html or "").strip() or (report.summary or "").strip()
    if not has_body:
        raise HTTPException(status_code=400, detail="Add report content before submitting")
    report.status = ReportStatus.UNDER_REVIEW
    commit_or_http(db)
    return {"status": "under_review"}


@router.post("/monthly/{report_id}/approve")
def approve_report(
    report_id: int,
    payload: ReviewAction,
    request: Request,
    user: User = Depends(require_mutation_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if case:
        guard_clinical_case(user, case, db, feature="reports")
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
    user: User = Depends(require_mutation_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if case:
        guard_clinical_case(user, case, db, feature="reports")
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
        body_html=report.body_html,
        plan_next_month=report.plan_next_month,
        category=report.category,
        sub_category=report.sub_category,
        report_date=report.report_date,
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
        body_html=payload.body_html,
        plan_next_month=payload.plan_next_month,
        category=payload.category or ReportCategory.OBSERVATION.value,
        sub_category=payload.sub_category,
        report_date=payload.report_date,
    )
    if payload.body_html and not payload.content:
        report.content = report.body_html[:500]
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
    if data.get("body_html") and not report.content:
        report.content = (report.body_html or "")[:500]
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.DRAFT
    db.commit()
    db.refresh(report)
    return _observation_read(db, report)


@router.post("/observation/{report_id}/images")
async def upload_observation_report_image(
    report_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("monthly_report.create")),
    db: Session = Depends(get_db),
):
    result = await report_image_service.save_report_image(db, user, "observation", report_id, file)
    commit_or_http(db)
    return result


@router.get("/observation/{report_id}/download")
def download_observation_report_pdf(
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
    child_name = case.child.full_name if case.child else ""
    pdf = report_pdf_service.observation_report_pdf(report, case.case_code, child_name)
    safe = (report.title or "report").replace(" ", "_")[:40]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{safe}.pdf"'},
    )


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
