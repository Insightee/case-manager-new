"""Tests for alembic_version row compaction after reparented merge migrations."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.db.alembic_version_cleanup import (
    compact_stale_version_rows,
    current_revision,
    effective_stored_revision,
    stale_version_rows,
)

_BACKEND = Path(__file__).resolve().parents[2]
_ALEMBIC_DIR = str(_BACKEND / "alembic")


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    # Migration files import migration_util from backend/alembic (same as CI alembic heads step).
    if _ALEMBIC_DIR not in sys.path:
        sys.path.insert(0, _ALEMBIC_DIR)
    cfg = Config(str(_BACKEND / "alembic.ini"))
    return ScriptDirectory.from_config(cfg)


def test_stale_version_rows_detects_reparented_ancestor(script: ScriptDirectory) -> None:
    versions = ["d0b7effca6df", "z9c0d1e2f3a7"]
    stale = stale_version_rows(script, versions)
    assert stale == {"d0b7effca6df"}


def test_stale_version_rows_keeps_sibling_heads(script: ScriptDirectory) -> None:
    versions = ["c6b1725843e6", "p2q3r4s5t6u7"]
    assert stale_version_rows(script, versions) == set()


def test_effective_stored_revision_prefers_descendant(script: ScriptDirectory) -> None:
    versions = ["d0b7effca6df", "z9c0d1e2f3a7"]
    assert effective_stored_revision(script, versions) == "z9c0d1e2f3a7"


def test_compact_stale_version_rows_removes_ancestor_row(script: ScriptDirectory) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('d0b7effca6df')")
        )
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('z9c0d1e2f3a7')")
        )

    kept = compact_stale_version_rows(engine, script)
    assert kept == ["z9c0d1e2f3a7"]
    assert current_revision(engine, script) == "z9c0d1e2f3a7"

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    assert [row[0] for row in rows] == ["z9c0d1e2f3a7"]
