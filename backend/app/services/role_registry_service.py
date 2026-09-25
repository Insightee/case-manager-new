"""Ensure coded roles (e.g. SPOT) exist in the database before assignment."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.models.role import Permission, Role


def _permissions_for_role(db: Session, role_name: str) -> list[Permission]:
    perm_names: list[str] = []
    for role_enum, names in ROLE_PERMISSIONS.items():
        if role_enum.value == role_name:
            perm_names = list(names)
            break
    if not perm_names:
        return []
    return list(db.scalars(select(Permission).where(Permission.name.in_(perm_names))).all())


def ensure_role(db: Session, role_name: str) -> Role:
    """Return Role row, creating registry entry + permissions when missing."""
    name = str(role_name).strip().upper()
    if not name:
        raise ValueError("Role name is required")

    known = any(role_enum.value == name for role_enum in ROLE_PERMISSIONS)
    if not known:
        raise ValueError(f"Unknown role: {name}")

    role = db.scalars(select(Role).where(Role.name == name)).first()
    if role:
        return role

    for perm_name in ALL_PERMISSIONS:
        if not db.scalars(select(Permission).where(Permission.name == perm_name)).first():
            db.add(Permission(name=perm_name))
    db.flush()

    role = Role(name=name)
    role.permissions = _permissions_for_role(db, name)
    db.add(role)
    db.flush()
    return role


def ensure_roles(db: Session, role_names: list[str]) -> list[Role]:
    return [ensure_role(db, name) for name in role_names]


def sync_missing_coded_roles(db: Session) -> None:
    """Idempotent: create any roles defined in ROLE_PERMISSIONS that are not in the DB yet."""
    for role_enum in ROLE_PERMISSIONS:
        ensure_role(db, role_enum.value)
