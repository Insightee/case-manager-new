from __future__ import annotations

from typing import Optional

import csv
import io
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.config import settings
from app.core.database import get_db
from app.core.pagination import paginate_query, paginated_response
from app.schemas.pagination import PaginatedList
from app.core.module_access import (
    get_allowed_case_product_modules,
    get_user_features,
    modules_for_api,
    user_has_feature,
    validate_module_assignments,
)
from app.core.modules import ROLE_DEFAULT_MODULES, module_catalog_for_api
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.daily_log import DailyLog
from app.models.invoice import Invoice, InvoiceStatus
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import InviteToken, User
from app.schemas.therapist_profile import (
    TherapistProfileAdminCreate,
    TherapistProfileRead,
    TherapistProfileReview,
    TherapistProfileUpdate,
)
from app.schemas.therapist_review import (
    TherapistReviewSummary,
    TherapistReviewsResponse,
    TherapistSessionReviewRead,
)
from app.schemas.allotment import CaseAllotRequest, ChildCreate, FamilyCreate
from app.schemas.user import InviteCreate, UserCreate, UserRead, UserUpdate
from app.services import auth_service, case_service, log_service, therapist_profile_service as profile_svc
from app.services import therapist_review_service as review_svc
from app.core.permissions import RoleName

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_dashboard_user(user: User = Depends(get_current_user)) -> User:
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


def _case_filter(allowed: set[str] | None):
    if allowed is None:
        return []
    if not allowed:
        return [Case.id == -1]
    return [Case.product_module.in_(allowed)]


@router.get("/modules")
def list_product_modules(user: User = Depends(require_permission("user.manage"))):
    return {
        "modules": module_catalog_for_api(),
        "role_defaults": ROLE_DEFAULT_MODULES,
    }


