"""Production startup validation (secrets, database, storage, CORS, email)."""
from __future__ import annotations

import os

from app.core.config import settings

_INSECURE_JWT_SECRETS = frozenset(
    {
        "dev-secret-change-in-production",
        "dev-refresh-secret-change-in-production",
        "change-me-in-production",
        "change-me-refresh-in-production",
    }
)


def validate_production_settings() -> None:
    """Fail fast when production is misconfigured for healthcare deploys."""
    if settings.is_development:
        return

    errors: list[str] = []

    if settings.seed_demo_data:
        errors.append("SEED_DEMO_DATA must be false in production (demo seed is for local/staging only)")

    if settings.jwt_secret_key.strip() in _INSECURE_JWT_SECRETS:
        errors.append("JWT_SECRET_KEY must be a strong unique value (not a dev default)")
    if settings.jwt_refresh_secret_key.strip() in _INSECURE_JWT_SECRETS:
        errors.append("JWT_REFRESH_SECRET_KEY must be a strong unique value (not a dev default)")

    if settings.is_sqlite:
        errors.append("DATABASE_URL must be Postgres in production (SQLite is local dev only)")

    provider = (settings.storage_provider or "local").strip().lower()
    if provider == "local":
        errors.append(
            "STORAGE_PROVIDER must be 'r2' in production so PHI uploads are not stored on disk "
            "(set R2_* env vars; see backend/.env.example)"
        )
    elif provider == "r2":
        from app.storage.factory import _validate_r2_settings

        try:
            _validate_r2_settings()
        except RuntimeError as exc:
            errors.append(str(exc))

    redis_url = (settings.redis_url or "").strip()
    if not redis_url.startswith(("redis://", "rediss://")):
        errors.append(
            "REDIS_URL must be set to a Redis URL (redis:// or rediss://) in production for refresh tokens"
        )
    elif "localhost" in redis_url or "127.0.0.1" in redis_url:
        errors.append("REDIS_URL must not point at localhost in production")

    cors = settings.cors_origin_list
    if not cors or all("localhost" in o or "127.0.0.1" in o for o in cors):
        errors.append("CORS_ORIGINS must include your production Vercel URL(s)")

    frontend = (settings.frontend_url or "").strip()
    if not frontend or "localhost" in frontend or "127.0.0.1" in frontend:
        errors.append("FRONTEND_URL must be your production Vercel URL (not localhost)")

    if os.environ.get("SMTP_USERNAME", "").strip():
        errors.append(
            "Use SMTP_USER for ZeptoMail/SMTP auth, not SMTP_USERNAME (remove SMTP_USERNAME from Railway)"
        )

    email_provider = (settings.email_provider or "smtp").strip().lower()
    if email_provider in ("zeptomail", "zepto"):
        if not (settings.smtp_user or "").strip():
            errors.append("SMTP_USER is required when EMAIL_PROVIDER=zeptomail")
        if not (settings.smtp_password or "").strip():
            errors.append("SMTP_PASSWORD is required when EMAIL_PROVIDER=zeptomail")
        if not (settings.smtp_host or "").strip():
            errors.append("SMTP_HOST is required when EMAIL_PROVIDER=zeptomail")

    if errors:
        detail = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(f"Production configuration invalid:\n{detail}")

    from app.services.email.service import is_smtp_configured

    if not is_smtp_configured():
        import logging

        logging.getLogger("insightcase").warning(
            "SMTP is not fully configured in production; password reset and invite emails may fail."
        )
