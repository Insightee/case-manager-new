#!/usr/bin/env python3
"""One-off migration: ADMIN → MODULE_ADMIN; SUPERVISOR/VIEWER → CASE_MANAGER (+ view grants).

Run from backend/: python3 -m scripts.migrate_staff_roles
Or re-seed demo: python3 -m app.seed.demo_seed
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.core.permissions import RoleName
from app.core.rbac_access import sync_user_access_fields
from app.models.role import Role
from app.models.user import User

MIGRATE_ADMIN_TO = RoleName.MODULE_ADMIN.value
RETIRED_TO_CM = {
    RoleName.SUPERVISOR.value: False,
    RoleName.VIEWER.value: True,
}


def run(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        roles = {r.name: r for r in db.scalars(select(Role)).all()}
        users = db.scalars(select(User).options(selectinload(User.roles))).all()
        changed = 0
        for user in users:
            names = set(user.role_names or [])
            if not names.intersection({RoleName.ADMIN.value, *RETIRED_TO_CM}):
                continue
            new_names = [n for n in names if n not in ({RoleName.ADMIN.value, *RETIRED_TO_CM})]
            view_only = user.is_view_only
            modules = list(user.module_assignments or [])
            if RoleName.ADMIN.value in names:
                if MIGRATE_ADMIN_TO not in new_names:
                    new_names.append(MIGRATE_ADMIN_TO)
                user.roles = [roles[n] for n in new_names if n in roles]
                sync_user_access_fields(
                    user,
                    role_names=new_names,
                    module_assignments=modules,
                    view_only=view_only,
                )
                changed += 1
                print(f"  {user.email}: ADMIN → MODULE_ADMIN")
            for retired, force_view in RETIRED_TO_CM.items():
                if retired not in names:
                    continue
                if RoleName.CASE_MANAGER.value not in new_names:
                    new_names.append(RoleName.CASE_MANAGER.value)
                if force_view:
                    view_only = True
                user.roles = [roles[n] for n in new_names if n in roles]
                sync_user_access_fields(
                    user,
                    role_names=new_names,
                    module_assignments=modules,
                    view_only=view_only,
                )
                changed += 1
                print(f"  {user.email}: {retired} → CASE_MANAGER (view_only={view_only})")
        if dry_run:
            print(f"[dry-run] would update {changed} user(s)")
            db.rollback()
        else:
            db.commit()
            print(f"Migrated {changed} user(s).")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    run(dry_run="--dry-run" in sys.argv)
