"""case therapist transition handover

Revision ID: tr1a2n3s4t5
Revises: z8a9b0c1d2e3
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tr1a2n3s4t5"
down_revision: Union[str, None] = "z8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table)


def upgrade() -> None:
    if _has_table("case_therapist_transitions"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE casetherapisttransitionstatus AS ENUM (
                        'SCHEDULED', 'ACTIVE', 'COMPLETED', 'CANCELLED'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        status_col = sa.Enum(
            "SCHEDULED",
            "ACTIVE",
            "COMPLETED",
            "CANCELLED",
            name="casetherapisttransitionstatus",
            create_type=False,
        )
    else:
        status_col = sa.Enum(
            "SCHEDULED",
            "ACTIVE",
            "COMPLETED",
            "CANCELLED",
            name="casetherapisttransitionstatus",
        )

    op.create_table(
        "case_therapist_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("case_service_id", sa.Integer(), nullable=False),
        sa.Column("outgoing_therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("incoming_therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("outgoing_assignment_id", sa.Integer(), nullable=False),
        sa.Column("incoming_assignment_id", sa.Integer(), nullable=False),
        sa.Column("transition_dates", sa.JSON(), nullable=False),
        sa.Column("status", status_col, nullable=False),
        sa.Column("pending_billing_update", sa.JSON(), nullable=False),
        sa.Column("full_day_pay_inr", sa.Numeric(12, 2), nullable=False, server_default="500"),
        sa.Column("half_day_pay_inr", sa.Numeric(12, 2), nullable=False, server_default="350"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["case_service_id"], ["case_services.id"]),
        sa.ForeignKeyConstraint(["outgoing_therapist_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["incoming_therapist_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["outgoing_assignment_id"], ["case_assignments.id"]),
        sa.ForeignKeyConstraint(["incoming_assignment_id"], ["case_assignments.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_therapist_transitions_case_id", "case_therapist_transitions", ["case_id"])
    op.create_index("ix_case_therapist_transitions_status", "case_therapist_transitions", ["status"])


def downgrade() -> None:
    if not _has_table("case_therapist_transitions"):
        return
    op.drop_index("ix_case_therapist_transitions_status", table_name="case_therapist_transitions")
    op.drop_index("ix_case_therapist_transitions_case_id", table_name="case_therapist_transitions")
    op.drop_table("case_therapist_transitions")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DROP TYPE IF EXISTS casetherapisttransitionstatus"))
