"""External integration API (machine principals). Writes are structured signals only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps_integration import get_integration_principal, get_request_meta, raise_integration_http
from app.core.config import settings
from app.core.database import get_db
from app.schemas.integration import (
    IntegrationSignalCreate,
    IntegrationTherapistProfileCreate,
    IntegrationTokenRequest,
    IntegrationTokenResponse,
)
from app.services.integration import (
    auth_service,
    case_query,
    framework_query,
    ops_summary,
    profile_directory,
    report_query,
    session_summary,
    signal_inbox,
)
from app.services.integration.access import IntegrationPrincipal
from app.services.integration.errors import IntegrationError, ValidationError

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/oauth/token", response_model=IntegrationTokenResponse)
def issue_token(
    payload: IntegrationTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        if payload.grant_type != "client_credentials":
            raise ValidationError("Only grant_type=client_credentials is supported.")
        token, expires_in, client = auth_service.authenticate_client_credentials(
            db,
            public_client_id=payload.client_id,
            client_secret=payload.client_secret,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        return IntegrationTokenResponse(
            access_token=token,
            expires_in=expires_in,
            scope=" ".join(client.scopes),
        )
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/cases")
def list_cases(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1),
    status: str | None = None,
    product_module: str | None = None,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        page_size = min(page_size, settings.integration_max_page_size)
        result = case_query.list_cases(
            db,
            principal,
            page=page,
            page_size=page_size,
            status=status,
            product_module=product_module,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/cases/{case_id}")
def get_case(
    case_id: int,
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = case_query.get_case(
            db,
            principal,
            case_id,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/cases/{case_id}/session-summary")
def case_session_summary(
    case_id: int,
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = session_summary.get_session_summary(
            db,
            principal,
            case_id,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/reports")
def list_reports(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1),
    case_id: int | None = None,
    status: str | None = None,
    month: str | None = None,
    report_type: str | None = Query("all"),
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        page_size = min(page_size, settings.integration_max_page_size)
        result = report_query.list_reports(
            db,
            principal,
            page=page,
            page_size=page_size,
            case_id=case_id,
            status=status,
            month=month,
            report_type=report_type,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/reports/{report_id}")
def get_report(
    report_id: int,
    request: Request,
    report_type: str = Query("monthly"),
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = report_query.get_report(
            db,
            principal,
            report_id,
            report_type=report_type,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/reporting/pending")
def pending_reporting(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1),
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        page_size = min(page_size, settings.integration_max_page_size)
        result = report_query.list_pending_reporting(
            db,
            principal,
            page=page,
            page_size=page_size,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/ops/summary")
def ops_summary_endpoint(
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = ops_summary.get_anonymised_ops_summary(
            db,
            principal,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/goals")
def list_goals(
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = framework_query.list_goal_framework(
            db,
            principal,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/iep")
def list_iep(
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = framework_query.list_iep_framework(
            db,
            principal,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/v1/therapist-profiles")
def list_therapist_profiles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1),
    status: str | None = None,
    q: str | None = None,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        page_size = min(page_size, settings.integration_max_page_size)
        result = profile_directory.list_profiles(
            db,
            principal,
            page=page,
            page_size=page_size,
            status=status,
            q=q,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.post("/v1/therapist-profiles", status_code=201)
def create_therapist_profile(
    payload: IntegrationTherapistProfileCreate,
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        result = profile_directory.create_profile(
            db,
            principal,
            payload.model_dump(exclude_unset=True),
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return result
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.post("/v1/signals", status_code=201)
def submit_signal(
    payload: IntegrationSignalCreate,
    request: Request,
    principal: IntegrationPrincipal = Depends(get_integration_principal),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        row = signal_inbox.submit_signal(
            db,
            principal,
            case_id=payload.case_id,
            domain=payload.domain,
            signal_key=payload.signal_key,
            level=payload.level,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
        )
        db.commit()
        return {
            "id": row.id,
            "case_id": row.case_id,
            "domain": row.domain,
            "signal_key": row.signal_key,
            "level": row.level,
            "status": row.status,
        }
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)
