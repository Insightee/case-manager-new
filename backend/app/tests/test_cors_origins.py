"""CORS origin regex covers Vercel production aliases and git previews."""
from __future__ import annotations

import re

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "origin",
    [
        "https://frontend-omega-eight-92.vercel.app",
        "https://frontend-insightes-projects.vercel.app",
        "https://frontend-git-main-insightes-projects.vercel.app",
    ],
)
def test_production_cors_regex_matches_vercel_frontend_origins(origin: str):
    settings = Settings(app_env="production")
    pattern = settings.cors_origin_regex_effective
    assert pattern
    assert re.fullmatch(pattern, origin), f"{origin} did not match {pattern}"


def test_development_has_no_cors_regex_by_default():
    settings = Settings(app_env="development")
    assert settings.cors_origin_regex_effective is None
