"""Alembic 'heads' literal stamp must not block incremental migrations."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_BACKEND / "alembic") not in sys.path:
    sys.path.insert(0, str(_BACKEND / "alembic"))

import app.models  # noqa: F401
from app.core.database import Base
from scripts.migrate_production import _reconcile_heads_literal


@pytest.fixture()
def sqlite_db_with_heads_stamp(tmp_path):
    db_path = tmp_path / "heads.db"
    url = f"sqlite:///{db_path}"
    eng = create_engine(url)
    Base.metadata.create_all(bind=eng)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('heads')"))
        for idx in (
            "ix_daily_logs_visibility_status",
            "ix_daily_logs_approval_visibility_submitted",
        ):
            conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))
        conn.execute(text("ALTER TABLE daily_logs DROP COLUMN visibility_status"))
    yield eng, url
    eng.dispose()


def test_reconcile_heads_literal_replaces_with_merge_parent(monkeypatch, sqlite_db_with_heads_stamp):
    eng, url = sqlite_db_with_heads_stamp
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    script = ScriptDirectory.from_config(cfg)

    import scripts.migrate_production as mp

    monkeypatch.setattr(mp, "engine", eng)
    _reconcile_heads_literal(cfg, script)

    with eng.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    assert row is not None
    assert row[0] == "p0q1r2s3t4u5"
