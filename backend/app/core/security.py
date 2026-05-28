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

_REDIS_CONNECT_TIMEOUT_S = 2
_REDIS_SOCKET_TIMEOUT_S = 2

_redis_pool: redis.ConnectionPool | None = None
_redis_client: redis.Redis | None = None
_use_memory_refresh = False
_memory_refresh: dict[str, str] = {}


def reset_redis_client_for_tests() -> None:
    """Clear cached Redis client between tests."""
    global _redis_pool, _redis_client, _use_memory_refresh
    _redis_pool = None
    _redis_client = None
    _use_memory_refresh = False
    _memory_refresh.clear()


def _allow_memory_refresh_fallback() -> bool:
    return settings.is_development


def _redis_pool_kwargs() -> dict[str, Any]:
    return {
        "decode_responses": True,
        "socket_connect_timeout": _REDIS_CONNECT_TIMEOUT_S,
        "socket_timeout": _REDIS_SOCKET_TIMEOUT_S,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    }


def _try_connect_redis() -> redis.Redis | None:
    global _redis_pool, _redis_client
    try:
        if _redis_pool is None:
            _redis_pool = redis.ConnectionPool.from_url(settings.redis_url, **_redis_pool_kwargs())
        if _redis_client is None:
            _redis_client = redis.Redis(connection_pool=_redis_pool)
        _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        if _redis_pool is not None:
            try:
                _redis_pool.disconnect()
            except Exception:
                pass
        _redis_pool = None
        return None


def get_redis() -> redis.Redis | None:
    global _use_memory_refresh
    if _use_memory_refresh and _allow_memory_refresh_fallback():
        return None
    client = _try_connect_redis()
    if client is not None:
        return client
    if not _allow_memory_refresh_fallback():
        raise RuntimeError(
            "REDIS_URL is required in production but Redis is unreachable. "
            "Check Railway Redis plugin and REDIS_URL on the API service."
        )
    _use_memory_refresh = True
    return None


def warm_redis_connection() -> str:
    """Probe Redis at startup; return status for health/logging."""
    if settings.is_development and _use_memory_refresh:
        return "memory_fallback"
    try:
        client = get_redis()
        if client is None:
            return "memory_fallback" if _allow_memory_refresh_fallback() else "unavailable"
        return "ok"
    except RuntimeError:
        return "fail"


def ping_redis_for_health() -> str:
    """Fast Redis check for /health (does not flip dev to memory fallback)."""
    if _use_memory_refresh and _allow_memory_refresh_fallback():
        return "memory_fallback"
    client = _try_connect_redis()
    if client is not None:
        return "ok"
    if _allow_memory_refresh_fallback():
        return "memory_fallback"
    return "fail"


def verify_redis_at_startup() -> None:
    """Fail fast in production when refresh-token Redis is not reachable."""
    if settings.is_development:
        warm_redis_connection()
        return
    status = ping_redis_for_health()
    if status == "fail":
        raise RuntimeError("REDIS_URL is required in production for refresh token storage")


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