@router.get("/dashboard/summary")
def dashboard_summary(
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    allowed_cases = get_allowed_case_product_modules(user)
    case_filters = _case_filter(allowed_cases)

    def _count_case_status(status: CaseStatus) -> int:
        stmt = select(func.count()).select_from(Case).where(Case.status == status, *case_filters)
        return db.scalar(stmt) or 0

    pending_stmt = (
        select(Case.id, Case.case_code, Case.service_type, Case.status, Child.first_name, Child.last_name)
        .join(Child, Case.child_id == Child.id)
        .where(Case.status == CaseStatus.PENDING_ALLOTMENT, *case_filters)
        .order_by(Case.created_at.desc())
        .limit(6)
    )
    pending_rows = db.execute(pending_stmt).all()

    report_stmt = (
        select(
            MonthlyReport.id,
            MonthlyReport.case_id,
            MonthlyReport.month,
            MonthlyReport.status,
            Case.case_code,
            Child.first_name,
            Child.last_name,
        )
        .join(Case, MonthlyReport.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .where(MonthlyReport.status == ReportStatus.UNDER_REVIEW, *case_filters)
        .order_by(MonthlyReport.updated_at.desc())
        .limit(6)
    )
    report_rows = db.execute(report_stmt).all() if user_has_feature(user, "reports") else []

    invoice_rows = []
    invoices_pending = 0
    if user_has_feature(user, "invoices"):
        scoped_therapist_ids = None
        if allowed_cases is not None:
            if not allowed_cases:
                scoped_therapist_ids = []
            else:
                scoped_therapist_ids = list(
                    db.scalars(
                        select(CaseAssignment.therapist_user_id)
                        .join(Case, CaseAssignment.case_id == Case.id)
                        .where(
                            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                            Case.product_module.in_(allowed_cases),
                        )
                        .distinct()
                    ).all()
                )
        invoice_base = select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        if scoped_therapist_ids is not None:
            if not scoped_therapist_ids:
                invoice_base = invoice_base.where(Invoice.id == -1)
            else:
                invoice_base = invoice_base.where(Invoice.therapist_user_id.in_(scoped_therapist_ids))
        invoice_rows = list(
            db.scalars(invoice_base.order_by(Invoice.updated_at.desc()).limit(6)).all()
        )
        count_stmt = select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        if scoped_therapist_ids is not None:
            if not scoped_therapist_ids:
                count_stmt = count_stmt.where(Invoice.id == -1)
            else:
                count_stmt = count_stmt.where(Invoice.therapist_user_id.in_(scoped_therapist_ids))
        invoices_pending = db.scalar(count_stmt) or 0

    ticket_filters = []
    if allowed_cases is not None:
        if allowed_cases:
            ticket_filters.append(
                or_(SupportTicket.product_module.in_(allowed_cases), SupportTicket.product_module.is_(None))
            )
        else:
            ticket_filters.append(SupportTicket.id == -1)

    ticket_rows = []
    open_tickets = 0
    if user_has_feature(user, "tickets"):
        ticket_rows = list(
            db.scalars(
                select(SupportTicket)
                .where(SupportTicket.status == TicketStatus.OPEN, *ticket_filters)
                .order_by(SupportTicket.updated_at.desc())
                .limit(6)
            ).all()
        )
        open_tickets = (
            db.scalar(
                select(func.count()).select_from(SupportTicket).where(SupportTicket.status == TicketStatus.OPEN, *ticket_filters)
            )
            or 0
        )

    reports_in_review = 0
    if user_has_feature(user, "reports"):
        reports_in_review = (
            db.scalar(
                select(func.count())
                .select_from(MonthlyReport)
                .join(Case, MonthlyReport.case_id == Case.id)
                .where(MonthlyReport.status == ReportStatus.UNDER_REVIEW, *case_filters)
            )
            or 0
        )

    return {
        "open_cases": _count_case_status(CaseStatus.ACTIVE),
        "pending_allotment": _count_case_status(CaseStatus.PENDING_ALLOTMENT),
        "suspended_cases": _count_case_status(CaseStatus.SUSPENDED),
        "closed_cases": _count_case_status(CaseStatus.CLOSED),
        "total_cases": db.scalar(select(func.count()).select_from(Case).where(*case_filters)) or 0,
        "reports_in_review": reports_in_review,
        "invoices_pending": invoices_pending,
        "open_tickets": open_tickets,
        "status_breakdown": {
            "ACTIVE": _count_case_status(CaseStatus.ACTIVE),
            "PENDING_ALLOTMENT": _count_case_status(CaseStatus.PENDING_ALLOTMENT),
            "SUSPENDED": _count_case_status(CaseStatus.SUSPENDED),
            "CLOSED": _count_case_status(CaseStatus.CLOSED),
        },
        "pending_allotment_queue": [
            {
                "id": row.id,
                "case_code": row.case_code,
                "child_name": f"{row.first_name} {row.last_name}".strip(),
                "service_type": row.service_type,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            }
            for row in pending_rows
        ],
        "reports_queue": [
            {
                "id": row.id,
                "case_id": row.case_id,
                "month": row.month,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "case_code": row.case_code,
                "child_name": f"{row.first_name} {row.last_name}".strip(),
            }
            for row in report_rows
        ],
        "invoices_queue": [
            {
                "id": inv.id,
                "month": inv.month,
                "amount_inr": float(inv.amount_inr),
                "status": inv.status.value,
                "therapist_user_id": inv.therapist_user_id,
            }
            for inv in invoice_rows
        ],
        "tickets_queue": [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value,
                "product_module": t.product_module,
            }
            for t in ticket_rows
        ],
    }


@router.get("/session-logs/export")
def export_session_logs(
    therapist_user_id: Optional[int] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    logs = log_service.list_logs(db, therapist_user_id=therapist_user_id, month=month, product_module=product_module)
    scoped = []
    for log in logs:
        if not log.session:
            continue
        case = case_service.get_case(db, log.session.case_id)
        if case and case_scope_check(db, user, case):
            scoped.append(log)
    logs = scoped
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "log_id", "session_id", "case_id", "attendance", "session_notes", "activities",
        "goals", "observations", "follow_ups", "parent_notes", "scheduled_date",
        "start_time", "end_time", "actual_start", "actual_end", "submitted_at", "approval_status", "late_addition",
    ])
    for log in logs:
        s = log.session
        writer.writerow([
            log.id,
            log.session_id,
            s.case_id if s else "",
            log.attendance_status,
            log.session_notes or "",
            log.activities_done or "",
            log.goals_addressed or "",
            log.observations or "",
            log.follow_ups or "",
            log.parent_notes or "",
            s.scheduled_date.isoformat() if s else "",
            s.start_time.isoformat() if s and s.start_time else "",
            s.end_time.isoformat() if s and s.end_time else "",
            s.actual_start_at.isoformat() if s and s.actual_start_at else "",
            s.actual_end_at.isoformat() if s and s.actual_end_at else "",
            log.submitted_at.isoformat() if log.submitted_at else "",
            log.approval_status.value,
            log.late_addition,
        ])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=session_logs.csv"})


