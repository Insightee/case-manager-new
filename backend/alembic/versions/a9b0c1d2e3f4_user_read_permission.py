"""Alembic migration: grant user.read permission to CASE_MANAGER and SUPERVISOR roles."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f7a8b9c0d1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (name)
            SELECT 'user.read'
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'user.read')
            """
        )
    )
    for role_name in ("CASE_MANAGER", "SUPERVISOR"):
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r
                CROSS JOIN permissions p
                WHERE r.name = :role_name
                  AND p.name = 'user.read'
                  AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.permission_id = p.id
                  )
                """
            ),
            {"role_name": role_name},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id = (SELECT id FROM permissions WHERE name = 'user.read')
              AND role_id IN (SELECT id FROM roles WHERE name IN ('CASE_MANAGER', 'SUPERVISOR'))
            """
        )
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE name = 'user.read'"))
