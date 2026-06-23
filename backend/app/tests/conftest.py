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


def cm_email_for_case_id(case_id: int) -> str:
    """Return the managing case manager email for a case (demo seed / RBAC tests)."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.case import Case
    from app.models.user import User

    with SessionLocal() as db:
        case = db.get(Case, case_id)
        if not case or not case.case_manager_user_id:
            raise AssertionError(f"No case manager on case {case_id}")
        cm = db.get(User, case.case_manager_user_id)
        if not cm or not cm.email:
            raise AssertionError(f"Case manager user missing for case {case_id}")
        return cm.email


def casemanager_homecare_case_id() -> int:
    """Case where casemanager@demo.com is the assigned CM (homecare)."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.case import Case
    from app.models.user import User

    with SessionLocal() as db:
        cm = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        assert cm, "casemanager@demo.com missing from seed"
        case = db.scalars(
            select(Case).where(
                Case.case_manager_user_id == cm.id,
                Case.product_module == "homecare",
            )
        ).first()
        assert case, "No homecare case managed by casemanager@demo.com"
        return case.id


def pending_log_for_cm_email(cm_email: str = "casemanager@demo.com") -> dict | None:
    """First pending daily log on a case managed by the given CM."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from app.core.database import SessionLocal
    from app.models.case import Case
    from app.models.daily_log import DailyLog, LogApprovalStatus
    from app.models.session import Session as TherapySession
    from app.models.user import User

    with SessionLocal() as db:
        cm = db.scalars(select(User).where(User.email == cm_email)).first()
        assert cm, f"{cm_email} missing from seed"
        log = db.scalars(
            select(DailyLog)
            .options(joinedload(DailyLog.session))
            .join(TherapySession, TherapySession.id == DailyLog.session_id)
            .join(Case, Case.id == TherapySession.case_id)
            .where(
                DailyLog.approval_status == LogApprovalStatus.PENDING,
                Case.case_manager_user_id == cm.id,
            )
        ).first()
        if not log:
            return None
        case_id = log.session.case_id
        managing_cm = db.get(User, db.get(Case, case_id).case_manager_user_id)
        return {
            "id": log.id,
            "case_id": case_id,
            "cm_email": managing_cm.email if managing_cm else cm_email,
        }
