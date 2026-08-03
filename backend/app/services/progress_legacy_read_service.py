"""Engine-first progress resolution with legacy MonthlyReport fallback."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus
from app.models.report import MonthlyReport, ReportCategory, ReportStatus
from app.services import progress_report_service as progress_svc

logger = logging.getLogger(__name__)

_legacy_fallback_count = 0


def legacy_progress_fallback_count() -> int:
    return _legacy_fallback_count


def resolve_progress_for_case(db: Session, case: Case) -> dict | None:
    """Return hub state for progress — engine first, legacy MonthlyReport second."""
    global _legacy_fallback_count

    engine_report = progress_svc.get_active_progress_report(db, case.id)
    if engine_report:
        period = progress_svc.report_period_from_metadata(engine_report)
        approved = engine_report.status in (
            ClinicalReportStatus.APPROVED.value,
            ClinicalReportStatus.LOCKED.value,
        )
        return {
            "source": "clinical_reports",
            "report_id": engine_report.id,
            "status": engine_report.status,
            "period_start": period.get("start"),
            "period_end": period.get("end"),
            "approved": approved,
            "updated_at": engine_report.updated_at,
        }

    legacy = db.scalar(
        select(MonthlyReport)
        .where(
            MonthlyReport.case_id == case.id,
            MonthlyReport.category == ReportCategory.PROGRESS.value,
            MonthlyReport.status.in_((ReportStatus.APPROVED, ReportStatus.PUBLISHED)),
        )
        .order_by(MonthlyReport.updated_at.desc())
    )
    if legacy:
        _legacy_fallback_count += 1
        logger.info(
            "legacy_progress_fallback case_id=%s legacy_report_id=%s count=%s",
            case.id,
            legacy.id,
            _legacy_fallback_count,
        )
        return {
            "source": "legacy_monthly",
            "report_id": legacy.id,
            "status": legacy.status.value if hasattr(legacy.status, "value") else str(legacy.status),
            "period_start": None,
            "period_end": None,
            "approved": True,
            "updated_at": legacy.updated_at,
        }
    return None
