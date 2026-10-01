from __future__ import annotations

from sqlalchemy import String, cast

from app.models.case import Case, CaseStatus

PORTAL_HIDDEN_CASE_STATUSES = frozenset(
    {
        CaseStatus.CLOSED,
        CaseStatus.DEACTIVATED,
        CaseStatus.SUSPENDED,
    }
)

PORTAL_HIDDEN_CASE_STATUS_VALUES = tuple(s.value for s in PORTAL_HIDDEN_CASE_STATUSES)


def portal_visible_case_status_filter(status_column):
    """Exclude hidden statuses without invalid Postgres enum binds (e.g. DEACTIVATED before migration)."""
    return cast(status_column, String).notin_(PORTAL_HIDDEN_CASE_STATUS_VALUES)


def is_case_hidden_from_client_portals(case: Case) -> bool:
    status = case.status.value if hasattr(case.status, "value") else str(case.status)
    return status in PORTAL_HIDDEN_CASE_STATUS_VALUES
