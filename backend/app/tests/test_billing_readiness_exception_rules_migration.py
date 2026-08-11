"""Postgres up/down/up proof for billing_readiness_exception_rules (manual/CI gate).

Skips unless DATABASE_URL points at PostgreSQL. Never run against Railway.
"""
from __future__ import annotations

import os
import subprocess

import pytest
from sqlalchemy import create_engine, func, select, text

from app.core.config import settings
from app.models.billing_readiness_exception_rule import BillingReadinessExceptionRule


def _is_local_postgres(url: str) -> bool:
    u = (url or "").lower()
    if not u.startswith("postgresql"):
        return False
    if "railway" in u or "rlwy.net" in u:
        return False
    return True


@pytest.mark.skipif(
    not _is_local_postgres(settings.database_url),
    reason="Postgres migration proof requires local DATABASE_URL (not SQLite/Railway)",
)
def test_billing_readiness_exception_rules_postgres_up_down_up():
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM billing_readiness_exception_rules")
        ).scalar_one()
        assert int(before) >= 6

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    env = {**os.environ, "PYTHONPATH": f"{backend_dir}:{backend_dir}/alembic"}
    subprocess.run(["alembic", "downgrade", "c9d0e1f2a3b5"], cwd=backend_dir, env=env, check=True)
    subprocess.run(["alembic", "upgrade", "head"], cwd=backend_dir, env=env, check=True)

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT COUNT(*) FROM billing_readiness_exception_rules")
        ).scalar_one()
        assert int(after) >= 6

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(BillingReadinessExceptionRule)) or 0
        assert int(count) >= 6
    finally:
        db.close()
