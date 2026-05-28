"""app usage chunks

Revision ID: u7v8w9x0y1z2
Revises: p1q2r3s4t5u6
Create Date: 2026-05-28 13:02:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "u7v8w9x0y1z2"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_usage_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=96), nullable=False),
        sa.Column("portal", sa.String(length=32), nullable=False),
        sa.Column("route", sa.String(length=512), nullable=True),
        sa.Column("active_seconds", sa.Integer(), nullable=False),
        sa.Column("idle_seconds", sa.Integer(), nullable=False),
        sa.Column("hidden_seconds", sa.Integer(), nullable=False),
        sa.Column("chunk_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chunk_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_user_id", "idempotency_key", name="uq_app_usage_chunks_actor_idempotency"),
    )
    op.create_index("ix_app_usage_chunks_actor_user_id", "app_usage_chunks", ["actor_user_id"], unique=False)
    op.create_index("ix_app_usage_chunks_session_id", "app_usage_chunks", ["session_id"], unique=False)
    op.create_index("ix_app_usage_chunks_portal", "app_usage_chunks", ["portal"], unique=False)
    op.create_index("ix_app_usage_chunks_created_at", "app_usage_chunks", ["created_at"], unique=False)
    op.create_index(
        "ix_app_usage_chunks_actor_portal_created",
        "app_usage_chunks",
        ["actor_user_id", "portal", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_entity_action_created_at",
        "audit_events",
        ["entity_type", "action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_entity_action_created_at", table_name="audit_events")
    op.drop_index("ix_app_usage_chunks_actor_portal_created", table_name="app_usage_chunks")
    op.drop_index("ix_app_usage_chunks_created_at", table_name="app_usage_chunks")
    op.drop_index("ix_app_usage_chunks_portal", table_name="app_usage_chunks")
    op.drop_index("ix_app_usage_chunks_session_id", table_name="app_usage_chunks")
    op.drop_index("ix_app_usage_chunks_actor_user_id", table_name="app_usage_chunks")
    op.drop_table("app_usage_chunks")
