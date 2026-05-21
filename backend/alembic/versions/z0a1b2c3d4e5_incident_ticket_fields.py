"""incident ticket fields, status migration, incident_attachments

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z0a1b2c3d4e5"
down_revision: Union[str, None] = "y9z0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("ticket_code", sa.String(32), nullable=True))
    op.add_column("incidents", sa.Column("primary_category", sa.String(64), nullable=True))
    op.add_column("incidents", sa.Column("subcategory", sa.String(64), nullable=True))
    op.add_column("incidents", sa.Column("priority", sa.String(16), nullable=True))
    op.add_column("incidents", sa.Column("service_type", sa.String(32), nullable=True))
    op.add_column("incidents", sa.Column("incident_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("location", sa.String(32), nullable=True))
    op.add_column("incidents", sa.Column("immediate_action", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("child_safe", sa.String(8), nullable=True))
    op.add_column("incidents", sa.Column("parent_informed", sa.String(8), nullable=True))
    op.add_column("incidents", sa.Column("primary_owner_role", sa.String(32), nullable=True))
    op.add_column("incidents", sa.Column("tagged_roles", sa.JSON(), nullable=True))
    op.add_column("incidents", sa.Column("action_taken_note", sa.Text(), nullable=True))
    op.add_column("incidents", sa.Column("last_owner_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("sla_reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE incidents SET status = 'REPORTED' WHERE status = 'OPEN'")
    op.execute("UPDATE incidents SET status = 'IN_REVIEW' WHERE status = 'INVESTIGATING'")
    op.execute("UPDATE incidents SET status = 'ACTION_TAKEN' WHERE status = 'RESOLVED'")

    op.execute(
        "UPDATE incidents SET ticket_code = 'INC-LEGACY-' || id WHERE ticket_code IS NULL"
    )

    op.create_index("ix_incidents_ticket_code", "incidents", ["ticket_code"], unique=True)
    op.create_index("ix_incidents_primary_category", "incidents", ["primary_category"])

    op.create_table(
        "incident_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("incident_messages.id"), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_incident_attachments_incident_id", "incident_attachments", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incident_attachments_incident_id", table_name="incident_attachments")
    op.drop_table("incident_attachments")
    op.drop_index("ix_incidents_primary_category", table_name="incidents")
    op.drop_index("ix_incidents_ticket_code", table_name="incidents")
    for col in (
        "escalated_at",
        "sla_reminder_sent_at",
        "last_owner_activity_at",
        "action_taken_note",
        "tagged_roles",
        "primary_owner_role",
        "parent_informed",
        "child_safe",
        "immediate_action",
        "location",
        "incident_at",
        "service_type",
        "priority",
        "subcategory",
        "primary_category",
        "ticket_code",
    ):
        op.drop_column("incidents", col)
