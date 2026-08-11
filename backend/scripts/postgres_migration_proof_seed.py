"""Seed FK-backed rows for the current Alembic head revision(s).

Run after `alembic upgrade head` + `app.seed.demo_seed` on throwaway Postgres.

Usage:
  export DATABASE_URL=postgresql+psycopg2://...
  python3 -m scripts.postgres_migration_proof_seed
"""
from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.database import SessionLocal
from scripts.postgres_migration_proof_registry import head_config


def _resolve_head_revision() -> str:
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected single Alembic head, got: {heads}")
    return heads[0]


def run(*, head_revision: str | None = None) -> dict[str, object]:
    head = head_revision or _resolve_head_revision()
    meta = head_config(head)
    if not meta:
        raise RuntimeError(
            f"Alembic head {head} is not registered in postgres_migration_proof_registry.py — "
            "add tables_added/columns_added and a seed() before merging."
        )
    if not meta.get("seed"):
        raise RuntimeError(f"Alembic head {head} is registered without a seed() function")

    db = SessionLocal()
    try:
        result = meta["seed"](db)
        db.commit()
        return {"head": head, "seeded": True, **result}
    finally:
        db.close()


if __name__ == "__main__":
    try:
        out = run()
    except Exception as exc:
        print(f"Migration proof seed FAILED: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
    print("Seeded migration proof rows:", out)
