"""Read helpers for report artifact triple-read (engine + uploaded PDFs + legacy)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_document import (
    CaseDocument,
    CaseDocumentCategory,
    CaseDocumentStatus,
    CaseDocumentVisibility,
)
from app.models.clinical_report import ClinicalReport, ClinicalReportType
from app.services import report_engine_service as report_engine_svc

REPORT_DOCUMENT_CATEGORIES = frozenset(
    {
        CaseDocumentCategory.OBSERVATION_REPORT.value,
        CaseDocumentCategory.CLIENT_MONTHLY_REPORT.value,
        CaseDocumentCategory.MONTHLY_PROGRESS_REPORT.value,
        CaseDocumentCategory.IEP_PLAN.value,
        CaseDocumentCategory.ANNUAL_PROGRESS_REPORT.value,
        CaseDocumentCategory.TERMINATION_PROGRESS_REPORT.value,
        CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
    }
)

DOCUMENT_STATUS_LABELS = {
    CaseDocumentStatus.DRAFT.value: "Draft",
    CaseDocumentStatus.SUBMITTED.value: "Pending CM approval",
    CaseDocumentStatus.CM_REVIEW.value: "Pending CM approval",
    CaseDocumentStatus.CHANGES_REQUESTED.value: "Needs changes",
    CaseDocumentStatus.CLIENT_REVIEW.value: "With family",
    CaseDocumentStatus.APPROVED.value: "Approved",
    CaseDocumentStatus.ARCHIVED.value: "Archived",
}


def document_report_type(category: str) -> str:
    if category == CaseDocumentCategory.OBSERVATION_REPORT.value:
        return "observation_report"
    if category == CaseDocumentCategory.IEP_PLAN.value:
        return "iep"
    if category in (
        CaseDocumentCategory.MONTHLY_PROGRESS_REPORT.value,
        CaseDocumentCategory.ANNUAL_PROGRESS_REPORT.value,
        CaseDocumentCategory.TERMINATION_PROGRESS_REPORT.value,
    ):
        return "progress_report"
    return "monthly_report"


def document_month_key(doc: CaseDocument) -> str | None:
    if doc.report_month:
        try:
            return report_engine_svc._normalize_month_key(doc.report_month)  # noqa: SLF001
        except ValueError:
            pass
    if doc.report_date:
        return doc.report_date.strftime("%Y-%m")
    if doc.updated_at:
        return doc.updated_at.strftime("%Y-%m")
    return None


def dedupe_key(case_id: int, report_type: str, month_key: str | None) -> tuple[int, str, str]:
    return (case_id, report_type, month_key or "")


def list_report_documents_for_case(db: Session, case_id: int) -> list[CaseDocument]:
    return list(
        db.scalars(
            select(CaseDocument)
            .where(
                CaseDocument.case_id == case_id,
                CaseDocument.category.in_(REPORT_DOCUMENT_CATEGORIES),
            )
            .order_by(CaseDocument.updated_at.desc())
        ).all()
    )


def engine_month_keys_for_case(db: Session, case_id: int) -> set[tuple[int, str, str]]:
    keys: set[tuple[int, str, str]] = set()
    for row in report_engine_svc.list_case_reports(db, case_id):
        if row.report_type == ClinicalReportType.MONTHLY.value:
            mk = report_engine_svc._report_month_from_metadata(row)  # noqa: SLF001
            if mk:
                norm = report_engine_svc._normalize_month_key(mk)  # noqa: SLF001
                keys.add(dedupe_key(case_id, "monthly_report", norm))
        elif row.report_type == ClinicalReportType.OBSERVATION.value:
            mk = (row.updated_at or datetime.now(timezone.utc)).strftime("%Y-%m")
            keys.add(dedupe_key(case_id, "observation_report", mk))
        elif row.report_type == ClinicalReportType.IEP.value:
            mk = (row.updated_at or datetime.now(timezone.utc)).strftime("%Y-%m")
            keys.add(dedupe_key(case_id, "iep", mk))
    return keys


def engine_has_exportable_monthly(db: Session, case_id: int, month_key: str) -> bool:
    """True when engine monthly exists with approved/locked status for month."""
    report = report_engine_svc.get_monthly_report_for_case_month(db, case_id, month_key)
    if not report:
        return False
    from app.models.clinical_report import ClinicalReportStatus

    return report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
        ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value,
    )


def history_item_from_case_document(db: Session, case, doc: CaseDocument) -> dict:
    from app.models.user import User

    def _iso(d: date | datetime | None) -> str | None:
        if d is None:
            return None
        if isinstance(d, datetime):
            return d.date().isoformat()
        return d.isoformat()

    def _user_display(user_id: int | None) -> str | None:
        if not user_id:
            return None
        u = db.get(User, user_id)
        return u.full_name if u else None

    report_type = document_report_type(doc.category)
    month_key = document_month_key(doc)
    period = doc.report_month or (doc.report_date.isoformat() if doc.report_date else None)
    sort_d = doc.updated_at or doc.created_at or datetime.now(timezone.utc)
    title_map = {
        "observation_report": "Observation Report",
        "iep": "IEP",
        "progress_report": "Progress Report",
        "monthly_report": f"Monthly Report — {period or 'Uploaded PDF'}",
    }
    return {
        "id": f"doc-{doc.id}",
        "type": report_type,
        "title": title_map.get(report_type, doc.title),
        "status": doc.status.lower(),
        "status_label": DOCUMENT_STATUS_LABELS.get(doc.status, doc.status),
        "period_label": period or doc.title,
        "last_updated": _iso(doc.updated_at),
        "created_by": _user_display(db, doc.submitted_by_user_id),
        "summary": doc.title,
        "cta_label": "View document",
        "target_url": f"/therapist/cases/{case.id}?tab=documents&document={doc.id}",
        "sort_date": sort_d,
        "month_key": month_key or sort_d.strftime("%Y-%m"),
        "source": "uploaded_pdf",
        "case_document_id": doc.id,
        "parent_visible": doc.visibility
        in (
            CaseDocumentVisibility.CLIENT_VISIBLE.value,
            CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
        ),
    }


def monthly_document_for_month(db: Session, case_id: int, month_label: str) -> CaseDocument | None:
    norm = report_engine_svc._normalize_month_key(month_label)  # noqa: SLF001
    for doc in list_report_documents_for_case(db, case_id):
        if document_report_type(doc.category) != "monthly_report":
            continue
        mk = document_month_key(doc)
        if mk == norm:
            return doc
    return None
