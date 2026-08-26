"""Masked report reads and pending-reporting queues for integrations."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.config import settings
from app.core.pagination import normalize_pagination, paginated_response
from app.models.case import Case, CaseStatus
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.services.integration.access import (
    IntegrationPrincipal,
    filter_to_granted_cases,
    require_case_grant,
    require_scope,
)
from app.services.integration.dto_masking import mask_monthly_report, mask_observation_report
from app.services.integration.errors import NotFoundError, ValidationError
from app.services.integration.rate_limit import check_rate_limit

_ALLOWED_REPORT_STATUSES = {s.value for s in ReportStatus}


def _parse_status(raw: str | None) -> ReportStatus | None:
    if raw is None or raw == "":
        return None
    value = str(raw).strip().upper()
    if value not in _ALLOWED_REPORT_STATUSES:
        raise ValidationError("Invalid report status filter.")
    return ReportStatus(value)


def _case_code_map(db: Session, case_ids: set[int]) -> dict[int, str]:
    if not case_ids:
        return {}
    rows = db.execute(select(Case.id, Case.case_code).where(Case.id.in_(case_ids))).all()
    return {int(r[0]): str(r[1]) for r in rows}


def list_reports(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
    case_id: int | None = None,
    status: str | None = None,
    month: str | None = None,
    report_type: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "reports:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    page, page_size = normalize_pagination(page, page_size, settings.integration_max_page_size)
    status_enum = _parse_status(status)
    if month is not None and month != "":
        if len(month) > 32:
            raise ValidationError("Invalid month filter.")
    rtype = (report_type or "all").strip().lower()
    if rtype not in {"all", "monthly", "observation"}:
        raise ValidationError("report_type must be all, monthly, or observation.")

    if case_id is not None:
        require_case_grant(db, principal, case_id)
        allowed = {case_id}
    else:
        allowed = filter_to_granted_cases(db, principal, None)

    if not allowed:
        return paginated_response([], 0, page, page_size)

    items: list[dict[str, Any]] = []
    codes = _case_code_map(db, allowed)

    # Fetch both types then merge/sort for a unified list (bounded by grants + page).
    monthly_rows: list[MonthlyReport] = []
    obs_rows: list[ObservationReport] = []
    if rtype in {"all", "monthly"}:
        m_stmt = select(MonthlyReport).where(MonthlyReport.case_id.in_(allowed)).order_by(MonthlyReport.id.desc())
        if status_enum is not None:
            m_stmt = m_stmt.where(MonthlyReport.status == status_enum)
        if month:
            m_stmt = m_stmt.where(MonthlyReport.month == month)
        if case_id is not None:
            m_stmt = m_stmt.where(MonthlyReport.case_id == case_id)
        monthly_rows = list(db.scalars(m_stmt.limit(settings.integration_max_page_size * page)).all())
    if rtype in {"all", "observation"}:
        o_stmt = (
            select(ObservationReport)
            .where(ObservationReport.case_id.in_(allowed))
            .order_by(ObservationReport.id.desc())
        )
        if status_enum is not None:
            o_stmt = o_stmt.where(ObservationReport.status == status_enum)
        if case_id is not None:
            o_stmt = o_stmt.where(ObservationReport.case_id == case_id)
        obs_rows = list(db.scalars(o_stmt.limit(settings.integration_max_page_size * page)).all())

    combined: list[tuple[str, int, Any]] = []
    for r in monthly_rows:
        combined.append(("monthly", r.id, r))
    for r in obs_rows:
        combined.append(("observation", r.id, r))
    combined.sort(key=lambda t: t[1], reverse=True)
    total = len(combined)
    start = (page - 1) * page_size
    slice_rows = combined[start : start + page_size]
    for kind, _rid, row in slice_rows:
        if kind == "monthly":
            items.append(mask_monthly_report(row, case_code=codes.get(row.case_id)))
        else:
            items.append(mask_observation_report(row, case_code=codes.get(row.case_id)))

    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.reports_list",
        entity_type="report",
        entity_id=None,
        case_id=case_id,
        new_value={"total": total, "page": page, "page_size": page_size},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return paginated_response(items, total, page, page_size)


def get_report(
    db: Session,
    principal: IntegrationPrincipal,
    report_id: int,
    *,
    report_type: str = "monthly",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "reports:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    rtype = (report_type or "monthly").strip().lower()
    if rtype not in {"monthly", "observation"}:
        raise ValidationError("report_type must be monthly or observation.")

    if rtype == "monthly":
        report = db.get(MonthlyReport, report_id)
        if not report:
            raise NotFoundError("Report not found")
        require_case_grant(db, principal, report.case_id)
        case = db.get(Case, report.case_id)
        payload = mask_monthly_report(report, case_code=case.case_code if case else None)
    else:
        report = db.get(ObservationReport, report_id)
        if not report:
            raise NotFoundError("Report not found")
        require_case_grant(db, principal, report.case_id)
        case = db.get(Case, report.case_id)
        payload = mask_observation_report(report, case_code=case.case_code if case else None)

    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.report_read",
        entity_type="report",
        entity_id=report_id,
        case_id=report.case_id,
        new_value={"report_id": report_id, "report_type": rtype},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload


def list_pending_reporting(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "reporting:pending")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    page, page_size = normalize_pagination(page, page_size, settings.integration_max_page_size)
    allowed = filter_to_granted_cases(db, principal, None)
    if not allowed:
        return paginated_response([], 0, page, page_size)

    today = date.today()
    month_key = f"{today.year:04d}-{today.month:02d}"
    codes = _case_code_map(db, allowed)

    under_review_m = list(
        db.scalars(
            select(MonthlyReport)
            .where(
                MonthlyReport.case_id.in_(allowed),
                MonthlyReport.status == ReportStatus.UNDER_REVIEW,
            )
            .order_by(MonthlyReport.id.desc())
            .limit(200)
        ).all()
    )
    under_review_o = list(
        db.scalars(
            select(ObservationReport)
            .where(
                ObservationReport.case_id.in_(allowed),
                ObservationReport.status == ReportStatus.UNDER_REVIEW,
            )
            .order_by(ObservationReport.id.desc())
            .limit(200)
        ).all()
    )

    cases_with_monthly = set(
        db.scalars(
            select(MonthlyReport.case_id).where(
                MonthlyReport.case_id.in_(allowed),
                MonthlyReport.month == month_key,
            )
        ).all()
    )
    active_cases = list(
        db.scalars(
            select(Case).where(Case.id.in_(allowed), Case.status == CaseStatus.ACTIVE).order_by(Case.id)
        ).all()
    )
    missing = [c for c in active_cases if c.id not in cases_with_monthly]

    items: list[dict[str, Any]] = []
    for r in under_review_m:
        items.append(
            {
                "kind": "under_review",
                "report_type": "monthly",
                "report_id": r.id,
                "case_id": r.case_id,
                "case_code": codes.get(r.case_id),
                "month": r.month,
                "status": ReportStatus.UNDER_REVIEW.value,
            }
        )
    for r in under_review_o:
        items.append(
            {
                "kind": "under_review",
                "report_type": "observation",
                "report_id": r.id,
                "case_id": r.case_id,
                "case_code": codes.get(r.case_id),
                "status": ReportStatus.UNDER_REVIEW.value,
            }
        )
    for c in missing:
        items.append(
            {
                "kind": "missing_monthly",
                "report_type": "monthly",
                "report_id": None,
                "case_id": c.id,
                "case_code": c.case_code,
                "month": month_key,
                "status": "MISSING",
            }
        )

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.reporting_pending",
        entity_type="report",
        entity_id=None,
        new_value={"total": total, "page": page},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return paginated_response(page_items, total, page, page_size)
