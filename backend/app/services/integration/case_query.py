"""Masked case reads for integration principals."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import log_audit
from app.core.config import settings
from app.core.pagination import normalize_pagination, paginate_query, paginated_response
from app.models.case import Case
from app.services.integration.access import (
    IntegrationPrincipal,
    filter_to_granted_cases,
    require_case_grant,
    require_scope,
)
from app.services.integration.dto_masking import mask_case
from app.services.integration.errors import NotFoundError, ValidationError
from app.services.integration.rate_limit import check_rate_limit


def list_cases(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    product_module: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "cases:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    allowed = filter_to_granted_cases(db, principal, None)
    page, page_size = normalize_pagination(page, page_size, settings.integration_max_page_size)
    if not allowed:
        log_audit(
            db,
            actor_user_id=None,
            integration_client_id=principal.client_id,
            action="integration.cases_list",
            entity_type="case",
            entity_id=None,
            new_value={"total": 0, "page": page},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return paginated_response([], 0, page, page_size)

    stmt = (
        select(Case)
        .where(Case.id.in_(allowed))
        .options(selectinload(Case.child))
        .order_by(Case.id.desc())
    )
    if status:
        from app.models.case import CaseStatus

        try:
            status_enum = CaseStatus(status)
        except ValueError as exc:
            raise ValidationError("Invalid case status filter.") from exc
        stmt = stmt.where(Case.status == status_enum)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    rows, total = paginate_query(db, stmt, page=page, page_size=page_size, max_page_size=settings.integration_max_page_size)
    items = [mask_case(c, getattr(c, "child", None)) for c in rows]
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.cases_list",
        entity_type="case",
        entity_id=None,
        new_value={"total": total, "page": page, "page_size": page_size},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return paginated_response(items, total, page, page_size)


def get_case(
    db: Session,
    principal: IntegrationPrincipal,
    case_id: int,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "cases:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    require_case_grant(db, principal, case_id)
    case = db.scalars(
        select(Case).where(Case.id == case_id).options(selectinload(Case.child))
    ).first()
    if not case:
        raise NotFoundError("Case not found")
    payload = mask_case(case, getattr(case, "child", None))
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.case_read",
        entity_type="case",
        entity_id=case_id,
        case_id=case_id,
        new_value={"case_id": case_id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload
