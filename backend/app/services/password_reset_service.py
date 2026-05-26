from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_redis, hash_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.email.service import enqueue_password_reset_email

_RATE_PREFIX = "pwd_reset:"
_memory_rate: dict[str, list[float]] = {}


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not local:
        return "***"
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}" if domain else masked_local


def _rate_limit_key(email: str) -> str:
    return email.lower().strip()


def _rate_count(email: str) -> int:
    key = _rate_limit_key(email)
    r = get_redis()
    if r:
        redis_key = f"{_RATE_PREFIX}{key}"
        raw = r.get(redis_key)
        return int(raw) if raw else 0
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - 3600
    hits = [t for t in _memory_rate.get(key, []) if t >= window_start]
    _memory_rate[key] = hits
    return len(hits)


def is_rate_limited(email: str) -> bool:
    limit = max(1, settings.password_reset_rate_limit_per_hour)
    return _rate_count(email) >= limit


def record_rate_limit_hit(email: str) -> None:
    key = _rate_limit_key(email)
    r = get_redis()
    if r:
        redis_key = f"{_RATE_PREFIX}{key}"
        count = r.incr(redis_key)
        if count == 1:
            r.expire(redis_key, 3600)
        return
    now = datetime.now(timezone.utc).timestamp()
    hits = _memory_rate.get(key, [])
    hits.append(now)
    _memory_rate[key] = hits


def create_reset_token(db: Session, user: User) -> str:
    """Invalidate prior unused tokens, persist a new one, return plaintext token."""
    now = datetime.now(timezone.utc)
    pending = db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all()
    for row in pending:
        row.used_at = now

    plain = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(plain),
        expires_at=now + timedelta(hours=settings.password_reset_expire_hours),
        created_at=now,
    )
    db.add(token_row)
    db.flush()
    return plain


def get_valid_token_row(db: Session, plain_token: str) -> PasswordResetToken | None:
    token_hash = hash_reset_token(plain_token)
    row = db.scalars(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()
    if not row or row.used_at:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    return row


def request_password_reset(
    db: Session,
    email: str,
    background_tasks: BackgroundTasks,
) -> int | None:
    """Create token and queue reset email when user exists; always safe to call."""
    email_l = email.lower().strip()
    if is_rate_limited(email_l):
        return None
    user = db.scalars(
        select(User).where(User.email == email_l, User.is_active.is_(True))
    ).first()
    if not user:
        return None
    record_rate_limit_hit(email_l)
    plain = create_reset_token(db, user)
    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password/{plain}"
    return enqueue_password_reset_email(
        background_tasks,
        db,
        to=user.email,
        full_name=user.full_name or user.email,
        reset_url=reset_url,
        expires_hours=settings.password_reset_expire_hours,
    )


def reset_password(db: Session, plain_token: str, new_password: str) -> User:
    row = get_valid_token_row(db, plain_token)
    if not row:
        raise ValueError("Invalid or expired reset link")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise ValueError("Invalid or expired reset link")
    user.password_hash = hash_password(new_password)
    row.used_at = datetime.now(timezone.utc)
    return user
