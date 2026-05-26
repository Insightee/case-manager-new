"""Production startup validation (secrets, database, storage, CORS)."""
from __future__ import annotations

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

    cors = settings.cors_origin_list
    if not cors or all("localhost" in o or "127.0.0.1" in o for o in cors):
        errors.append("CORS_ORIGINS must include your production Vercel URL(s)")

    if errors:
        detail = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(f"Production configuration invalid:\n{detail}")

    if not (settings.redis_url or "").strip().startswith("redis://"):
        import logging

        logging.getLogger("insightcase").warning(
            "REDIS_URL is unset in production; refresh tokens use in-memory storage "
            "(not safe with multiple API replicas)."
        )
