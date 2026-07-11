"""Voice-first session log — session_audio_recordings table.

Revision ID: v0i1c2e3a4b5
Revises: i2n5s8g7h4t9
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_table

revision: str = "v0i1c2e3a4b5"
down_revision: Union[str, None] = "i2n5s8g7h4t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("session_audio_recordings"):
        op.create_table(
            "session_audio_recordings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "daily_log_id",
                sa.Integer(),
                sa.ForeignKey("daily_logs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
            sa.Column("therapist_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("storage_key", sa.String(length=512), nullable=False),
            sa.Column("mime_type", sa.String(length=128), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("recording_status", sa.String(length=32), nullable=False, server_default="UPLOADED"),
            sa.Column("transcription_status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("transcript", sa.Text(), nullable=True),
            sa.Column("transcript_language", sa.String(length=16), nullable=True),
            sa.Column("transcript_provider", sa.String(length=64), nullable=True),
            sa.Column("transcript_model", sa.String(length=128), nullable=True),
            sa.Column("transcript_confidence", sa.Integer(), nullable=True),
            sa.Column("processing_ms", sa.Integer(), nullable=True),
            sa.Column("extraction_json", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    create_index_if_missing("ix_session_audio_recordings_daily_log_id", "session_audio_recordings", ["daily_log_id"])
    create_index_if_missing("ix_session_audio_recordings_session_id", "session_audio_recordings", ["session_id"])
    create_index_if_missing("ix_session_audio_recordings_case_id", "session_audio_recordings", ["case_id"])
    create_index_if_missing("ix_session_audio_recordings_therapist_id", "session_audio_recordings", ["therapist_id"])


def downgrade() -> None:
    if has_table("session_audio_recordings"):
        op.drop_table("session_audio_recordings")
