"""case services and service-scoped assignments

Revision ID: w9x0y1z2a3b4
Revises: v1a2b3c4d5e6
Create Date: 2026-05-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w9x0y1z2a3b4"
down_revision: Union[str, None] = "v1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_columns(insp: sa.Inspector, table_name: str) -> set[str]:
    if not insp.has_table(table_name):
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("case_services"):
        op.create_table(
            "case_services",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("service_key", sa.String(length=64), nullable=False),
            sa.Column("product_module", sa.String(length=64), nullable=True),
            sa.Column("status", sa.Enum("ACTIVE", "PAUSED", "CLOSED", name="caseservicestatus"), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("case_id", "service_key", "status", name="uq_case_services_case_service_status"),
        )
    idx = {i["name"] for i in insp.get_indexes("case_services")} if insp.has_table("case_services") else set()
    if "ix_case_services_case_id" not in idx:
        op.create_index("ix_case_services_case_id", "case_services", ["case_id"], unique=False)
    if "ix_case_services_service_key" not in idx:
        op.create_index("ix_case_services_service_key", "case_services", ["service_key"], unique=False)
    if "ix_case_services_product_module" not in idx:
        op.create_index("ix_case_services_product_module", "case_services", ["product_module"], unique=False)
    if "ix_case_services_status" not in idx:
        op.create_index("ix_case_services_status", "case_services", ["status"], unique=False)

    assignment_cols = _table_columns(insp, "case_assignments")
    if "case_service_id" not in assignment_cols:
        op.add_column("case_assignments", sa.Column("case_service_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_case_assignments_case_service_id",
            "case_assignments",
            "case_services",
            ["case_service_id"],
            ["id"],
        )

    assignment_idx = {i["name"] for i in insp.get_indexes("case_assignments")} if insp.has_table("case_assignments") else set()
    if "ix_case_assignments_case_service_id" not in assignment_idx:
        op.create_index("ix_case_assignments_case_service_id", "case_assignments", ["case_service_id"], unique=False)
    if "ix_case_assignments_case_service_status" not in assignment_idx:
        op.create_index(
            "ix_case_assignments_case_service_status",
            "case_assignments",
            ["case_service_id", "status"],
            unique=False,
        )
    if "ix_case_assignments_service_therapist_status" not in assignment_idx:
        op.create_index(
            "ix_case_assignments_service_therapist_status",
            "case_assignments",
            ["case_service_id", "therapist_user_id", "status"],
            unique=False,
        )

    # Backfill: create one default ACTIVE service line per case from existing case fields.
    op.execute(
        sa.text(
            """
            INSERT INTO case_services (case_id, service_key, product_module, status, start_date, notes)
            SELECT c.id,
                   COALESCE(NULLIF(TRIM(c.service_type), ''), 'general') AS service_key,
                   c.product_module,
                   'ACTIVE' AS status,
                   DATE(c.created_at) AS start_date,
                   'Auto-created during multi-service migration' AS notes
            FROM cases c
            WHERE NOT EXISTS (
                SELECT 1
                FROM case_services cs
                WHERE cs.case_id = c.id AND cs.status = 'ACTIVE'
            )
            """
        )
    )

    # Backfill assignments into default active service line.
    op.execute(
        sa.text(
            """
            UPDATE case_assignments
            SET case_service_id = (
                SELECT cs.id
                FROM case_services cs
                WHERE cs.case_id = case_assignments.case_id
                  AND cs.status = 'ACTIVE'
                ORDER BY cs.id
                LIMIT 1
            )
            WHERE case_service_id IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("case_assignments"):
        assignment_idx = {i["name"] for i in insp.get_indexes("case_assignments")}
        if "ix_case_assignments_service_therapist_status" in assignment_idx:
            op.drop_index("ix_case_assignments_service_therapist_status", table_name="case_assignments")
        if "ix_case_assignments_case_service_status" in assignment_idx:
            op.drop_index("ix_case_assignments_case_service_status", table_name="case_assignments")
        if "ix_case_assignments_case_service_id" in assignment_idx:
            op.drop_index("ix_case_assignments_case_service_id", table_name="case_assignments")
        cols = _table_columns(insp, "case_assignments")
        if "case_service_id" in cols:
            op.drop_constraint("fk_case_assignments_case_service_id", "case_assignments", type_="foreignkey")
            op.drop_column("case_assignments", "case_service_id")

    if insp.has_table("case_services"):
        idx = {i["name"] for i in insp.get_indexes("case_services")}
        for name in (
            "ix_case_services_status",
            "ix_case_services_product_module",
            "ix_case_services_service_key",
            "ix_case_services_case_id",
        ):
            if name in idx:
                op.drop_index(name, table_name="case_services")
        op.drop_table("case_services")
