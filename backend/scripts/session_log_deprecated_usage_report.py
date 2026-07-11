"""Count deprecated session-log route usage for deletion gates.

Usage (from backend/):
  python3 scripts/session_log_deprecated_usage_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Placeholder report — wire to audit_events or request logs in production.
# Phase 3: query audit_events for deprecated route actions.

REPORT = {
    "deprecated_routes": [
        {
            "route": "POST /api/v1/therapist/session-logs",
            "gate": "G2_zero_route_traffic_30d",
            "note": "Check insightcase.deprecated logger or audit_events entity_type=daily_log via portal",
        },
        {
            "route": "PUT /api/v1/daily-logs/{id}/session-evidence",
            "gate": "G2_zero_route_traffic_30d",
            "note": "Check insightcase.deprecated logger",
        },
    ],
    "frontend_dead_modules": [
        "SubmitSessionLogForm.jsx",
        "clinical/session-log/*",
    ],
    "deletion_gates_doc": "docs/product/canonical-manifest.yml",
}


def main() -> int:
    print(json.dumps(REPORT, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
