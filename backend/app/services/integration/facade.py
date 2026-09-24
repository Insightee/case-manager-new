"""Session-managing facade for MCP (and callers that must not open SQLAlchemy Sessions)."""
from __future__ import annotations

from typing import Any

from app.core.database import SessionLocal
from app.services.integration import auth_service, case_query, framework_query, ops_summary, report_query, session_summary
from app.services.integration.access import IntegrationPrincipal
from app.services.integration.errors import IntegrationError, UnauthorizedError


def _run(fn, *args, **kwargs):
    db = SessionLocal()
    try:
        result = fn(db, *args, **kwargs)
        db.commit()
        return result
    except IntegrationError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def principal_from_bearer(token: str) -> IntegrationPrincipal:
    db = SessionLocal()
    try:
        principal = auth_service.resolve_principal_from_token(db, token)
        return principal
    finally:
        db.close()


def list_authorised_reports(
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
    case_id: int | None = None,
    status: str | None = None,
    month: str | None = None,
    report_type: str | None = None,
) -> dict[str, Any]:
    return _run(
        report_query.list_reports,
        principal,
        page=page,
        page_size=page_size,
        case_id=case_id,
        status=status,
        month=month,
        report_type=report_type,
    )


def get_report(
    principal: IntegrationPrincipal,
    report_id: int,
    *,
    report_type: str = "monthly",
) -> dict[str, Any]:
    return _run(report_query.get_report, principal, report_id, report_type=report_type)


def get_case_summary(principal: IntegrationPrincipal, case_id: int) -> dict[str, Any]:
    return _run(case_query.get_case, principal, case_id)


def get_session_summary(principal: IntegrationPrincipal, case_id: int) -> dict[str, Any]:
    return _run(session_summary.get_session_summary, principal, case_id)


def list_pending_reporting(
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    return _run(report_query.list_pending_reporting, principal, page=page, page_size=page_size)


def get_anonymised_ops_summary(principal: IntegrationPrincipal) -> dict[str, Any]:
    return _run(ops_summary.get_anonymised_ops_summary, principal)


def list_goal_framework(principal: IntegrationPrincipal) -> dict[str, Any]:
    return _run(framework_query.list_goal_framework, principal)


def list_iep_framework(principal: IntegrationPrincipal) -> dict[str, Any]:
    return _run(framework_query.list_iep_framework, principal)


def bearer_from_authorization_header(header: str | None) -> str:
    if not header:
        raise UnauthorizedError("Not authenticated")
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise UnauthorizedError("Not authenticated")
    return parts[1].strip()
