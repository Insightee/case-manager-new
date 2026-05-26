from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.role import Role
from app.models.user import User


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    stmt = (
        select(User)
        .where(User.email == email.lower(), User.is_active.is_(True))
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = db.scalars(stmt).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    claims = {"roles": user.role_names, "permissions": list(user.permission_names)}
    access = create_access_token(str(user.id), claims)
    refresh = create_refresh_token(str(user.id))
    return access, refresh


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role_names: list[str],
    region: str | None = None,
    module_assignments: list[str] | None = None,
    is_view_only: bool = False,
) -> User:
    roles = db.scalars(select(Role).where(Role.name.in_(role_names))).all()
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        full_name=full_name,
        region=region,
        module_assignments=module_assignments or [],
        module_access_grants={},
        feature_overrides={},
        is_view_only=is_view_only,
    )
    user.roles = list(roles)
    db.add(user)
    db.flush()
    return user
