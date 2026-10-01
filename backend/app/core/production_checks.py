"""Production startup validation (secrets, database, storage, CORS, email)."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from app.core.config import settings

# Extra Git-connected Vercel apps. Official UI is insightes-projects/frontend only.
_RETIRED_VERCEL_HOST_MARKERS = ("insightecasestaging", "insightecasetesting")


def _origin_host(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    return urlparse(value).netloc.lower()


def _retired_vercel_hosts(urls: list[str]) -> list[str]:
    """Return CORS/FRONTEND URLs that point at retired staging/testing Vercel apps."""
    found: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        value = (raw or "").strip()
        if not value or value in seen:
            continue
        host = _origin_host(value)
        if "vercel.app" not in host:
            continue
        if any(marker in host for marker in _RETIRED_VERCEL_HOST_MARKERS):
            seen.add(value)
            found.append(value)
    return found


_INSECURE_JWT_SECRETS = frozenset(
    {
        "dev-secret-change-in-production",
        "dev-refresh-secret-change-in-production",
        "dev-integration-secret-change-in-production",
        "change-me-in-production",
        "change-me-refresh-in-production",
        "change-me-integration-in-production",
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

    if settings.integration_api_enabled or settings.mcp_enabled:
        if settings.integration_jwt_secret_key.strip() in _INSECURE_JWT_SECRETS:
            errors.append(
                "INTEGRATION_JWT_SECRET_KEY must be a strong unique value when integration/MCP is enabled"
            )
        if settings.integration_jwt_secret_key.strip() in {
            settings.jwt_secret_key.strip(),
            settings.jwt_refresh_secret_key.strip(),
        }:
            errors.append("INTEGRATION_JWT_SECRET_KEY must differ from user JWT secrets")

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
        errors.append(
            "CORS_ORIGINS must include the production UI "
            "(insightes-projects/frontend or www.insighte.org)"
        )
    retired = _retired_vercel_hosts(cors + [settings.frontend_url or ""])
    if retired:
        errors.append(
            "CORS_ORIGINS / FRONTEND_URL must not list retired Vercel apps "
            f"({', '.join(retired)}). Use insightes-projects/frontend only "
            "(www.insighte.org or frontend*.vercel.app)."
        )

    frontend = (settings.frontend_url or "").strip()
    if not frontend or "localhost" in frontend or "127.0.0.1" in frontend:
        errors.append(
            "FRONTEND_URL must be the production UI "
            "(https://www.insighte.org or the frontend Vercel host), not localhost"
        )

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
