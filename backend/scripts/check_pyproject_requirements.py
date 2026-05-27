#!/usr/bin/env python3
"""Fail if production packages in requirements.txt are missing from pyproject.toml."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "requirements.txt"
PYPROJECT = ROOT / "pyproject.toml"

SKIP = frozenset({"pytest", "httpx"})  # dev-only in requirements.txt


def parse_requirements(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def parse_pyproject(path: Path) -> set[str]:
    text = path.read_text()
    block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    names: set[str] = set()
    for line in block.splitlines():
        line = line.strip().strip(",").strip('"')
        if not line or line.startswith("#"):
            continue
        # "package>=1.0" or "package[extra]>=1.0"
        name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def main() -> int:
    req = parse_requirements(REQ) - SKIP
    proj = parse_pyproject(PYPROJECT)
    missing = sorted(req - proj)
    if missing:
        print("Missing from pyproject.toml dependencies:", ", ".join(missing), file=sys.stderr)
        return 1
    print("requirements.txt production deps ⊆ pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
