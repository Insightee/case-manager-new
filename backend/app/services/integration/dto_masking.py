"""Field-level masking for external integration responses."""
from __future__ import annotations

from datetime import date
from typing import Any

from app.models.case import Case
from app.models.child import Child
from app.models.report import MonthlyReport, ObservationReport, ReportStatus


def child_initials(child: Child | None) -> str | None:
    if child is None:
        return None
    first = (child.first_name or "").strip()
    last = (child.last_name or "").strip()
    parts = []
    if first:
        parts.append(first[0].upper() + ".")
    if last:
        parts.append(last[0].upper() + ".")
    return " ".join(parts) if parts else None


def age_band(dob: date | None, *, today: date | None = None) -> str | None:
    if dob is None:
        return None
    ref = today or date.today()
    years = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    if years < 0:
        return None
    if years < 5:
        return "0-4"
    if years < 8:
        return "5-7"
    if years < 12:
        return "8-11"
    if years < 16:
        return "12-15"
    return "16+"


def truncate_summary(text: str | None, *, max_len: int = 240) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def mask_case(case: Case, child: Child | None = None) -> dict[str, Any]:
    child = child or getattr(case, "child", None)
    status = case.status.value if hasattr(case.status, "value") else str(case.status)
    return {
        "id": case.id,
        "case_code": case.case_code,
        "status": status,
        "product_module": case.product_module,
        "service_type": case.service_type,
        "region": case.region,
        "child_initials": child_initials(child),
        "child_age_band": age_band(child.date_of_birth if child else None),
    }


def mask_monthly_report(report: MonthlyReport, *, case_code: str | None = None) -> dict[str, Any]:
    status = report.status.value if isinstance(report.status, ReportStatus) else str(report.status)
    vis = report.visibility_status.value if hasattr(report.visibility_status, "value") else str(report.visibility_status)
    return {
        "id": report.id,
        "report_type": "monthly",
        "case_id": report.case_id,
        "case_code": case_code,
        "month": report.month,
        "status": status,
        "visibility_status": vis,
        "category": report.category,
        "submitted_for_review_at": report.submitted_for_review_at.isoformat() if report.submitted_for_review_at else None,
        "summary_excerpt": truncate_summary(report.summary),
        # Explicitly omit: body_html, plan_next_month, reviewer_comment, parent_feedback, therapist ids
    }


def mask_observation_report(report: ObservationReport, *, case_code: str | None = None) -> dict[str, Any]:
    status = report.status.value if isinstance(report.status, ReportStatus) else str(report.status)
    vis = report.visibility_status.value if hasattr(report.visibility_status, "value") else str(report.visibility_status)
    return {
        "id": report.id,
        "report_type": "observation",
        "case_id": report.case_id,
        "case_code": case_code,
        "title": truncate_summary(report.title, max_len=120),
        "status": status,
        "visibility_status": vis,
        "category": report.category,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "summary_excerpt": truncate_summary(report.content),
    }
