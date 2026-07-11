"""Environment-gated product modules for safe staged rollout."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import settings


def _reports_module_active() -> bool:
    env = settings.app_env.lower()
    if settings.enable_reports:
        return True
    return env in ("development", "dev", "local", "test", "staging", "testing")


def _feature_unavailable() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="This feature is not available in this environment.",
    )


def require_reports() -> None:
    if not _reports_module_active():
        _feature_unavailable()


def require_billing() -> None:
    if not settings.enable_billing:
        _feature_unavailable()


def require_clinical_brain() -> None:
    if not settings.enable_clinical_brain:
        _feature_unavailable()


def require_report_generation() -> None:
    if not settings.enable_report_generation:
        _feature_unavailable()


def voice_session_log_active() -> bool:
    if settings.enable_voice_session_log:
        return True
    env = settings.app_env.lower()
    return env in ("development", "dev", "local", "test", "staging", "testing")


def require_voice_session_log() -> None:
    if not voice_session_log_active():
        _feature_unavailable()
