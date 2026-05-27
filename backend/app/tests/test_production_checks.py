"""Production configuration guards."""
import os

import pytest

from app.core.config import settings
from app.core.production_checks import validate_production_settings


def _prod_baseline(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "prod-access-secret-unique-32chars-min")
    monkeypatch.setattr(settings, "jwt_refresh_secret_key", "prod-refresh-secret-unique-32chars-min")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setattr(settings, "storage_provider", "r2")
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
