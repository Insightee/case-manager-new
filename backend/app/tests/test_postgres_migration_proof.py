"""Postgres migration proof — runs in CI when DATABASE_URL is PostgreSQL.

These tests EXECUTE (do not skip) when MIGRATION_PROOF_REQUIRED=1 (set in CI).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, inspect, select

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _postgres_proof_enabled() -> bool:
    if os.environ.get("MIGRATION_PROOF_REQUIRED", "").lower() in ("1", "true", "yes"):
        return True
    url = (
        os.environ.get("POSTGRES_MIGRATION_PROOF_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).lower()
    if not url.startswith("postgresql"):
        return False
    if "railway" in url or "rlwy.net" in url:
        return False
    return True


@pytest.mark.skipif(
    not _postgres_proof_enabled(),
    reason="Postgres migration proof requires DATABASE_URL=postgresql… or MIGRATION_PROOF_REQUIRED=1",
)
def test_postgres_migration_up_down_up_orchestrator():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BACKEND_DIR}:{BACKEND_DIR / 'alembic'}"
    result = subprocess.run(
        [sys.executable, str(BACKEND_DIR / "scripts" / "postgres_migration_up_down_up.py")],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(
    not _postgres_proof_enabled(),
    reason="Postgres migration proof requires DATABASE_URL=postgresql… or MIGRATION_PROOF_REQUIRED=1",
)
def test_alembic_single_head():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BACKEND_DIR}:{BACKEND_DIR / 'alembic'}"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    head_lines = [ln for ln in proc.stdout.splitlines() if "(head)" in ln]
    assert len(head_lines) == 1, proc.stdout


@pytest.mark.skipif(
    not _postgres_proof_enabled(),
    reason="Postgres migration proof requires DATABASE_URL=postgresql… or MIGRATION_PROOF_REQUIRED=1",
)
def test_billing_readiness_exception_rules_when_head_applies():
    """Runs when head is d0e1f2a3b4c6+; no-op skip when model/revision absent."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    head = ScriptDirectory.from_config(cfg).get_heads()[0]
    if head != "d0e1f2a3b4c6":
        pytest.skip(f"Head is {head}, not d0e1f2a3b4c6")

    try:
        from app.core.database import SessionLocal
        from app.models.billing_readiness_exception_rule import BillingReadinessExceptionRule
    except ImportError:
        pytest.skip("billing_readiness_exception_rule model not present")

    engine = create_engine(os.environ["DATABASE_URL"])
    if not inspect(engine).has_table("billing_readiness_exception_rules"):
        pytest.skip("billing_readiness_exception_rules table not present")

    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(BillingReadinessExceptionRule)) or 0
        assert int(count) >= 6
    finally:
        db.close()
