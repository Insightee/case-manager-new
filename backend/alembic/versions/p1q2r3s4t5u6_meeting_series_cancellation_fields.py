"""meeting series and cancellation fields

Revision ID: q1q2r3s4t5u6
Revises: k2pct2lumpfix
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q1q2r3s4t5u6"
down_revision: Union[str, None] = "k2pct2lumpfix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _series_uuid_for_root(root_meeting_id: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"case_manager_meetings:{root_meeting_id}"))


def upgrade() -> None:
    op.add_column("case_manager_meetings", sa.Column("series_id", sa.String(length=36), nullable=True))
    op.add_column("case_manager_meetings", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column(
        "case_manager_meetings",
        sa.Column("cancelled_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("case_manager_meetings", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("case_manager_meetings", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, rescheduled_from_id, series_id FROM case_manager_meetings")
    ).mappings().all()
    rows_by_id = {int(row["id"]): row for row in rows}

    def root_meeting_id(meeting_id: int) -> int:
        seen: set[int] = set()
        current = meeting_id
        while current and current not in seen:
            seen.add(current)
            row = rows_by_id.get(current)
            if not row:
                return current
            parent_id = row["rescheduled_from_id"]
            if parent_id is None:
                return current
            current = int(parent_id)
        return meeting_id

    for row in rows:
        if row["series_id"]:
            continue
        root_id = root_meeting_id(int(row["id"]))
        conn.execute(
            sa.text(
                "UPDATE case_manager_meetings "
                "SET series_id = :series_id "
                "WHERE id = :id AND series_id IS NULL"
            ),
            {"series_id": _series_uuid_for_root(root_id), "id": int(row["id"])},
        )

    op.alter_column("case_manager_meetings", "series_id", nullable=False)
    op.create_index("ix_case_manager_meetings_series_id", "case_manager_meetings", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_case_manager_meetings_series_id", table_name="case_manager_meetings")
    op.drop_column("case_manager_meetings", "reminder_sent_at")
    op.drop_column("case_manager_meetings", "cancelled_at")
    op.drop_column("case_manager_meetings", "cancelled_by_user_id")
    op.drop_column("case_manager_meetings", "cancel_reason")
    op.drop_column("case_manager_meetings", "series_id")
