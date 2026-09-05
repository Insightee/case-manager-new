"""CORS origin regex covers Vercel production aliases and git previews."""
from __future__ import annotations

import re

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "origin",
    [
        "https://frontend.vercel.app",
        "https://frontend-omega-eight-92.vercel.app",
        "https://frontend-insightes-projects.vercel.app",
        "https://frontend-git-main-insightes-projects.vercel.app",
        "https://frontend-abc123xyz-insightes-projects.vercel.app",
        "https://www.insighte.org",
        "https://insighte.org",
    ],
)
def test_production_cors_regex_matches_vercel_frontend_origins(origin: str):
    settings = Settings(app_env="production")
    pattern = settings.cors_origin_regex_effective
    assert pattern
    assert re.fullmatch(pattern, origin), f"{origin} did not match {pattern}"


@pytest.mark.parametrize(
    "origin",
    [
        "https://insightecasestaging-insightes-projects.vercel.app",
        "https://insightecasestaging.vercel.app",
        "https://insightecasetesting-insightes-projects.vercel.app",
        "https://insightecasetesting.vercel.app",
        "https://case-manager-new.vercel.app",
        "http://frontend-omega-eight-92.vercel.app",
    ],
)
def test_production_cors_regex_rejects_retired_or_unofficial_vercel_hosts(origin: str):
    settings = Settings(app_env="production")
    pattern = settings.cors_origin_regex_effective
    assert pattern
    assert re.fullmatch(pattern, origin) is None, f"{origin} unexpectedly matched {pattern}"


def test_development_has_no_cors_regex_by_default():
    settings = Settings(app_env="development")
    assert settings.cors_origin_regex_effective is None
