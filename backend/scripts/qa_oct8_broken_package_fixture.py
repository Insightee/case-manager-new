#!/usr/bin/env python3
"""E2E-only: create PACKAGE case missing package_session_count for invoice 422 QA."""
from __future__ import annotations

import sys

from app.tests.test_missing_package_count_invoice_routes import (
    _broken_package_fixture,
    _cleanup_case,
)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        _cleanup_case(int(sys.argv[2]))
        return
    therapist_id, case_code, case_id = _broken_package_fixture()
    print(f"{case_id}|{case_code}|{therapist_id}", flush=True)


if __name__ == "__main__":
    main()
