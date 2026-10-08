"""therapist vault documents

Revision ID: tvault001
Revises: i2all3cases4fin
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migration_util import has_table

revision: str = "tvault001"
down_revision: Union[str, None] = "i2all3cases4fin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_NAME = "therapistvaultdocumentstatus"
_ENUM_VALUES = ("PENDING", "APPROVED", "REJECTED")


def _status_column():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME, create_type=False)
    return sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME)


def upgrade() -> None:
    if has_table("therapist_vault_documents"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                f"""
                DO $$ BEGIN
                    CREATE TYPE {_ENUM_NAME} AS ENUM (
                        'PENDING', 'APPROVED', 'REJECTED'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "therapist_vault_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("slot_key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            _status_column(),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("replaces_document_id", sa.Integer(), sa.ForeignKey("therapist_vault_documents.id"), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_therapist_vault_documents_therapist_user_id", "therapist_vault_documents", ["therapist_user_id"])
    op.create_index("ix_therapist_vault_documents_slot_key", "therapist_vault_documents", ["slot_key"])
    op.create_index(
        "ix_therapist_vault_documents_replaces_document_id", "therapist_vault_documents", ["replaces_document_id"]
    )


def downgrade() -> None:
    if not has_table("therapist_vault_documents"):
        return
    op.drop_index("ix_therapist_vault_documents_replaces_document_id", table_name="therapist_vault_documents")
    op.drop_index("ix_therapist_vault_documents_slot_key", table_name="therapist_vault_documents")
    op.drop_index("ix_therapist_vault_documents_therapist_user_id", table_name="therapist_vault_documents")
    op.drop_table("therapist_vault_documents")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(f"DROP TYPE IF EXISTS {_ENUM_NAME}"))
