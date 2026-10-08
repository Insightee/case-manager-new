from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.role import Role
from app.models.user import User


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return user when credentials match. Caller must enforce login eligibility separately."""
    stmt = (
        select(User)
        .where(User.email == email.lower())
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = db.scalars(stmt).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def issue_tokens(user: User, *, remember_me: bool = False) -> tuple[str, str]:
    claims = {"roles": user.role_names, "permissions": list(user.permission_names)}
    access = create_access_token(str(user.id), claims)
    refresh = create_refresh_token(str(user.id), remember_me=remember_me)
    return access, refresh


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role_names: list[str],
    region: str | None = None,
    department: str | None = None,
    module_assignments: list[str] | None = None,
    external_employee_id: str | None = None,
    is_view_only: bool = False,
) -> User:
    from app.services.external_employee_id_service import normalize_external_employee_id

    from app.services.role_registry_service import ensure_roles

    roles = ensure_roles(db, role_names)
    user = User(
        email=email.lower(),
        external_employee_id=normalize_external_employee_id(external_employee_id),
        password_hash=hash_password(password),
        full_name=full_name,
        region=region,
        department=department,
        module_assignments=module_assignments or [],
        module_access_grants={},
        feature_overrides={},
        is_view_only=is_view_only,
    )
    user.roles = list(roles)
    db.add(user)
    db.flush()
    return user


_CHANGE_PWD_FAIL_PREFIX = "change_pwd_fail:"
_memory_change_pwd_fail: dict[str, list[float]] = {}
_CHANGE_PWD_FAIL_LIMIT = 8
_CHANGE_PWD_FAIL_WINDOW_SEC = 3600


def _change_pwd_fail_key(user_id: int) -> str:
    return str(user_id)


def is_change_password_rate_limited(user_id: int) -> bool:
    from datetime import datetime, timezone

    from app.core.security import get_redis

    key = _change_pwd_fail_key(user_id)
    r = get_redis()
    if r:
        count = int(r.get(f"{_CHANGE_PWD_FAIL_PREFIX}{key}") or 0)
        return count >= _CHANGE_PWD_FAIL_LIMIT
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - _CHANGE_PWD_FAIL_WINDOW_SEC
    hits = [t for t in _memory_change_pwd_fail.get(key, []) if t >= window_start]
    _memory_change_pwd_fail[key] = hits
    return len(hits) >= _CHANGE_PWD_FAIL_LIMIT


def record_change_password_failure(user_id: int) -> None:
    from datetime import datetime, timezone

    from app.core.security import get_redis

    key = _change_pwd_fail_key(user_id)
    r = get_redis()
    if r:
        redis_key = f"{_CHANGE_PWD_FAIL_PREFIX}{key}"
        count = r.incr(redis_key)
        if count == 1:
            r.expire(redis_key, _CHANGE_PWD_FAIL_WINDOW_SEC)
        return
    now = datetime.now(timezone.utc).timestamp()
    hits = _memory_change_pwd_fail.get(key, [])
    hits.append(now)
    _memory_change_pwd_fail[key] = hits


def clear_change_password_failures(user_id: int) -> None:
    from app.core.security import get_redis

    key = _change_pwd_fail_key(user_id)
    r = get_redis()
    if r:
        r.delete(f"{_CHANGE_PWD_FAIL_PREFIX}{key}")
        return
    _memory_change_pwd_fail.pop(key, None)
