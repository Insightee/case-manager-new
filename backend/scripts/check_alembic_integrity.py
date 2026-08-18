#!/usr/bin/env python3
"""Fail if Alembic revision IDs collide or multiple heads exist."""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"

REVISION_RE = re.compile(
    r'revision(?:\s*:\s*str\s*=\s*|\s*=\s*)["\']([^"\']+)["\']',
)


def _revision_ids() -> list[str]:
    ids: list[str] = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        match = REVISION_RE.search(text)
        if match:
            ids.append(match.group(1))
    return ids


def check_duplicate_revision_ids() -> None:
    ids = _revision_ids()
    duplicates = [rev for rev, count in Counter(ids).items() if count > 1]
    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise SystemExit(f"Alembic integrity failed: duplicate revision id(s): {joined}")


def check_single_head() -> None:
    env = {**dict(**__import__("os").environ), "PYTHONPATH": ".:alembic"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        raise SystemExit(proc.returncode)
    head_lines = [line for line in proc.stdout.splitlines() if "(head)" in line]
    if len(head_lines) != 1:
        sys.stderr.write(proc.stdout)
        raise SystemExit(
            f"Alembic integrity failed: expected exactly one head, found {len(head_lines)}"
        )


def main() -> None:
    check_duplicate_revision_ids()
    check_single_head()
    print("Alembic integrity OK: unique revision ids and single head")


if __name__ == "__main__":
    main()
