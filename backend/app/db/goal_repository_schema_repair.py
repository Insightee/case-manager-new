"""Idempotent Postgres repairs for partial clinical-report schema rollouts."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine

_GOAL_REPO_REPAIR_DDL: tuple[tuple[str, str], ...] = (
    ("source_daily_log_id", "INTEGER"),
    ("source_session_id", "INTEGER"),
    ("review_note", "TEXT"),
    ("core_domains_json", "TEXT"),
    ("core_environments_json", "TEXT"),
    ("baseline_state", "TEXT"),
    ("desired_state", "TEXT"),
    ("goal_statement", "TEXT"),
    ("lifecycle_status", "VARCHAR(32)"),
    ("source", "VARCHAR(32)"),
    ("scope", "VARCHAR(32)"),
    ("source_clinical_report_id", "INTEGER"),
)

_STRATEGY_REPO_REPAIR_DDL: tuple[tuple[str, str], ...] = (
    ("domain_key", "VARCHAR(64)"),
    ("environment_context", "VARCHAR(32)"),
    ("linked_goal_card_id", "INTEGER"),
    ("source_daily_log_id", "INTEGER"),
    ("review_note", "TEXT"),
    ("core_domains_json", "TEXT"),
    ("core_environments_json", "TEXT"),
    ("strategy_steps_json", "TEXT"),
    ("expected_outcome", "TEXT"),
    ("source", "VARCHAR(32)"),
    ("scope", "VARCHAR(32)"),
    ("source_clinical_report_id", "INTEGER"),
)


def _repair_table_columns(table: str, ddl_spec: tuple[tuple[str, str], ...]) -> list[str]:
    if settings.is_sqlite:
        return []
    insp = inspect(engine)
    if not insp.has_table(table):
        return []
    existing = {c["name"] for c in insp.get_columns(table)}
    added: list[str] = []
    with engine.begin() as conn:
        for col, ddl in ddl_spec:
            if col in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"))
            added.append(col)
    return added


def repair_goal_repository_columns() -> list[str]:
    """Ensure goal/strategy repository tables match ORM models."""
    goal_added = _repair_table_columns("goal_repository_items", _GOAL_REPO_REPAIR_DDL)
    strategy_added = _repair_table_columns("strategy_repository_items", _STRATEGY_REPO_REPAIR_DDL)
    return goal_added + strategy_added
