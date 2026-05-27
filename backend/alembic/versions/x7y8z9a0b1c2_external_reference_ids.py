"""external reference ids on users, children, cases

Revision ID: x7y8z9a0b1c2
Revises: w6x7y8z9a0b1
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x7y8z9a0b1c2"
down_revision: Union[str, None] = "w6x7y8z9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    user_cols = {c["name"] for c in insp.get_columns("users")} if insp.has_table("users") else set()
    child_cols = {c["name"] for c in insp.get_columns("children")} if insp.has_table("children") else set()
    case_cols = {c["name"] for c in insp.get_columns("cases")} if insp.has_table("cases") else set()
    if "external_employee_id" not in user_cols:
        op.add_column("users", sa.Column("external_employee_id", sa.String(length=64), nullable=True))
    if "external_client_id" not in child_cols:
        op.add_column("children", sa.Column("external_client_id", sa.String(length=64), nullable=True))
    if "external_case_ref" not in case_cols:
        op.add_column("cases", sa.Column("external_case_ref", sa.String(length=128), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_users_external_employee_id",
            "users",
            ["external_employee_id"],
            unique=True,
            postgresql_where=sa.text("external_employee_id IS NOT NULL"),
        )
        op.create_index(
            "uq_children_external_client_id",
            "children",
            ["external_client_id"],
            unique=True,
            postgresql_where=sa.text("external_client_id IS NOT NULL"),
        )
        op.create_index(
            "uq_cases_external_case_ref",
            "cases",
            ["external_case_ref"],
            unique=True,
            postgresql_where=sa.text("external_case_ref IS NOT NULL"),
        )
    else:
        op.create_index("ix_users_external_employee_id", "users", ["external_employee_id"], unique=True)
        op.create_index("ix_children_external_client_id", "children", ["external_client_id"], unique=True)
        op.create_index("ix_cases_external_case_ref", "cases", ["external_case_ref"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("uq_cases_external_case_ref", table_name="cases")
        op.drop_index("uq_children_external_client_id", table_name="children")
        op.drop_index("uq_users_external_employee_id", table_name="users")
    else:
        op.drop_index("ix_cases_external_case_ref", table_name="cases")
        op.drop_index("ix_children_external_client_id", table_name="children")
        op.drop_index("ix_users_external_employee_id", table_name="users")
    op.drop_column("cases", "external_case_ref")
    op.drop_column("children", "external_client_id")
    op.drop_column("users", "external_employee_id")
