"""Anonymised operational counts (no child/therapist/case identifiers)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.case import Case, CaseStatus
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.services.integration.access import IntegrationPrincipal, granted_case_ids, require_scope
from app.services.integration.rate_limit import check_rate_limit


def get_anonymised_ops_summary(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "ops:summary")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    allowed = granted_case_ids(db, principal)

    if not allowed:
        payload = {
            "granted_case_count": 0,
            "active_case_count": 0,
            "sessions_completed": 0,
            "sessions_scheduled": 0,
            "reports_under_review": 0,
            "reports_approved": 0,
        }
    else:
        active = db.scalar(
            select(func.count()).select_from(Case).where(Case.id.in_(allowed), Case.status == CaseStatus.ACTIVE)
        ) or 0
        completed = db.scalar(
            select(func.count())
            .select_from(TherapySession)
            .where(TherapySession.case_id.in_(allowed), TherapySession.status == SessionStatus.COMPLETED)
        ) or 0
        scheduled = db.scalar(
            select(func.count())
            .select_from(TherapySession)
            .where(TherapySession.case_id.in_(allowed), TherapySession.status == SessionStatus.SCHEDULED)
        ) or 0
        ur_m = db.scalar(
            select(func.count())
            .select_from(MonthlyReport)
            .where(MonthlyReport.case_id.in_(allowed), MonthlyReport.status == ReportStatus.UNDER_REVIEW)
        ) or 0
        ur_o = db.scalar(
            select(func.count())
            .select_from(ObservationReport)
            .where(
                ObservationReport.case_id.in_(allowed),
                ObservationReport.status == ReportStatus.UNDER_REVIEW,
            )
        ) or 0
        ap_m = db.scalar(
            select(func.count())
            .select_from(MonthlyReport)
            .where(MonthlyReport.case_id.in_(allowed), MonthlyReport.status == ReportStatus.APPROVED)
        ) or 0
        ap_o = db.scalar(
            select(func.count())
            .select_from(ObservationReport)
            .where(ObservationReport.case_id.in_(allowed), ObservationReport.status == ReportStatus.APPROVED)
        ) or 0
        payload = {
            "granted_case_count": len(allowed),
            "active_case_count": int(active),
            "sessions_completed": int(completed),
            "sessions_scheduled": int(scheduled),
            "reports_under_review": int(ur_m) + int(ur_o),
            "reports_approved": int(ap_m) + int(ap_o),
        }

    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.ops_summary",
        entity_type="ops_summary",
        entity_id=principal.client_id,
        new_value={"granted_case_count": payload["granted_case_count"]},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload
