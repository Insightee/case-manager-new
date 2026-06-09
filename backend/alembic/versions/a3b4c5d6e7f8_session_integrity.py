"""Session integrity: schedule caps, idempotency, time edit fields."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table)


def upgrade() -> None:
    if not _has_column("sessions", "scheduled_duration_mins"):
        op.add_column("sessions", sa.Column("scheduled_duration_mins", sa.Integer(), nullable=True))
    if not _has_column("sessions", "overage_mins"):
        op.add_column("sessions", sa.Column("overage_mins", sa.Integer(), nullable=True))
    if not _has_column("sessions", "time_confirmation_required"):
        op.add_column(
            "sessions",
            sa.Column("time_confirmation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column("sessions", "actual_times_edited"):
        op.add_column(
            "sessions",
            sa.Column("actual_times_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column("sessions", "actual_times_edited_at"):
        op.add_column("sessions", sa.Column("actual_times_edited_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_column("sessions", "actual_times_edited_by"):
        op.add_column("sessions", sa.Column("actual_times_edited_by", sa.Integer(), nullable=True))
    if not _has_column("sessions", "actual_times_edit_reason"):
        op.add_column("sessions", sa.Column("actual_times_edit_reason", sa.String(512), nullable=True))
    if not _has_column("sessions", "is_additional_visit"):
        op.add_column(
            "sessions",
            sa.Column("is_additional_visit", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column("sessions", "additional_visit_reason"):
        op.add_column("sessions", sa.Column("additional_visit_reason", sa.String(64), nullable=True))
    if not _has_column("sessions", "resumed_count"):
        op.add_column(
            "sessions",
            sa.Column("resumed_count", sa.Integer(), nullable=False, server_default="0"),
        )
    bind = op.get_bind()
    insp = sa.inspect(bind)
    fk_names = {fk["name"] for fk in insp.get_foreign_keys("sessions")}
    if "fk_sessions_actual_times_edited_by" not in fk_names and _has_column("sessions", "actual_times_edited_by"):
        op.create_foreign_key(
            "fk_sessions_actual_times_edited_by",
            "sessions",
            "users",
            ["actual_times_edited_by"],
            ["id"],
        )

    if not _has_table("session_start_idempotency"):
        op.create_table(
            "session_start_idempotency",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
            sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("idempotency_key", name="uq_session_start_idempotency_key"),
        )
        op.create_index("ix_session_start_idempotency_key", "session_start_idempotency", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_session_start_idempotency_key", table_name="session_start_idempotency")
    op.drop_table("session_start_idempotency")
    op.drop_constraint("fk_sessions_actual_times_edited_by", "sessions", type_="foreignkey")
    for col in (
        "resumed_count",
        "additional_visit_reason",
        "is_additional_visit",
        "actual_times_edit_reason",
        "actual_times_edited_by",
        "actual_times_edited_at",
        "actual_times_edited",
        "time_confirmation_required",
        "overage_mins",
        "scheduled_duration_mins",
    ):
        op.drop_column("sessions", col)
