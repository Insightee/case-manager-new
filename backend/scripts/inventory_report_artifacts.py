#!/usr/bin/env python3
"""Production-safe inventory of report artifact families (read-only).

Counts structured monthly_reports, clinical_reports (engine), and uploaded PDFs
in case_documents. Use before legacy bridge retirement.

Usage (from backend/):
  python -m scripts.inventory_report_artifacts [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.case_document import (
    CLINICAL_CATEGORIES,
    CaseDocument,
    CaseDocumentCategory,
    CaseDocumentStatus,
    CaseDocumentVisibility,
)
from app.models.case_document import CaseDocumentVersion
from app.models.clinical_report import ClinicalReport, ClinicalReportType
from app.models.report import MonthlyReport, ReportCategory, ReportStatus


REPORT_DOC_CATEGORIES = frozenset(
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

PARENT_VISIBLE_STATUSES = frozenset(
    {
        CaseDocumentStatus.CLIENT_REVIEW.value,
        CaseDocumentStatus.APPROVED.value,
    }
)


def _count_by(stmt_group) -> dict[str, int]:
    return {str(k): int(v) for k, v in stmt_group}


def _legacy_without_engine_mirror(db) -> int:
    """Legacy monthly rows with no clinical_reports mirror (best-effort)."""
    import json as json_mod

    legacy_rows = db.scalars(
        select(MonthlyReport).where(MonthlyReport.category != ReportCategory.PROGRESS.value)
    ).all()
    engine_rows = db.scalars(
        select(ClinicalReport).where(
            ClinicalReport.report_type == ClinicalReportType.MONTHLY.value,
            ClinicalReport.archived_at.is_(None),
        )
    ).all()
    mirrored_legacy_ids: set[int] = set()
    engine_month_keys: set[tuple[int, str]] = set()
    for row in engine_rows:
        meta = json_mod.loads(row.metadata_json) if row.metadata_json else {}
        lid = meta.get("legacy_source_id")
        if lid:
            mirrored_legacy_ids.add(int(lid))
        month = meta.get("month")
        if month:
            engine_month_keys.add((row.case_id, month))

    missing = 0
    for leg in legacy_rows:
        if leg.id in mirrored_legacy_ids:
            continue
        from app.services import report_engine_service

        norm = report_engine_service._normalize_month_key(leg.month) if leg.month else None  # noqa: SLF001
        if norm and (leg.case_id, norm) in engine_month_keys:
            continue
        if leg.status in (ReportStatus.APPROVED, ReportStatus.PUBLISHED, ReportStatus.UNDER_REVIEW):
            missing += 1
    return missing


def build_inventory(db) -> dict:
    monthly_by_status = _count_by(
        db.execute(
            select(MonthlyReport.status, func.count())
            .where(MonthlyReport.category != ReportCategory.PROGRESS.value)
            .group_by(MonthlyReport.status)
        ).all()
    )
    monthly_by_category = _count_by(
        db.execute(select(MonthlyReport.category, func.count()).group_by(MonthlyReport.category)).all()
    )
    progress_by_status = _count_by(
        db.execute(
            select(MonthlyReport.status, func.count())
            .where(MonthlyReport.category == ReportCategory.PROGRESS.value)
            .group_by(MonthlyReport.status)
        ).all()
    )

    engine_monthly = int(
        db.scalar(
            select(func.count())
            .select_from(ClinicalReport)
            .where(
                ClinicalReport.report_type == ClinicalReportType.MONTHLY.value,
                ClinicalReport.archived_at.is_(None),
            )
        )
        or 0
    )
    engine_all = _count_by(
        db.execute(
            select(ClinicalReport.report_type, func.count())
            .where(ClinicalReport.archived_at.is_(None))
            .group_by(ClinicalReport.report_type)
        ).all()
    )

    docs_by_category = _count_by(
        db.execute(
            select(CaseDocument.category, func.count())
            .where(CaseDocument.category.in_(REPORT_DOC_CATEGORIES))
            .group_by(CaseDocument.category)
        ).all()
    )
    docs_by_status = _count_by(
        db.execute(
            select(CaseDocument.status, func.count())
            .where(CaseDocument.category.in_(REPORT_DOC_CATEGORIES))
            .group_by(CaseDocument.status)
        ).all()
    )
    docs_by_visibility = _count_by(
        db.execute(
            select(CaseDocument.visibility, func.count())
            .where(CaseDocument.category.in_(REPORT_DOC_CATEGORIES))
            .group_by(CaseDocument.visibility)
        ).all()
    )

    parent_visible_docs = int(
        db.scalar(
            select(func.count())
            .select_from(CaseDocument)
            .where(
                CaseDocument.category.in_(REPORT_DOC_CATEGORIES),
                CaseDocument.status.in_(PARENT_VISIBLE_STATUSES),
                CaseDocument.visibility.in_(
                    (
                        CaseDocumentVisibility.CLIENT_VISIBLE.value,
                        CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
                    )
                ),
            )
        )
        or 0
    )

    linked_to_monthly = int(
        db.scalar(
            select(func.count())
            .select_from(CaseDocument)
            .where(
                CaseDocument.category.in_(REPORT_DOC_CATEGORIES),
                CaseDocument.linked_report_id.isnot(None),
            )
        )
        or 0
    )
    unlinked_pdfs = int(
        db.scalar(
            select(func.count())
            .select_from(CaseDocument)
            .where(
                CaseDocument.category.in_(REPORT_DOC_CATEGORIES),
                CaseDocument.linked_report_id.is_(None),
            )
        )
        or 0
    )

    with_storage_key = int(
        db.scalar(
            select(func.count())
            .select_from(CaseDocumentVersion)
            .join(CaseDocument, CaseDocumentVersion.case_document_id == CaseDocument.id)
            .where(
                CaseDocument.category.in_(REPORT_DOC_CATEGORIES),
                CaseDocumentVersion.storage_key.isnot(None),
            )
        )
        or 0
    )
    with_external_url = int(
        db.scalar(
            select(func.count())
            .select_from(CaseDocumentVersion)
            .join(CaseDocument, CaseDocumentVersion.case_document_id == CaseDocument.id)
            .where(
                CaseDocument.category.in_(REPORT_DOC_CATEGORIES),
                CaseDocumentVersion.external_url.isnot(None),
            )
        )
        or 0
    )

    cases_with_artifacts: dict[str, set[int]] = defaultdict(set)
    for case_id in db.scalars(select(MonthlyReport.case_id).distinct()):
        cases_with_artifacts["monthly_reports"].add(case_id)
    for case_id in db.scalars(
        select(ClinicalReport.case_id).where(ClinicalReport.archived_at.is_(None)).distinct()
    ):
        cases_with_artifacts["clinical_reports"].add(case_id)
    for case_id in db.scalars(
        select(CaseDocument.case_id).where(CaseDocument.category.in_(REPORT_DOC_CATEGORIES)).distinct()
    ):
        cases_with_artifacts["uploaded_pdfs"].add(case_id)

    return {
        "structured_monthly_reports": {
            "total_non_progress": sum(monthly_by_status.values()),
            "by_status": monthly_by_status,
            "by_category": monthly_by_category,
            "progress_reports_by_status": progress_by_status,
            "approved_or_published_without_engine_mirror": _legacy_without_engine_mirror(db),
        },
        "clinical_reports_engine": {
            "monthly_count": engine_monthly,
            "by_report_type": engine_all,
        },
        "uploaded_report_documents": {
            "total_report_category_docs": sum(docs_by_category.values()),
            "by_category": docs_by_category,
            "by_status": docs_by_status,
            "by_visibility": docs_by_visibility,
            "parent_visible_count": parent_visible_docs,
            "linked_to_monthly_reports": linked_to_monthly,
            "not_linked_to_monthly_reports": unlinked_pdfs,
            "versions_with_r2_storage_key": with_storage_key,
            "versions_with_external_url": with_external_url,
        },
        "case_coverage": {
            "cases_with_monthly_reports": len(cases_with_artifacts["monthly_reports"]),
            "cases_with_clinical_reports": len(cases_with_artifacts["clinical_reports"]),
            "cases_with_uploaded_pdfs": len(cases_with_artifacts["uploaded_pdfs"]),
        },
        "notes": [
            "Read-only inventory — no mutations.",
            "Uploaded PDFs live in case_documents; parent access via documents API.",
            "Gate PR B on confirming PDF access paths from production counts.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        inv = build_inventory(db)
        if args.json:
            print(json.dumps(inv, indent=2))
        else:
            print("=== Report artifact inventory (read-only) ===\n")
            print(json.dumps(inv, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
