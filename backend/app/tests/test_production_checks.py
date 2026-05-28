"""Production configuration guards."""
import os

import pytest

from app.core.config import settings
from app.core.production_checks import validate_production_settings


def _prod_baseline(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "prod-access-secret-unique-32chars-min")
    monkeypatch.setattr(settings, "jwt_refresh_secret_key", "prod-refresh-secret-unique-32chars-min")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg2://u:p@db.example.com/railway")
    monkeypatch.setattr(settings, "storage_provider", "r2")
    monkeypatch.setattr(settings, "r2_account_id", "acct")
    monkeypatch.setattr(settings, "r2_access_key_id", "key")
    monkeypatch.setattr(settings, "r2_secret_access_key", "secret")
    monkeypatch.setattr(settings, "r2_bucket_name", "bucket")
    monkeypatch.setattr(settings, "r2_endpoint_url", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setattr(settings, "redis_url", "redis://redis.example.com:6379/0")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example.com")
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    monkeypatch.setattr(settings, "seed_demo_data", False)
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)


def test_production_rejects_default_jwt(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret_key", "dev-secret-change-in-production")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_production_settings()


def test_production_rejects_seed_demo_data(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "seed_demo_data", True)
    with pytest.raises(RuntimeError, match="SEED_DEMO_DATA"):
        validate_production_settings()


def test_production_rejects_sqlite(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "database_url", "sqlite:///insightcase.db")
    with pytest.raises(RuntimeError, match="Postgres"):
        validate_production_settings()


def test_production_rejects_local_storage(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "storage_provider", "local")
    with pytest.raises(RuntimeError, match="STORAGE_PROVIDER"):
        validate_production_settings()


def test_production_requires_redis_url(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "redis_url", "")
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        validate_production_settings()


def test_production_rejects_localhost_redis(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        validate_production_settings()


def test_production_rejects_localhost_only_cors(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_production_settings()


def test_production_requires_r2_credentials(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "r2_access_key_id", "")
    with pytest.raises(RuntimeError, match="R2_ACCESS_KEY_ID"):
        validate_production_settings()


def test_production_requires_zeptomail_password(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setattr(settings, "email_provider", "zeptomail")
    monkeypatch.setattr(settings, "smtp_user", "emailapikey")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "smtp_host", "smtp.zeptomail.in")
    with pytest.raises(RuntimeError, match="SMTP_PASSWORD"):
        validate_production_settings()


def test_production_rejects_smtp_username_env(monkeypatch):
    _prod_baseline(monkeypatch)
    monkeypatch.setenv("SMTP_USERNAME", "wrong-var")
    with pytest.raises(RuntimeError, match="SMTP_USER"):
        validate_production_settings()


def test_development_skips_validation(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "jwt_secret_key", "dev-secret-change-in-production")
    monkeypatch.setattr(settings, "storage_provider", "local")
    validate_production_settings()
