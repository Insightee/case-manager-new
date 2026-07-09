"""Engine-first, legacy-fallback parent report resolution.

Parents see approved/locked clinical_reports when available; otherwise legacy tables.
See docs/REPORT_ARCHITECTURE.md.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus, ClinicalReportType
from app.models.report import MonthlyReport, ObservationReport
from app.models.user import User
from app.services import parent_service, report_engine_service


PARENT_VISIBLE_STATUSES = frozenset({
    ClinicalReportStatus.APPROVED.value,
    ClinicalReportStatus.LOCKED.value,
})


def _parent_visible_clinical_query(case_ids: list[int], report_type: str):
    return (
        select(ClinicalReport)
        .where(
            ClinicalReport.case_id.in_(case_ids),
            ClinicalReport.report_type == report_type,
            ClinicalReport.status.in_(PARENT_VISIBLE_STATUSES),
            ClinicalReport.archived_at.is_(None),
        )
        .order_by(ClinicalReport.updated_at.desc())
    )


def list_parent_visible_clinical_monthly(db: Session, case_ids: list[int]) -> list[ClinicalReport]:
    if not case_ids:
        return []
    rows = db.scalars(_parent_visible_clinical_query(case_ids, ClinicalReportType.MONTHLY.value)).all()
    return [r for r in rows if report_engine_service.parent_can_see_clinical_report(r)]


def list_parent_visible_clinical_observation(db: Session, case_ids: list[int]) -> list[ClinicalReport]:
    if not case_ids:
        return []
    rows = db.scalars(_parent_visible_clinical_query(case_ids, ClinicalReportType.OBSERVATION.value)).all()
    return [r for r in rows if report_engine_service.parent_can_see_clinical_report(r)]


def list_parent_visible_clinical_iep(db: Session, case_ids: list[int]) -> list[ClinicalReport]:
    if not case_ids:
        return []
    rows = db.scalars(_parent_visible_clinical_query(case_ids, ClinicalReportType.IEP.value)).all()
    return [r for r in rows if report_engine_service.parent_can_see_clinical_report(r)]


def _month_key_for_clinical(report: ClinicalReport) -> str:
    meta = json.loads(report.metadata_json) if report.metadata_json else {}
    return str(meta.get("month") or "")


def serialize_clinical_monthly_list_item_light(report: ClinicalReport, case: Case | None) -> dict:
    month = _month_key_for_clinical(report)
    return {
        "kind": "monthly",
        "id": str(report.id),
        "source": "clinical_reports",
        "clinicalReportId": report.id,
        "caseId": case.case_code if case else "",
        "caseDbId": report.case_id,
        "childName": case.child.full_name if case and case.child else "",
        "month": month or report.title,
        "label": month or report.title,
        "status": "approved",
        "summaryPreview": (report.title or "")[:120],
        "category": "CLIENT_MONTHLY",
    }


def merge_monthly_hub_items(
    engine_items: list[dict],
    legacy_items: list[dict],
    document_items: list[dict] | None = None,
) -> list[dict]:
    """Prefer engine monthly per caseDbId+month; then uploaded PDFs; then legacy."""
    engine_keys = {(i.get("caseDbId"), i.get("month")) for i in engine_items}
    doc_filtered = [
        i
        for i in (document_items or [])
        if (i.get("caseDbId"), i.get("month")) not in engine_keys
    ]
    covered = engine_keys | {(i.get("caseDbId"), i.get("month")) for i in doc_filtered}
    legacy_filtered = [i for i in legacy_items if (i.get("caseDbId"), i.get("month")) not in covered]
    return engine_items + doc_filtered + legacy_filtered


def serialize_document_monthly_list_item(doc: dict[str, Any], case: Case | None) -> dict:
    month = doc.get("reportMonth") or doc.get("report_month") or doc.get("title") or ""
    return {
        "kind": "monthly",
        "id": f"doc-{doc.get('id')}",
        "source": "case_documents",
        "caseDocumentId": doc.get("id"),
        "caseId": case.case_code if case else doc.get("caseCode", ""),
        "caseDbId": doc.get("caseDbId") or (case.id if case else None),
        "childName": case.child.full_name if case and case.child else doc.get("childName", ""),
        "month": month,
        "label": month or doc.get("title", "Monthly report"),
        "status": "approved" if doc.get("status") == "APPROVED" else str(doc.get("status", "")).lower(),
        "summaryPreview": (doc.get("title") or "")[:120],
        "category": "CLIENT_MONTHLY",
        "downloadPath": f"/api/v1/case-documents/{doc.get('id')}/download",
    }


def get_clinical_monthly_for_parent(
    db: Session, user: User, report_id: int
) -> dict | None:
    report = db.get(ClinicalReport, report_id)
    if not report or report.report_type != ClinicalReportType.MONTHLY.value:
        return None
    if not report_engine_service.parent_can_see_clinical_report(report):
        return None
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        return None
    safe = report_engine_service.serialize_parent_safe_monthly(db, report, case)
    sections_html = "".join(
        f"<h2>{s['label']}</h2>{s.get('narrative_text', '')}" for s in safe.get("sections", [])
    )
    return {
        "kind": "monthly",
        "id": str(report.id),
        "source": "clinical_reports",
        "clinicalReportId": report.id,
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "month": safe.get("month") or _month_key_for_clinical(report),
        "summary": safe.get("title"),
        "bodyHtml": sections_html,
        "planNextMonth": "",
        "category": "CLIENT_MONTHLY",
        "downloadPath": f"/api/v1/parent/reports/monthly/{report.id}/download",
        "status": "approved",
        "parentReviewStatus": None,
        "parentFeedback": None,
        "parentMonthlyRating": None,
        "createdAt": report.created_at.isoformat() if report.created_at else None,
        "comments": [],
    }


def get_clinical_observation_for_parent(
    db: Session, user: User, report_id: int
) -> dict | None:
    report = db.get(ClinicalReport, report_id)
    if not report or report.report_type != ClinicalReportType.OBSERVATION.value:
        return None
    if not report_engine_service.parent_can_see_clinical_report(report):
        return None
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        return None
    safe = report_engine_service.serialize_parent_safe_observation(db, report, case)
    sections_html = "".join(
        f"<h2>{s['label']}</h2>{s.get('narrative_text', '')}" for s in safe.get("sections", [])
    )
    return {
        "kind": "observation",
        "id": str(report.id),
        "source": "clinical_reports",
        "clinicalReportId": report.id,
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "title": report.title,
        "bodyHtml": sections_html,
        "content": sections_html,
        "planNextMonth": "",
        "reportDate": report.approved_at.isoformat() if report.approved_at else None,
        "downloadPath": f"/api/v1/parent/reports/observation/{report.id}/download",
        "status": "approved",
        "createdAt": report.created_at.isoformat() if report.created_at else None,
    }


def get_clinical_iep_for_parent(
    db: Session, user: User, clinical_report_id: int
) -> dict | None:
    report = db.get(ClinicalReport, clinical_report_id)
    if not report or report.report_type != ClinicalReportType.IEP.value:
        return None
    if not report_engine_service.parent_can_see_clinical_report(report):
        return None
    case = parent_service.get_parent_case(db, user, report.case_id)
    if not case:
        return None
    safe = report_engine_service.serialize_parent_safe_iep(db, report, case)
    sections_html = "".join(
        f"<h2>{s['label']}</h2>{s.get('narrative_text', '')}" for s in safe.get("sections", [])
    )
    return {
        "kind": "iep",
        "id": str(report.id),
        "source": "clinical_reports",
        "clinicalReportId": report.id,
        "caseId": case.case_code,
        "caseDbId": case.id,
        "childName": case.child.full_name if case.child else "",
        "version": "engine",
        "fileName": report.title,
        "title": report.title,
        "downloadPath": f"/api/v1/parent/reports/iep/{report.id}/download",
        "status": "acknowledged" if report.status == ClinicalReportStatus.LOCKED.value else "pending",
        "planId": None,
        "canAcknowledge": False,
        "canSuggestGoals": False,
        "bodyHtml": sections_html,
        "issuedAt": report.approved_at.isoformat() if report.approved_at else None,
        "comments": [],
    }


def resolve_parent_monthly_detail(db: Session, user: User, report_id: int) -> dict:
    clinical = get_clinical_monthly_for_parent(db, user, report_id)
    if clinical:
        return clinical
    from app.services import parent_reports_service as legacy

    return legacy.get_monthly_detail(db, user, report_id)


def resolve_parent_observation_detail(db: Session, user: User, report_id: int) -> dict:
    clinical = get_clinical_observation_for_parent(db, user, report_id)
    if clinical:
        return clinical
    from app.services import parent_reports_service as legacy

    return legacy.get_observation_detail(db, user, report_id)
