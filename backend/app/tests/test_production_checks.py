"""Production configuration guards."""
import pytest

from app.core.config import settings
from app.core.production_checks import validate_production_settings


def test_production_rejects_default_jwt(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "dev-secret-change-in-production")
    monkeypatch.setattr(settings, "jwt_refresh_secret_key", "ok-refresh-secret")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setattr(settings, "storage_provider", "r2")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example.com")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_production_settings()


def test_development_skips_validation(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "jwt_secret_key", "dev-secret-change-in-production")
    monkeypatch.setattr(settings, "storage_provider", "local")
    validate_production_settings()
