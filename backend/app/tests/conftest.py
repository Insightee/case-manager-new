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
# Production defaults keep billing off; CI/unit suite exercises billing routes and ledger math.
os.environ["ENABLE_BILLING"] = "true"
os.environ["BILLING_LEDGER_WRITES"] = "true"
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
        [sys.executable, "-c", "from app.core.database import ensure_sqlite_schema_patches; ensure_sqlite_schema_patches()"],
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


def api_first_case_id(client, headers: dict, *, page_size: int = 1) -> int:
    """First case visible to the authenticated user (team-scoped for CMs)."""
    res = client.get(f"/api/v1/cases?page_size={page_size}", headers=headers)
    assert res.status_code == 200, res.text
    items = api_items(res.json())
    assert items, "Expected at least one visible case"
    return int(items[0]["id"])


def login_headers(client, email: str, password: str = "demo123") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def cm_headers_for_case(client, case_id: int, password: str = "demo123") -> dict[str, str]:
    """Auth headers for the case manager assigned to ``case_id``."""
    from app.core.database import SessionLocal
    from app.models.case import Case
    from app.models.user import User

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None and case.case_manager_user_id is not None
        cm = db.get(User, case.case_manager_user_id)
        assert cm is not None
        email = cm.email
    finally:
        db.close()
    return login_headers(client, email, password=password)
