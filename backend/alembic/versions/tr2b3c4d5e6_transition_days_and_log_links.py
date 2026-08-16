"""normalize transition days and link transition logs

Revision ID: tr2b3c4d5e6
Revises: tr1a2n3s4t5
Create Date: 2026-08-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tr2b3c4d5e6"
down_revision: Union[str, None] = "tr1a2n3s4t5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("case_therapist_transitions", "day_type"):
        op.add_column(
            "case_therapist_transitions",
            sa.Column("day_type", sa.String(length=16), nullable=True),
        )
        op.add_column(
            "case_therapist_transitions",
            sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        )
        op.add_column(
            "case_therapist_transitions",
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            "case_therapist_transitions",
            sa.Column("cancellation_reason", sa.Text(), nullable=True),
        )
        op.create_foreign_key(
            "fk_transition_cancelled_by",
            "case_therapist_transitions",
            "users",
            ["cancelled_by_user_id"],
            ["id"],
        )

    if not sa.inspect(op.get_bind()).has_table("case_therapist_transition_days"):
        op.create_table(
            "case_therapist_transition_days",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("transition_id", sa.Integer(), nullable=False),
            sa.Column("transition_date", sa.Date(), nullable=False),
            sa.Column("day_type", sa.String(length=16), nullable=True),
            sa.Column("pay_rate_inr", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["transition_id"],
                ["case_therapist_transitions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "transition_id",
                "transition_date",
                name="uq_transition_day_date",
            ),
        )
        op.create_index(
            "ix_case_therapist_transition_days_transition_id",
            "case_therapist_transition_days",
            ["transition_id"],
        )
        op.create_index(
            "ix_case_therapist_transition_days_transition_date",
            "case_therapist_transition_days",
            ["transition_date"],
        )

    if not _has_column("daily_logs", "transition_id"):
        op.add_column("daily_logs", sa.Column("transition_id", sa.Integer(), nullable=True))
        op.add_column("daily_logs", sa.Column("transition_day_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_daily_logs_transition",
            "daily_logs",
            "case_therapist_transitions",
            ["transition_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_daily_logs_transition_day",
            "daily_logs",
            "case_therapist_transition_days",
            ["transition_day_id"],
            ["id"],
        )
        op.create_index("ix_daily_logs_transition_id", "daily_logs", ["transition_id"])
        op.create_index("ix_daily_logs_transition_day_id", "daily_logs", ["transition_day_id"])


def downgrade() -> None:
    if _has_column("daily_logs", "transition_id"):
        op.drop_index("ix_daily_logs_transition_day_id", table_name="daily_logs")
        op.drop_index("ix_daily_logs_transition_id", table_name="daily_logs")
        op.drop_constraint("fk_daily_logs_transition_day", "daily_logs", type_="foreignkey")
        op.drop_constraint("fk_daily_logs_transition", "daily_logs", type_="foreignkey")
        op.drop_column("daily_logs", "transition_day_id")
        op.drop_column("daily_logs", "transition_id")

    if sa.inspect(op.get_bind()).has_table("case_therapist_transition_days"):
        op.drop_index(
            "ix_case_therapist_transition_days_transition_date",
            table_name="case_therapist_transition_days",
        )
        op.drop_index(
            "ix_case_therapist_transition_days_transition_id",
            table_name="case_therapist_transition_days",
        )
        op.drop_table("case_therapist_transition_days")

    if _has_column("case_therapist_transitions", "day_type"):
        op.drop_constraint(
            "fk_transition_cancelled_by",
            "case_therapist_transitions",
            type_="foreignkey",
        )
        op.drop_column("case_therapist_transitions", "cancellation_reason")
        op.drop_column("case_therapist_transitions", "cancelled_at")
        op.drop_column("case_therapist_transitions", "cancelled_by_user_id")
        op.drop_column("case_therapist_transitions", "day_type")
