#!/usr/bin/env python3
"""Seeded Postgres up/down/up migration proof — CI gate (HARNESS-001/002).

1. Assert single Alembic head
2. upgrade head (greenfield create_all + stamp on empty DB)
3. demo_seed + head revision proof seed
4. downgrade <parent of head>
5. Assert head tables/columns gone; core tables intact
6. upgrade head again (idempotent re-apply)
7. Assert head schema restored

Exit 0 on success, 1 on failure. Never point at Railway/production.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "alembic"))

from scripts.postgres_migration_proof_registry import (  # noqa: E402
    assert_core_tables_intact,
    assert_head_absent,
    assert_head_present,
    head_config,
)


def _database_url() -> str:
    url = (
        os.environ.get("POSTGRES_MIGRATION_PROOF_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    )
    if not url:
        raise RuntimeError("DATABASE_URL is required for migration proof")
    lower = url.lower()
    if "railway" in lower or "rlwy.net" in lower:
        raise RuntimeError("Refusing migration proof against Railway DATABASE_URL")
    if not lower.startswith("postgresql"):
        raise RuntimeError(f"Migration proof requires PostgreSQL, got: {url.split(':/')[0]}")
    return url


def _alembic_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BACKEND_DIR}:{BACKEND_DIR / 'alembic'}"
    env.setdefault("APP_ENV", "test")
    env.setdefault("STORAGE_PROVIDER", "local")
    return env


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=_alembic_env(),
        check=True,
    )


def _linear_merge_parent(script: ScriptDirectory, head: str, parents: tuple[str, ...]) -> str:
    """Pick the merge parent that subsumes sibling branch work (for downgrade proof)."""
    for tip in parents:
        if not any(
            tip != other and tip in _revision_ancestor_ids(script, other)
            for other in parents
        ):
            return tip
    return parents[0]


def _revision_ancestor_ids(script: ScriptDirectory, revision_id: str) -> set[str]:
    rev = script.get_revision(revision_id)
    if rev is None:
        return set()
    down = rev.down_revision
    if down is None:
        return set()
    parent_ids = down if isinstance(down, (tuple, list)) else (down,)
    result = set(parent_ids)
    for parent in parent_ids:
        result |= _revision_ancestor_ids(script, parent)
    return result


def _head_and_parent() -> tuple[str, str]:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one Alembic head, got: {heads}")
    head = heads[0]
    rev = script.get_revision(head)
    parent = rev.down_revision
    if parent is None:
        raise RuntimeError(f"Head revision {head} has no down_revision — cannot run downgrade proof")
    if isinstance(parent, tuple):
        parent = _linear_merge_parent(script, head, parent)
    return head, parent


def _assert_single_head_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=BACKEND_DIR,
        env=_alembic_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    head_lines = [ln for ln in proc.stdout.splitlines() if "(head)" in ln]
    if len(head_lines) != 1:
        raise RuntimeError(f"alembic heads must show exactly one head:\n{proc.stdout}")


def _seed_demo_and_proof(head: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "app.seed.demo_seed"],
        cwd=BACKEND_DIR,
        env=_alembic_env(),
        check=True,
    )
    if not head_config(head):
        raise RuntimeError(
            f"Alembic head {head} is not registered in postgres_migration_proof_registry.py — "
            "add tables_added/columns_added and a seed() before merging."
        )
    subprocess.run(
        [sys.executable, "-m", "scripts.postgres_migration_proof_seed"],
        cwd=BACKEND_DIR,
        env=_alembic_env(),
        check=True,
    )


def _assert_seeded_rows(engine, head: str) -> None:
    meta = head_config(head)
    if not meta:
        return
    with engine.connect() as conn:
        for table in meta["tables_added"]:
            if not inspect(engine).has_table(table):
                raise AssertionError(f"Expected table {table} before downgrade")
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            if int(count or 0) < 1:
                raise AssertionError(f"Expected at least one seeded row in {table}, got {count}")


def main() -> int:
    url = _database_url()
    print("Postgres migration proof starting…")
    _assert_single_head_cli()
    head, parent = _head_and_parent()
    print(f"Head={head} parent={parent}")

    engine = create_engine(url)
    _run_alembic("upgrade", "head")
    _seed_demo_and_proof(head)
    _assert_seeded_rows(engine, head)

    print(f"Downgrading {head} -> {parent} …")
    _run_alembic("downgrade", parent)
    assert_head_absent(engine, head)
    assert_core_tables_intact(engine)

    print("Re-upgrading to head …")
    _run_alembic("upgrade", "head")
    assert_head_present(engine, head)

    print("Second upgrade head (idempotency) …")
    _run_alembic("upgrade", "head")
    assert_head_present(engine, head)

    print("Postgres migration proof PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Migration proof FAILED (subprocess exit {exc.returncode})", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"Migration proof FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
