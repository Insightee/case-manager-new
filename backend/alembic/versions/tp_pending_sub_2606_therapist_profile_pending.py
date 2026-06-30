"""Therapist profile pending_submission + revert draft profiles to approved.

Revision ID: tp_pending_sub_2606
Revises: r2s3t4u5v6w7
Create Date: 2026-06-30

Staged listing edits stay in pending_submission while status remains APPROVED.
Data fix: DRAFT profiles with an approved baseline revert to APPROVED; others
are approved from current fields.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "tp_pending_sub_2606"
down_revision: Union[str, None] = "r2s3t4u5v6w7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SNAPSHOT_KEYS = (
    "display_name",
    "short_bio",
    "academic_qualifications",
    "professional_certificates",
    "services_offered",
)


def _parse_json(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    return json.loads(value)


def _apply_snapshot(row: dict, snapshot: dict) -> dict:
    out = dict(row)
    for key in SNAPSHOT_KEYS:
        if key in snapshot:
            out[key] = snapshot[key]
    return out


def _snapshot_from_row(row: dict) -> dict:
    return {
        "display_name": row.get("display_name"),
        "short_bio": row.get("short_bio"),
        "academic_qualifications": row.get("academic_qualifications"),
        "professional_certificates": _parse_json(row.get("professional_certificates")) or [],
        "services_offered": _parse_json(row.get("services_offered")) or [],
    }


def upgrade() -> None:
    if not has_column("therapist_profiles", "approved_snapshot"):
        op.add_column("therapist_profiles", sa.Column("approved_snapshot", sa.JSON(), nullable=True))
    if not has_column("therapist_profiles", "pending_submission"):
        op.add_column("therapist_profiles", sa.Column("pending_submission", sa.JSON(), nullable=True))

    conn = op.get_bind()
    draft_rows = conn.execute(
        sa.text(
            "SELECT id, display_name, short_bio, academic_qualifications, "
            "professional_certificates, services_offered, approved_snapshot "
            "FROM therapist_profiles WHERE status = 'DRAFT'"
        )
    ).mappings().all()

    for row in draft_rows:
        snap = _parse_json(row["approved_snapshot"])
        if snap:
            restored = _apply_snapshot(dict(row), snap)
        else:
            restored = dict(row)
        approved_snapshot = snap or _snapshot_from_row(restored)
        conn.execute(
            sa.text(
                "UPDATE therapist_profiles SET "
                "display_name = :display_name, short_bio = :short_bio, "
                "academic_qualifications = :academic_qualifications, "
                "professional_certificates = :professional_certificates, "
                "services_offered = :services_offered, "
                "approved_snapshot = :approved_snapshot, "
                "status = 'APPROVED', pending_submission = NULL, submitted_at = NULL "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "display_name": restored.get("display_name"),
                "short_bio": restored.get("short_bio"),
                "academic_qualifications": restored.get("academic_qualifications"),
                "professional_certificates": json.dumps(
                    _parse_json(restored.get("professional_certificates")) or []
                ),
                "services_offered": json.dumps(_parse_json(restored.get("services_offered")) or []),
                "approved_snapshot": json.dumps(approved_snapshot),
            },
        )

    pending_rows = conn.execute(
        sa.text(
            "SELECT id, display_name, short_bio, academic_qualifications, "
            "professional_certificates, services_offered, approved_snapshot "
            "FROM therapist_profiles WHERE status = 'PENDING' AND approved_snapshot IS NOT NULL"
        )
    ).mappings().all()

    for row in pending_rows:
        snap = _parse_json(row["approved_snapshot"])
        if not snap:
            continue
        pending_payload = _snapshot_from_row(dict(row))
        restored = _apply_snapshot(dict(row), snap)
        conn.execute(
            sa.text(
                "UPDATE therapist_profiles SET "
                "display_name = :display_name, short_bio = :short_bio, "
                "academic_qualifications = :academic_qualifications, "
                "professional_certificates = :professional_certificates, "
                "services_offered = :services_offered, "
                "status = 'APPROVED', pending_submission = :pending_submission "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "display_name": restored.get("display_name"),
                "short_bio": restored.get("short_bio"),
                "academic_qualifications": restored.get("academic_qualifications"),
                "professional_certificates": json.dumps(
                    _parse_json(restored.get("professional_certificates")) or []
                ),
                "services_offered": json.dumps(_parse_json(restored.get("services_offered")) or []),
                "pending_submission": json.dumps(pending_payload),
            },
        )


def downgrade() -> None:
    if has_column("therapist_profiles", "pending_submission"):
        op.drop_column("therapist_profiles", "pending_submission")
