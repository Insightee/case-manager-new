"""Idempotent migration helpers."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return index_name in {idx["name"] for idx in insp.get_indexes(table)}


def create_index_if_missing(index_name: str, table: str, columns: list[str], **kwargs) -> None:
    if not has_index(table, index_name):
        op.create_index(index_name, table, columns, **kwargs)
