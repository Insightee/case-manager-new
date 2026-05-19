from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import redis
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

ALGORITHM = "HS256"
REFRESH_PREFIX = "refresh:"


_redis_client: redis.Redis | None = None
_use_memory_refresh = False


def get_redis() -> redis.Redis | None:
    global _redis_client, _use_memory_refresh
    if _use_memory_refresh:
        return None
    try:
        if _redis_client is None:
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
        return _redis_client
    except Exception:
        _use_memory_refresh = True
        return None


_memory_refresh: dict[str, str] = {}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    jti = str(uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh", "jti": jti}
    token = jwt.encode(payload, settings.jwt_refresh_secret_key, algorithm=ALGORITHM)
    r = get_redis()
    ttl = settings.jwt_refresh_token_expire_days * 86400
    if r:
        r.setex(f"{REFRESH_PREFIX}{jti}", ttl, subject)
    else:
        _memory_refresh[jti] = subject
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])


def decode_refresh_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_refresh_secret_key, algorithms=[ALGORITHM])


def revoke_refresh_token(jti: str) -> None:
    r = get_redis()
    if r:
        r.delete(f"{REFRESH_PREFIX}{jti}")
    else:
        _memory_refresh.pop(jti, None)


def is_refresh_token_valid(jti: str) -> bool:
    r = get_redis()
    if r:
        return r.exists(f"{REFRESH_PREFIX}{jti}") == 1
    return jti in _memory_refresh


def safe_decode_access(token: str) -> dict[str, Any] | None:
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