@router.get("/users", response_model=PaginatedList[UserRead])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    stmt = select(User).order_by(User.email)
    users, total = paginate_query(db, stmt, page=page, page_size=page_size)
    items = [
        UserRead(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            roles=u.role_names,
            region=u.region,
            module_assignments=u.module_assignments or [],
        )
        for u in users
    ]
    return PaginatedList[UserRead](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role_names is not None:
        from app.models.role import Role

        roles = db.scalars(select(Role).where(Role.name.in_(payload.role_names))).all()
        target.roles = list(roles)
    if payload.module_assignments is not None:
        target.module_assignments = validate_module_assignments(target.role_names, payload.module_assignments)
    if payload.region is not None:
        target.region = payload.region
    if payload.is_active is not None:
        target.is_active = payload.is_active
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=current.id, action="update", entity_type="user", entity_id=user_id, **meta)
    db.commit()
    db.refresh(target)
    return UserRead(
        id=target.id,
        email=target.email,
        full_name=target.full_name,
        is_active=target.is_active,
        roles=target.role_names,
        region=target.region,
        module_assignments=target.module_assignments or [],
    )


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    modules = validate_module_assignments(payload.role_names, payload.module_assignments)
    new_user = auth_service.create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role_names=payload.role_names,
        region=payload.region,
        module_assignments=modules,
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="user", entity_id=new_user.id, **meta)
    db.commit()
    db.refresh(new_user)
    return UserRead(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        is_active=new_user.is_active,
        roles=new_user.role_names,
        region=new_user.region,
        module_assignments=new_user.module_assignments or [],
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    request: Request,
    current: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=current.id, action="deactivate", entity_type="user", entity_id=user_id, **meta)
    db.commit()


@router.post("/therapists/invite")
def invite_therapist(
    payload: InviteCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    token = secrets.token_urlsafe(32)
    modules = validate_module_assignments([payload.role_name], payload.module_assignments)
    invite = InviteToken(
        email=payload.email.lower(),
        role_name=payload.role_name,
        module_assignments=modules,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=user.id,
    )
    db.add(invite)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="invite", entity_type="invite_token", entity_id=invite.id, **meta)
    db.commit()
    url = f"{settings.frontend_url}/invite/{token}"
    print(f"[DEV INVITE] {payload.email} -> {url}")
    return {"invite_url": url, "email": payload.email, "expires_at": invite.expires_at.isoformat()}


@router.get("/therapist-profiles", response_model=list[TherapistProfileRead])
def list_therapist_profiles(
    status: Optional[str] = None,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    st = TherapistProfileStatus(status) if status else None
    profiles = profile_svc.list_profiles(db, st)
    result = []
    for p in profiles:
        u = db.get(User, p.user_id)
        result.append(TherapistProfileRead(**profile_svc.profile_to_dict(p, u)))
    return result


@router.post("/therapist-profiles", response_model=TherapistProfileRead, status_code=status.HTTP_201_CREATED)
def admin_create_therapist_profile(
    payload: TherapistProfileAdminCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if RoleName.THERAPIST.value not in target.role_names:
        raise HTTPException(status_code=400, detail="User is not a therapist")
    existing = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == payload.user_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists for this therapist")
    profile = TherapistProfile(user_id=payload.user_id)
    profile_svc.apply_profile_fields(profile, payload.model_dump(exclude={"user_id", "status"}))
    try:
        st = TherapistProfileStatus(payload.status or "APPROVED")
    except ValueError:
        st = TherapistProfileStatus.APPROVED
    profile.status = st
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    db.add(profile)
    db.flush()
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="therapist_profile", entity_id=profile.id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, target))


@router.patch("/therapist-profiles/{profile_id}", response_model=TherapistProfileRead)
def admin_update_therapist_profile(
    profile_id: int,
    payload: TherapistProfileUpdate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile_svc.apply_profile_fields(profile, payload.model_dump(exclude_unset=True))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    target = db.get(User, profile.user_id)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, target))


@router.get("/therapist-profiles/{user_id}/reviews", response_model=TherapistReviewsResponse)
def admin_therapist_reviews(
    user_id: int,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target or RoleName.THERAPIST.value not in target.role_names:
        raise HTTPException(status_code=404, detail="Therapist not found")
    rows = review_svc.list_therapist_reviews(db, user_id)
    summary = review_svc.review_summary(db, user_id)
    return TherapistReviewsResponse(
        summary=TherapistReviewSummary(**summary),
        reviews=[TherapistSessionReviewRead(**r) for r in rows],
    )


@router.post("/therapist-profiles/{profile_id}/approve", response_model=TherapistProfileRead)
def admin_approve_profile(
    profile_id: int,
    payload: TherapistProfileReview,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.status = TherapistProfileStatus.APPROVED
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    if payload.admin_note:
        profile.admin_note = payload.admin_note
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="approve_profile", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, db.get(User, profile.user_id)))


@router.post("/therapist-profiles/{profile_id}/pause", response_model=TherapistProfileRead)
def admin_pause_profile(
    profile_id: int,
    payload: TherapistProfileReview,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.status = TherapistProfileStatus.PAUSED
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    if payload.admin_note:
        profile.admin_note = payload.admin_note
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="pause_profile", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, db.get(User, profile.user_id)))


