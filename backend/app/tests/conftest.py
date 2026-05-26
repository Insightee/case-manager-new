"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_TEST_DB = _BACKEND_ROOT / f"test_ci_{os.getpid()}.db"

# Must run before test modules import app.main (engine binds to DATABASE_URL).
os.environ.setdefault("STORAGE_PROVIDER", "local")
os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

_BOOTSTRAP_DONE = False


def _bootstrap_test_database() -> None:
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    env = {**os.environ, "PYTHONPATH": f"{_BACKEND_ROOT}:{_BACKEND_ROOT / 'alembic'}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "app.seed.demo_seed"],
        cwd=_BACKEND_ROOT,
        env=env,
        check=True,
    )
    _BOOTSTRAP_DONE = True


_bootstrap_test_database()


def api_items(data):
    """Unwrap paginated API responses for assertions."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data
