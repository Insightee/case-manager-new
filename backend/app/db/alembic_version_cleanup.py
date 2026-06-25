"""Helpers to reconcile alembic_version when parallel heads were stamped then reparented."""
from __future__ import annotations

from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text


def revision_ancestors(script: ScriptDirectory, revision_id: str) -> set[str]:
    """All direct and indirect parent revisions for ``revision_id``."""
    rev = script.get_revision(revision_id)
    if rev is None:
        return set()
    down = rev.down_revision
    if down is None:
        return set()
    parents = down if isinstance(down, (tuple, list)) else (down,)
    result = set(parents)
    for parent in parents:
        result |= revision_ancestors(script, parent)
    return result


def stale_version_rows(script: ScriptDirectory, versions: list[str]) -> set[str]:
    """Version rows superseded by another stored row in the same database."""
    if len(versions) <= 1:
        return set()
    stale: set[str] = set()
    for version in versions:
        for other in versions:
            if version == other:
                continue
            if version in revision_ancestors(script, other):
                stale.add(version)
    return stale


def effective_stored_revision(script: ScriptDirectory, versions: list[str]) -> str | None:
    """Best current revision among one or more alembic_version rows."""
    if not versions:
        return None
    if len(versions) == 1:
        return versions[0]
    tips = [
        version
        for version in versions
        if not any(
            version in revision_ancestors(script, other)
            for other in versions
            if other != version
        )
    ]
    if len(tips) == 1:
        return tips[0]
    return versions[0]


def all_stored_revisions(engine: Engine) -> list[str]:
    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        return []
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    return [row[0] for row in rows]


def compact_stale_version_rows(engine: Engine, script: ScriptDirectory) -> list[str]:
    """Drop ancestor rows when a descendant revision is also recorded as current."""
    versions = all_stored_revisions(engine)
    if len(versions) <= 1:
        return versions

    stale = stale_version_rows(script, versions)
    if not stale:
        return versions

    kept = [version for version in versions if version not in stale]
    with engine.begin() as conn:
        for version in stale:
            conn.execute(
                text("DELETE FROM alembic_version WHERE version_num = :version"),
                {"version": version},
            )
    print(
        "Compacted stale alembic_version rows: "
        f"removed {sorted(stale)}, kept {kept}"
    )
    return kept


def current_revision(engine: Engine, script: ScriptDirectory | None = None) -> str | None:
    versions = all_stored_revisions(engine)
    if not versions:
        return None
    if script is None:
        return versions[0] if len(versions) == 1 else versions[-1]
    return effective_stored_revision(script, versions)
