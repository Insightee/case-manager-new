#!/usr/bin/env python3
"""Throwaway walkthrough seed — delegates to reusable fixture module."""
from __future__ import annotations

from app.core.database import ensure_sqlite_schema_patches
from app.seed.finance_walkthrough_fixture import run


if __name__ == "__main__":
    ensure_sqlite_schema_patches()
    import json

    print(json.dumps(run(), indent=2))
