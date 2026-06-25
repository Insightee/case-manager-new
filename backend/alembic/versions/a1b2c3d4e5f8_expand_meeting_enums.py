"""Expand meetingtype and meetingstatus Postgres enums for CM meetings.

Revision ID: a1b2c3d4e5f8
Revises: z9c0d1e2f3a7
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f8"
down_revision: Union[str, None] = "z9c0d1e2f3a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MEETING_TYPE_VALUES = (
    "OBSERVATION_REVIEW",
    "OBSERVATION_CHECKLIST_REVIEW",
    "IEP_MEETING",
    "MONTHLY_REPORT_REVIEW",
    "PROGRESS_REVIEW",
    "PARENT_MEETING",
    "SCHOOL_MEETING",
    "THERAPIST_SUPPORT",
    "MENTOR_REVIEW",
    "INCIDENT_REVIEW",
    "SUPPORT_TICKET_REVIEW",
    "ADMINISTRATIVE_MEETING",
    "TRANSITION_PLANNING",
    "CASE_CLOSURE_MEETING",
    "OTHER",
)

_MEETING_STATUS_VALUES = (
    "NO_SHOW",
    "RESCHEDULED",
)


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    for value in _MEETING_TYPE_VALUES:
        _pg_enum_value("meetingtype", value)
    for value in _MEETING_STATUS_VALUES:
        _pg_enum_value("meetingstatus", value)


def downgrade() -> None:
    # Postgres cannot remove enum values safely; no-op.
    pass
