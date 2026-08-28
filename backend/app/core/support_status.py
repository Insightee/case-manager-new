"""Canonical support status buckets for tickets + incidents.

Layer-1 mapping only — DB enums stay TicketStatus / IncidentStatus.
Display and filters collapse to: open | in_progress | closed | escalated.

Mapping (exactly one bucket per raw value):
  open        ← ticket OPEN (not escalated), incident REPORTED (+ legacy OPEN)
  in_progress ← ticket IN_PROGRESS (not escalated) only
  escalated   ← incident IN_REVIEW + ESCALATED; tickets with escalated_to_department set
                (and not terminal CLOSED/RESOLVED)
  closed      ← ticket RESOLVED + CLOSED; incident ACTION_TAKEN + CLOSED
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.sql import ColumnElement

from app.models.incident import Incident, IncidentStatus
from app.models.support_ticket import SupportTicket, TicketStatus

CANONICAL_OPEN = "open"
CANONICAL_IN_PROGRESS = "in_progress"
CANONICAL_CLOSED = "closed"
CANONICAL_ESCALATED = "escalated"

CANONICAL_STATUSES = frozenset(
    {CANONICAL_OPEN, CANONICAL_IN_PROGRESS, CANONICAL_CLOSED, CANONICAL_ESCALATED}
)

CANONICAL_LABELS = {
    CANONICAL_OPEN: "Open",
    CANONICAL_IN_PROGRESS: "In progress",
    CANONICAL_CLOSED: "Closed",
    CANONICAL_ESCALATED: "Escalated",
}

# Ticket statuses that are terminal — escalation flag does not override these.
_TICKET_TERMINAL = frozenset({TicketStatus.RESOLVED, TicketStatus.CLOSED})

_INCIDENT_BY_CANONICAL = {
    CANONICAL_OPEN: frozenset({IncidentStatus.REPORTED}),
    CANONICAL_IN_PROGRESS: frozenset(),  # no incident status maps here
    CANONICAL_ESCALATED: frozenset({IncidentStatus.IN_REVIEW, IncidentStatus.ESCALATED}),
    CANONICAL_CLOSED: frozenset({IncidentStatus.ACTION_TAKEN, IncidentStatus.CLOSED}),
}


def normalize_canonical(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return None
    aliases = {
        "reported": CANONICAL_OPEN,
        "resolved": CANONICAL_CLOSED,
        "action_taken": CANONICAL_CLOSED,
        "in_review": CANONICAL_ESCALATED,
        "investigating": CANONICAL_ESCALATED,
    }
    if raw in aliases:
        return aliases[raw]
    if raw in CANONICAL_STATUSES:
        return raw
    # Accept raw enum casing (OPEN → open) when it already matches a canonical key.
    upper = raw.upper()
    if upper == "OPEN":
        return CANONICAL_OPEN
    if upper == "IN_PROGRESS":
        return CANONICAL_IN_PROGRESS
    if upper in ("CLOSED", "RESOLVED", "ACTION_TAKEN"):
        return CANONICAL_CLOSED
    if upper in ("ESCALATED", "IN_REVIEW", "REPORTED"):
        return CANONICAL_ESCALATED if upper != "REPORTED" else CANONICAL_OPEN
    return None


def ticket_is_escalated(*, status: TicketStatus | str | None, escalated_to_department: Any) -> bool:
    if not escalated_to_department:
        return False
    st = status.value if hasattr(status, "value") else status
    if st in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value, "RESOLVED", "CLOSED"):
        return False
    return True


def canonical_ticket_status(
    status: TicketStatus | str | None,
    *,
    escalated_to_department: Any = None,
) -> str:
    if ticket_is_escalated(status=status, escalated_to_department=escalated_to_department):
        return CANONICAL_ESCALATED
    raw = status.value if hasattr(status, "value") else (status or "")
    raw = str(raw).upper()
    if raw == TicketStatus.OPEN.value:
        return CANONICAL_OPEN
    if raw == TicketStatus.IN_PROGRESS.value:
        return CANONICAL_IN_PROGRESS
    if raw in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value):
        return CANONICAL_CLOSED
    return CANONICAL_OPEN


def canonical_incident_status(status: IncidentStatus | str | None) -> str:
    raw = status.value if hasattr(status, "value") else (status or "")
    raw = str(raw).strip().upper()
    legacy = {"OPEN": "REPORTED", "INVESTIGATING": "IN_REVIEW", "RESOLVED": "ACTION_TAKEN"}
    raw = legacy.get(raw, raw)
    if raw == IncidentStatus.REPORTED.value:
        return CANONICAL_OPEN
    if raw in (IncidentStatus.IN_REVIEW.value, IncidentStatus.ESCALATED.value):
        return CANONICAL_ESCALATED
    if raw in (IncidentStatus.ACTION_TAKEN.value, IncidentStatus.CLOSED.value):
        return CANONICAL_CLOSED
    return CANONICAL_OPEN


def canonical_status(
    record_type: str,
    status: Any,
    *,
    escalated_to_department: Any = None,
) -> str:
    rt = (record_type or "").lower()
    if rt in ("ticket", "tickets"):
        return canonical_ticket_status(status, escalated_to_department=escalated_to_department)
    return canonical_incident_status(status)


def canonical_label(value: Optional[str]) -> str:
    key = normalize_canonical(value) or (value or "")
    return CANONICAL_LABELS.get(key, key.replace("_", " ").title() if key else "")


def ticket_status_predicate(canonical: str) -> Optional[ColumnElement[bool]]:
    """SQLAlchemy predicate for SupportTicket rows under a canonical status filter.

    Escalated is a compound predicate on escalated_to_department (flag), not an enum value.
    """
    key = normalize_canonical(canonical)
    if not key:
        return None
    escalated_flag = SupportTicket.escalated_to_department.isnot(None)
    not_escalated = SupportTicket.escalated_to_department.is_(None)
    terminal = SupportTicket.status.in_(list(_TICKET_TERMINAL))

    if key == CANONICAL_OPEN:
        return and_(SupportTicket.status == TicketStatus.OPEN, not_escalated)
    if key == CANONICAL_IN_PROGRESS:
        return and_(SupportTicket.status == TicketStatus.IN_PROGRESS, not_escalated)
    if key == CANONICAL_ESCALATED:
        return and_(escalated_flag, ~terminal)
    if key == CANONICAL_CLOSED:
        return terminal
    return None


def incident_status_predicate(canonical: str) -> Optional[ColumnElement[bool]]:
    key = normalize_canonical(canonical)
    if not key:
        return None
    statuses = _INCIDENT_BY_CANONICAL.get(key)
    if not statuses:
        # Empty set (e.g. in_progress for incidents) → match nothing.
        return Incident.id == -1
    return Incident.status.in_(list(statuses))


def write_ticket_status(canonical: str) -> TicketStatus:
    """Map a canonical write choice to the underlying ticket enum."""
    key = normalize_canonical(canonical) or CANONICAL_OPEN
    if key == CANONICAL_IN_PROGRESS:
        return TicketStatus.IN_PROGRESS
    if key == CANONICAL_CLOSED:
        return TicketStatus.CLOSED
    if key == CANONICAL_ESCALATED:
        # Escalation for tickets is a flag/department flow, not a status write.
        # Keep current working status as IN_PROGRESS when UI picks escalated.
        return TicketStatus.IN_PROGRESS
    return TicketStatus.OPEN


def write_incident_status(canonical: str) -> IncidentStatus:
    """Map a canonical write choice to the underlying incident enum."""
    key = normalize_canonical(canonical) or CANONICAL_OPEN
    if key == CANONICAL_ESCALATED:
        return IncidentStatus.ESCALATED
    if key == CANONICAL_CLOSED:
        return IncidentStatus.CLOSED
    if key == CANONICAL_IN_PROGRESS:
        # No dedicated incident in_progress — map to ESCALATED bucket's IN_REVIEW is wrong;
        # write as ESCALATED per product rule that in-review merges into escalated.
        return IncidentStatus.ESCALATED
    return IncidentStatus.REPORTED
