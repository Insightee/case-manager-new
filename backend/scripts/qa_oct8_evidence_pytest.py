#!/usr/bin/env python3
"""Run evidence-summary contract tests (staff 200 / parent 403) for Playwright QA."""
from __future__ import annotations

import subprocess
import sys


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "app/tests/test_report_evidence_summary.py::test_evidence_summary_therapist_admin_portals_share_endpoint_parent_blocked",
            "-q",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
