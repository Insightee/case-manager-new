"""Sync legacy monthly reports into clinical_reports (idempotent strangler adapter)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import MonthlyReportSection
from app.models.clinical_report import (
    ClinicalReport,
    ClinicalReportStatus,
    ClinicalReportType,
)
from app.models.report import MonthlyReport, ReportStatus
from app.models.user import User
from app.report_engine_constants import LEGACY_MONTHLY_SECTION_KEY_MAP, MONTHLY_REPORT_SECTIONS
from app.services import report_engine_service, report_status_service

logger = logging.getLogger(__name__)


def _find_synced_clinical_report(db: Session, legacy: MonthlyReport) -> ClinicalReport | None:
    month_key = report_engine_service._normalize_month_key(legacy.month)
    rows = db.scalars(
        select(ClinicalReport).where(
            ClinicalReport.case_id == legacy.case_id,
            ClinicalReport.report_type == ClinicalReportType.MONTHLY.value,
            ClinicalReport.archived_at.is_(None),
        )
    ).all()
    for row in rows:
        meta = json.loads(row.metadata_json) if row.metadata_json else {}
        if meta.get("legacy_source_id") == legacy.id:
            return row
        if meta.get("month") == month_key and meta.get("legacy_source_id") in (None, legacy.id):
            return row
    return None


def _legacy_section_map(db: Session, legacy_id: int) -> dict[str, str]:
    rows = db.scalars(
        select(MonthlyReportSection).where(MonthlyReportSection.report_id == legacy_id)
    ).all()
    out: dict[str, str] = {}
    for row in rows:
        engine_key = LEGACY_MONTHLY_SECTION_KEY_MAP.get(row.section_key, row.section_key)
        if row.content_html:
            out[engine_key] = row.content_html
    return out


def _map_legacy_status(legacy: MonthlyReport) -> str:
    if legacy.status == ReportStatus.PUBLISHED:
        return ClinicalReportStatus.LOCKED.value
    if legacy.status == ReportStatus.APPROVED:
        return ClinicalReportStatus.APPROVED.value
    if legacy.status == ReportStatus.UNDER_REVIEW:
        return ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value
    if legacy.status == ReportStatus.REJECTED:
        return ClinicalReportStatus.RETURNED_FOR_CHANGES.value
    return ClinicalReportStatus.DRAFT.value


def sync_legacy_monthly_to_clinical(
    db: Session,
    legacy: MonthlyReport,
    *,
    reviewer: User | None = None,
) -> ClinicalReport:
    """Create or update engine monthly mirror from legacy report (idempotent)."""
    month_key = report_engine_service._normalize_month_key(legacy.month)
    existing = _find_synced_clinical_report(db, legacy)
    from app.services import case_service

    case = case_service.get_case(db, legacy.case_id)
    child_id = case.child_id if case else None

    meta = {
        "month": month_key,
        "legacy_source_id": legacy.id,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        report = existing
        report.metadata_json = json.dumps(meta)
    else:
        title_child = case.child.full_name if case and case.child else "Client"
        report = ClinicalReport(
            case_id=legacy.case_id,
            child_id=child_id,
            report_type=ClinicalReportType.MONTHLY.value,
            title=f"Monthly Report — {month_key} — {title_child}",
            status=_map_legacy_status(legacy),
            created_by_id=legacy.therapist_user_id,
            assigned_therapist_id=legacy.therapist_user_id,
            metadata_json=json.dumps(meta),
        )
        db.add(report)
        db.flush()
        report_engine_service.seed_monthly_sections(db, report.id)

    report.status = _map_legacy_status(legacy)
    report.submitted_at = legacy.submitted_for_review_at
    report.approved_at = legacy.cm_published_at or legacy.admin_published_at
    if legacy.cm_published_by_user_id:
        report.approved_by_id = legacy.cm_published_by_user_id
    elif legacy.admin_published_by_user_id:
        report.approved_by_id = legacy.admin_published_by_user_id
    if legacy.cm_published_at or legacy.admin_published_at:
        report.parent_visible_at = legacy.cm_published_at or legacy.admin_published_at
    if report.status == ClinicalReportStatus.LOCKED.value:
        report.locked_at = report.approved_at

    section_content = _legacy_section_map(db, legacy.id)
    if legacy.body_html and not section_content:
        section_content["sessions_summary"] = legacy.body_html
    if legacy.summary:
        section_content.setdefault("child_summary", f"<p>{legacy.summary}</p>")
    if legacy.plan_next_month:
        section_content.setdefault("next_month_focus", f"<p>{legacy.plan_next_month}</p>")

    for key, html in section_content.items():
        try:
            report_engine_service.patch_section(db, report, key, narrative_text=html)
        except ValueError:
            continue

    if report.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value) and reviewer:
        try:
            report_status_service.create_approved_version_snapshot(db, report, reviewer)
        except Exception:
            logger.exception("version snapshot failed for synced monthly report_id=%s", report.id)

    db.flush()
    return report


def sync_legacy_monthly_best_effort(db: Session, legacy: MonthlyReport, reviewer: User | None = None) -> None:
    """Best-effort sync — never blocks legacy approval."""
    try:
        sync_legacy_monthly_to_clinical(db, legacy, reviewer=reviewer)
    except Exception:
        logger.exception("monthly sync failed legacy_id=%s", legacy.id)
