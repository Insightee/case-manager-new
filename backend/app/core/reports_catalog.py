"""Operational report catalog for HR / admin exports."""
from __future__ import annotations

from typing import Any

REPORT_CATEGORIES: list[dict[str, str]] = [
    {"id": "hr_attendance", "label": "HR & attendance"},
    {"id": "session_ops", "label": "Session logs & billing"},
    {"id": "crm_lifecycle", "label": "CRM & client lifecycle"},
    {"id": "case_manager", "label": "Case manager compliance"},
    {"id": "legacy", "label": "Legacy exports"},
]

REPORT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "bulk-attendance",
        "label": "Bulk attendance",
        "description": "Monthly attendance by case×therapist assignment window (mid-month replacements produce separate rows with start/end dates).",
        "category": "hr_attendance",
        "filters": ["month", "product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "therapist-log-compliance",
        "label": "Therapist log compliance",
        "description": "Therapist–case rows for completed sessions missing logs (2+ days old).",
        "category": "hr_attendance",
        "filters": ["product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "session-log-detail",
        "label": "Detailed session log",
        "description": "Every session in range with log compliance, approvals, and billable status.",
        "category": "session_ops",
        "filters": ["date_from", "date_to", "product_module", "case_manager_user_id", "therapist_user_id", "case_id"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "session-monthly-summary",
        "label": "Monthly session summary",
        "description": "Client-wise (split by assignment window on reassignment) and therapist-wise session aggregates for the selected month.",
        "category": "session_ops",
        "filters": ["month", "product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
        "multi_sheet": True,
    },
    {
        "key": "replacement-history",
        "label": "Therapist replacement history",
        "description": "Therapist changes on cases with reasons and reassignment dates.",
        "category": "crm_lifecycle",
        "filters": ["month", "product_module"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "support-tickets-parent",
        "label": "Parent support tickets",
        "description": "Grievances and requests raised by parents.",
        "category": "crm_lifecycle",
        "filters": ["month", "product_module"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "incident-reports",
        "label": "Incident reports",
        "description": "Safeguarding and operational incidents with category, status, and case linkage.",
        "category": "crm_lifecycle",
        "filters": ["month", "product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "cm-meetings",
        "label": "Case manager meetings",
        "description": "Checklist and IEP meetings with monthly CM rollups.",
        "category": "case_manager",
        "filters": ["month", "product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
        "multi_sheet": True,
    },
    {
        "key": "inactive-clients",
        "label": "Clients without recent sessions (7+ days)",
        "description": "Active cases with no completed session in the last 7 days.",
        "category": "crm_lifecycle",
        "filters": ["product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "parent-portal-usage",
        "label": "Parent portal usage",
        "description": "Parent portal login status (Active/Inactive) and last login by active case.",
        "category": "crm_lifecycle",
        "filters": ["product_module", "case_manager_user_id"],
        "formats": ["csv", "xlsx", "pdf"],
    },
    {
        "key": "observation",
        "label": "Observation reports",
        "category": "legacy",
        "filters": ["month", "product_module"],
        "formats": ["csv"],
    },
    {
        "key": "client-monthly",
        "label": "Client monthly reports",
        "category": "legacy",
        "filters": ["month", "product_module"],
        "formats": ["csv"],
    },
    {
        "key": "session-logs",
        "label": "Session logs (simple)",
        "category": "legacy",
        "filters": ["month", "product_module"],
        "formats": ["csv"],
    },
    {
        "key": "cases-roster",
        "label": "Cases roster",
        "category": "legacy",
        "filters": ["product_module"],
        "formats": ["csv"],
    },
    {
        "key": "staff-status",
        "label": "Staff status",
        "category": "legacy",
        "filters": [],
        "formats": ["csv"],
    },
    {
        "key": "therapist-status",
        "label": "Therapist status",
        "category": "legacy",
        "filters": [],
        "formats": ["csv"],
    },
]

REPORT_KEYS = frozenset(d["key"] for d in REPORT_DEFINITIONS)


def catalog_payload() -> dict[str, Any]:
    return {
        "categories": REPORT_CATEGORIES,
        "reports": REPORT_DEFINITIONS,
    }


def report_definition(key: str) -> dict[str, Any] | None:
    for item in REPORT_DEFINITIONS:
        if item["key"] == key:
            return item
    return None
