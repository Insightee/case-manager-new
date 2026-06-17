from __future__ import annotations

from app.models.case import Case, CaseStatus

PORTAL_HIDDEN_CASE_STATUSES = frozenset(
    {
        CaseStatus.CLOSED,
        CaseStatus.DEACTIVATED,
    }
)


def is_case_hidden_from_client_portals(case: Case) -> bool:
    status = case.status.value if hasattr(case.status, "value") else str(case.status)
    return status in {s.value for s in PORTAL_HIDDEN_CASE_STATUSES}
