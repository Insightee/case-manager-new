"""Email suppressions, extended email_logs, invite delivery tracking."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_index, has_table

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("email_suppressions"):
        op.create_table(
            "email_suppressions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("reason", sa.String(length=64), nullable=False),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "suppressed_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cleared_by", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["cleared_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_email_suppressions_email", "email_suppressions", ["email"])

    if has_table("email_logs"):
        if not has_column("email_logs", "entity_type"):
            op.add_column("email_logs", sa.Column("entity_type", sa.String(length=64), nullable=True))
        if not has_column("email_logs", "entity_id"):
            op.add_column("email_logs", sa.Column("entity_id", sa.Integer(), nullable=True))
        if not has_column("email_logs", "provider_request_id"):
            op.add_column(
                "email_logs", sa.Column("provider_request_id", sa.String(length=255), nullable=True)
            )
        if not has_column("email_logs", "attempt_count"):
            op.add_column(
                "email_logs",
                sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if not has_column("email_logs", "next_retry_at"):
            op.add_column("email_logs", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
        if not has_column("email_logs", "last_attempt_at"):
            op.add_column("email_logs", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
        if not has_column("email_logs", "idempotency_key"):
            op.add_column("email_logs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        if not has_column("email_logs", "updated_at"):
            op.add_column(
                "email_logs",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            )
        if not has_index("email_logs", "ix_email_logs_idempotency_key"):
            op.create_index("ix_email_logs_idempotency_key", "email_logs", ["idempotency_key"], unique=False)

    if has_table("invite_tokens"):
        cols = [
            ("email_delivery_status", sa.String(32), "not_sent"),
            ("email_attempt_count", sa.Integer(), "0"),
            ("email_first_attempt_at", sa.DateTime(timezone=True), None),
            ("email_last_attempt_at", sa.DateTime(timezone=True), None),
            ("email_next_retry_at", sa.DateTime(timezone=True), None),
            ("delivery_failed_at", sa.DateTime(timezone=True), None),
            ("expired_due_to_delivery_failure", sa.Boolean(), "0"),
            ("resend_allowed_at", sa.DateTime(timezone=True), None),
        ]
        for name, col_type, default in cols:
            if not has_column("invite_tokens", name):
                if default is not None and col_type is sa.Integer():
                    op.add_column(
                        "invite_tokens",
                        sa.Column(name, col_type, nullable=False, server_default=default),
                    )
                elif default is not None and col_type is sa.Boolean():
                    op.add_column(
                        "invite_tokens",
                        sa.Column(name, col_type, nullable=False, server_default=default),
                    )
                elif default is not None:
                    op.add_column(
                        "invite_tokens",
                        sa.Column(name, col_type, nullable=False, server_default=default),
                    )
                else:
                    op.add_column("invite_tokens", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    if has_table("invite_tokens"):
        for col in (
            "resend_allowed_at",
            "expired_due_to_delivery_failure",
            "delivery_failed_at",
            "email_next_retry_at",
            "email_last_attempt_at",
            "email_first_attempt_at",
            "email_attempt_count",
            "email_delivery_status",
        ):
            if has_column("invite_tokens", col):
                op.drop_column("invite_tokens", col)

    if has_table("email_logs"):
        if has_index("email_logs", "ix_email_logs_idempotency_key"):
            op.drop_index("ix_email_logs_idempotency_key", table_name="email_logs")
        for col in (
            "updated_at",
            "idempotency_key",
            "last_attempt_at",
            "next_retry_at",
            "attempt_count",
            "provider_request_id",
            "entity_id",
            "entity_type",
        ):
            if has_column("email_logs", col):
                op.drop_column("email_logs", col)

    if has_table("email_suppressions"):
        op.drop_index("ix_email_suppressions_email", table_name="email_suppressions")
        op.drop_table("email_suppressions")
