"""Refresh token storage: Redis in production, in-memory fallback in dev only."""
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.core import security


@pytest.fixture(autouse=True)
def _reset_redis_state():
    security.reset_redis_client_for_tests()
    yield
    security.reset_redis_client_for_tests()


def _patch_redis_client(mock_client):
    """Patch connection pool so get_redis() receives mock_client."""
    mock_pool = MagicMock()
    return patch("app.core.security.redis.ConnectionPool.from_url", return_value=mock_pool), patch(
        "app.core.security.redis.Redis", return_value=mock_client
    )


def test_dev_uses_memory_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")

    mock_client = MagicMock()
    mock_client.ping.side_effect = ConnectionError("down")
    pool_patch, redis_patch = _patch_redis_client(mock_client)
    with pool_patch, redis_patch:
        token = security.create_refresh_token("42")
        payload = security.decode_refresh_token(token)
        assert security.is_refresh_token_valid(payload["jti"])


def test_production_raises_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "redis_url", "redis://redis.example.com:6379/0")

    mock_client = MagicMock()
    mock_client.ping.side_effect = ConnectionError("down")
    pool_patch, redis_patch = _patch_redis_client(mock_client)
    with pool_patch, redis_patch:
        with pytest.raises(RuntimeError, match="Redis is unreachable"):
            security.get_redis()


def test_production_stores_refresh_in_redis(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "redis_url", "redis://redis.example.com:6379/0")

    mock_client = MagicMock()
    mock_client.ping.return_value = True
    store: dict[str, str] = {}

    def setex(key, ttl, value):
        store[key] = value

    mock_client.setex.side_effect = setex
    mock_client.exists.side_effect = lambda key: 1 if key in store else 0
    mock_client.delete.side_effect = lambda key: store.pop(key, None)

    pool_patch, redis_patch = _patch_redis_client(mock_client)
    with pool_patch, redis_patch:
        token = security.create_refresh_token("99")
        payload = security.decode_refresh_token(token)
        jti = payload["jti"]
        assert security.is_refresh_token_valid(jti)
        security.revoke_refresh_token(jti)
        assert not security.is_refresh_token_valid(jti)