@router.post("/therapist-profiles/{profile_id}/resume", response_model=TherapistProfileRead)
def admin_resume_profile(
    profile_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.status = TherapistProfileStatus.APPROVED
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="resume_profile", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, db.get(User, profile.user_id)))


@router.delete("/therapist-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_therapist_profile(
    profile_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="delete", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.delete(profile)
    db.commit()


# --- Case allotment & families ---


@router.get("/cases/next-code")
def admin_next_case_code(
    product_module: str,
    user: User = Depends(require_permission("case.create")),
    db: Session = Depends(get_db),
):
    from app.services import case_code_service

    code = case_code_service.generate_case_code(db, product_module)
    return {"case_code": code, "preview": case_code_service.preview_case_code(product_module)}


@router.get("/allotment/therapists")
def admin_allotment_therapists(
    product_module: str,
    search: Optional[str] = None,
    approved_only: bool = True,
    user: User = Depends(require_permission("case.assign")),
    db: Session = Depends(get_db),
):
    from app.services import allotment_service

    return allotment_service.list_allotment_therapists(db, user, product_module, search, approved_only)


@router.get("/families")
def admin_list_families(
    search: Optional[str] = None,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    return family_admin_service.list_families(db, search)


@router.post("/children", status_code=status.HTTP_201_CREATED)
def admin_create_child(
    payload: ChildCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    child = family_admin_service.create_child(
        db, payload.first_name, payload.last_name, payload.date_of_birth
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="child", entity_id=child.id, **meta)
    db.commit()
    return {"id": child.id, "fullName": child.full_name}


@router.post("/families", status_code=status.HTTP_201_CREATED)
def admin_create_family(
    payload: FamilyCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    try:
        result = family_admin_service.create_family(
            db,
            parent_email=payload.parent_email,
            parent_full_name=payload.parent_full_name,
            parent_phone=payload.parent_phone,
            child_first=payload.child.first_name,
            child_last=payload.child.last_name,
            child_dob=payload.child.date_of_birth,
            send_invite=payload.send_invite,
            password=payload.password,
            created_by_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create_family", entity_type="child", entity_id=result["childId"], **meta)
    db.commit()
    if result.get("inviteUrl"):
        print(f"[DEV INVITE] {payload.parent_email} -> {result['inviteUrl']}")
    return result


@router.post("/families/{parent_user_id}/invite")
def admin_invite_parent(
    parent_user_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    try:
        url = family_admin_service.issue_parent_invite(db, parent_user_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="invite", entity_type="user", entity_id=parent_user_id, **meta)
    db.commit()
    print(f"[DEV INVITE] parent user {parent_user_id} -> {url}")
    return {"invite_url": url}


@router.post("/families/link")
def admin_link_parent_child(
    parent_user_id: int = Query(...),
    child_id: int = Query(...),
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.models.parent import ParentGuardian
    from app.models.child import Child

    pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent_user_id)).first()
    if not pg:
        pg = ParentGuardian(user_id=parent_user_id)
        db.add(pg)
        db.flush()
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if child not in pg.children:
        pg.children.append(child)
    from app.services.parent_service import dedupe_parent_child_links

    dedupe_parent_child_links(db, pg.id)
    db.commit()
    return {"status": "linked"}


@router.post("/cases/allot", status_code=status.HTTP_201_CREATED)
def admin_allot_case(
    payload: CaseAllotRequest,
    request: Request,
    user: User = Depends(require_permission("case.create")),
    db: Session = Depends(get_db),
):
    from app.services import allotment_service

    try:
        result = allotment_service.allot_case(db, user, payload.model_dump())
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="allot",
        entity_type="case",
        entity_id=result["case"]["id"],
        **meta,
    )
    db.commit()
    return result


@router.get("/invites")
def admin_list_invites(
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(InviteToken)
        .where(InviteToken.used_at.is_(None), InviteToken.expires_at > now)
        .order_by(InviteToken.expires_at.desc())
    ).all()
    return [
        {
            "id": inv.id,
            "email": inv.email,
            "role_name": inv.role_name,
            "module_assignments": inv.module_assignments or [],
            "expires_at": inv.expires_at.isoformat(),
            "invite_url": f"{settings.frontend_url}/invite/{inv.token}",
            "pending_slot_id": (inv.invite_metadata or {}).get("pending_slot_id"),
            "client_name": (inv.invite_metadata or {}).get("client_name"),
            "therapist_user_id": (inv.invite_metadata or {}).get("therapist_user_id"),
        }
        for inv in rows
    ]


@router.post("/invites")
def admin_create_invite(
    payload: InviteCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    return invite_therapist(payload, request, user, db)
