"""Unit tests for canonical support status mapping."""
from __future__ import annotations

from app.core.support_status import (
    CANONICAL_CLOSED,
    CANONICAL_ESCALATED,
    CANONICAL_IN_PROGRESS,
    CANONICAL_OPEN,
    canonical_incident_status,
    canonical_ticket_status,
    normalize_canonical,
    ticket_is_escalated,
)
from app.models.incident import IncidentStatus
from app.models.support_ticket import TicketStatus


def test_normalize_canonical_aliases():
    assert normalize_canonical("REPORTED") == CANONICAL_OPEN
    assert normalize_canonical("in_review") == CANONICAL_ESCALATED
    assert normalize_canonical("ACTION_TAKEN") == CANONICAL_CLOSED
    assert normalize_canonical("RESOLVED") == CANONICAL_CLOSED
    assert normalize_canonical("open") == CANONICAL_OPEN


def test_ticket_mapping_no_escalation():
    assert canonical_ticket_status(TicketStatus.OPEN) == CANONICAL_OPEN
    assert canonical_ticket_status(TicketStatus.IN_PROGRESS) == CANONICAL_IN_PROGRESS
    assert canonical_ticket_status(TicketStatus.RESOLVED) == CANONICAL_CLOSED
    assert canonical_ticket_status(TicketStatus.CLOSED) == CANONICAL_CLOSED


def test_ticket_escalation_flag_compound():
    assert ticket_is_escalated(status=TicketStatus.OPEN, escalated_to_department="HR") is True
    assert (
        canonical_ticket_status(TicketStatus.OPEN, escalated_to_department="HR")
        == CANONICAL_ESCALATED
    )
    assert (
        canonical_ticket_status(TicketStatus.IN_PROGRESS, escalated_to_department="TECH")
        == CANONICAL_ESCALATED
    )
    # Terminal statuses are not escalated even with the flag set
    assert (
        canonical_ticket_status(TicketStatus.CLOSED, escalated_to_department="HR")
        == CANONICAL_CLOSED
    )
    assert (
        canonical_ticket_status(TicketStatus.RESOLVED, escalated_to_department="HR")
        == CANONICAL_CLOSED
    )


def test_incident_in_review_maps_only_to_escalated():
    assert canonical_incident_status(IncidentStatus.REPORTED) == CANONICAL_OPEN
    assert canonical_incident_status(IncidentStatus.IN_REVIEW) == CANONICAL_ESCALATED
    assert canonical_incident_status(IncidentStatus.ESCALATED) == CANONICAL_ESCALATED
    assert canonical_incident_status(IncidentStatus.ACTION_TAKEN) == CANONICAL_CLOSED
    assert canonical_incident_status(IncidentStatus.CLOSED) == CANONICAL_CLOSED
    # IN_REVIEW must never land in in_progress
    assert canonical_incident_status("IN_REVIEW") != CANONICAL_IN_PROGRESS
