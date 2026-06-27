#!/usr/bin/env python3
"""One-off CSV: assigned therapists with missing session logs (2+ calendar days old).

Usage (from backend/):
  python scripts/session_log_compliance_audit.py
  python scripts/session_log_compliance_audit.py --output ../exports/session-log-audit.csv
  python scripts/session_log_compliance_audit.py --api-url https://case-manager-new-production.up.railway.app --email you@insighte.com
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.timezone import today_ist  # noqa: E402
from app.models.assignment import CaseAssignment, CaseAssignmentStatus  # noqa: E402
from app.models.case import Case  # noqa: E402
from app.models.daily_log import DailyLog  # noqa: E402
from app.models.session import Session as TherapySession  # noqa: E402
from app.models.session import SessionStatus  # noqa: E402
from app.models.user import User  # noqa: E402


def _aggregate_rows(
    therapist_cases: dict[int, list[str]],
    users_by_id: dict[int, dict],
    missing_by_therapist: dict[int, list[dict]],
) -> list[dict]:
    rows: list[dict] = []
    for therapist_id in sorted(therapist_cases.keys()):
        missing = missing_by_therapist.get(therapist_id, [])
        if not missing:
            continue
        user = users_by_id.get(therapist_id, {})
        dates = [m["scheduled_date"] for m in missing]
        rows.append(
            {
                "therapist_user_id": therapist_id,
                "full_name": user.get("full_name", "") or "",
                "email": user.get("email", "") or "",
                "staff_id": user.get("staff_id", "") or "",
                "active_case_count": len(therapist_cases[therapist_id]),
                "active_case_codes": "; ".join(therapist_cases[therapist_id]),
                "missing_logs_2plus_days": len(missing),
                "oldest_missing_session_date": min(dates).isoformat(),
                "newest_missing_session_date": max(dates).isoformat(),
                "missing_case_codes": "; ".join(
                    sorted({m["case_code"] for m in missing if m.get("case_code")})
                ),
            }
        )
    return rows


def run_audit_via_api(
    *,
    api_url: str,
    email: str,
    password: str,
    min_age_days: int,
) -> list[dict]:
    today = today_ist()
    cutoff = today - timedelta(days=min_age_days)

    with httpx.Client(base_url=api_url.rstrip("/"), timeout=120.0) as client:
        login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        therapist_rows = client.get("/api/v1/admin/hr-reports/therapist-status", headers=headers)
        therapist_rows.raise_for_status()
        assigned = [
            row
            for row in therapist_rows.json().get("rows", [])
            if int(row.get("activeAssignments") or 0) > 0
        ]
        therapist_cases: dict[int, list[str]] = {}
        users_by_id: dict[int, dict] = {}
        for row in assigned:
            tid = int(row["therapistUserId"])
            therapist_cases[tid] = []
            users_by_id[tid] = {
                "full_name": row.get("displayName") or "",
                "email": row.get("email") or "",
                "staff_id": "",
            }

        for tid in list(therapist_cases.keys()):
            cases = client.get(
                "/api/v1/cases",
                params={"assigned": "true", "therapist_user_id": tid, "page_size": 200},
                headers=headers,
            )
            if cases.status_code == 200:
                items = cases.json().get("items") or cases.json()
                if isinstance(items, dict):
                    items = items.get("items", [])
                therapist_cases[tid] = [
                    item.get("case_code") or str(item.get("id", ""))
                    for item in items
                    if item.get("case_code") or item.get("id")
                ]

        missing_by_therapist: dict[int, list[dict]] = defaultdict(list)
        page = 1
        while True:
            res = client.get(
                "/api/v1/admin/session-logs",
                params={
                    "status": "missing",
                    "to_date": cutoff.isoformat(),
                    "page": page,
                    "page_size": 200,
                },
                headers=headers,
            )
            res.raise_for_status()
            data = res.json()
            for item in data.get("items", []):
                tid = item.get("therapist_user_id")
                if tid is None or int(tid) not in therapist_cases:
                    continue
                scheduled = item.get("scheduled_date")
                if isinstance(scheduled, str):
                    scheduled = date.fromisoformat(scheduled[:10])
                missing_by_therapist[int(tid)].append(
                    {
                        "scheduled_date": scheduled,
                        "case_code": item.get("case_code") or "",
                    }
                )
            if page >= data.get("pages", 1):
                break
            page += 1

    return _aggregate_rows(therapist_cases, users_by_id, missing_by_therapist)


def run_audit(*, min_age_days: int = 2) -> list[dict]:
    today = today_ist()
    cutoff = today - timedelta(days=min_age_days)

    with SessionLocal() as db:
        assignments = db.execute(
            select(
                CaseAssignment.therapist_user_id,
                CaseAssignment.case_id,
                Case.case_code,
            )
            .join(Case, Case.id == CaseAssignment.case_id)
            .where(CaseAssignment.status == CaseAssignmentStatus.ACTIVE)
            .order_by(CaseAssignment.therapist_user_id, Case.case_code)
        ).all()

        therapist_cases: dict[int, list[str]] = defaultdict(list)
        for therapist_id, _case_id, case_code in assignments:
            therapist_cases[int(therapist_id)].append(case_code)

        if not therapist_cases:
            return []

        therapist_ids = list(therapist_cases.keys())
        users = {
            u.id: u
            for u in db.scalars(
                select(User).where(User.id.in_(therapist_ids))
            ).all()
        }

        missing_rows = db.execute(
            select(
                TherapySession.therapist_user_id,
                TherapySession.scheduled_date,
                TherapySession.id,
                Case.case_code,
            )
            .join(Case, Case.id == TherapySession.case_id)
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id.in_(therapist_ids),
                TherapySession.status == SessionStatus.COMPLETED,
                DailyLog.id.is_(None),
                TherapySession.scheduled_date <= cutoff,
            )
            .order_by(TherapySession.therapist_user_id, TherapySession.scheduled_date)
        ).all()

        by_therapist: dict[int, list] = defaultdict(list)
        for therapist_id, scheduled_date, session_id, case_code in missing_rows:
            by_therapist[int(therapist_id)].append(
                {
                    "session_id": session_id,
                    "scheduled_date": scheduled_date,
                    "case_code": case_code,
                }
            )

        users_by_id = {
            tid: {
                "full_name": (users[tid].full_name if users.get(tid) else "") or "",
                "email": (users[tid].email if users.get(tid) else "") or "",
                "staff_id": (users[tid].external_employee_id if users.get(tid) else "") or "",
            }
            for tid in therapist_cases
        }
        missing_by_therapist = {
            tid: [
                {"scheduled_date": m["scheduled_date"], "case_code": m["case_code"]}
                for m in items
            ]
            for tid, items in by_therapist.items()
        }
        return _aggregate_rows(therapist_cases, users_by_id, missing_by_therapist)

    return []


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "therapist_user_id",
        "full_name",
        "email",
        "staff_id",
        "active_case_count",
        "active_case_codes",
        "missing_logs_2plus_days",
        "oldest_missing_session_date",
        "newest_missing_session_date",
        "missing_case_codes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export missing session log compliance CSV for HR.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: ../exports/session-log-compliance-audit-YYYY-MM-DD.csv)",
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=2,
        help="Minimum calendar days since session date (default: 2)",
    )
    parser.add_argument("--api-url", default=None, help="Use live API instead of local DATABASE_URL")
    parser.add_argument("--email", default="hr@demo.com", help="Login email when using --api-url")
    parser.add_argument("--password", default="demo123", help="Login password when using --api-url")
    args = parser.parse_args()

    today = today_ist()
    cutoff = today - timedelta(days=args.min_age_days)
    default_name = f"session-log-compliance-audit-{today.isoformat()}.csv"
    output = Path(args.output) if args.output else Path(__file__).resolve().parents[2] / "exports" / default_name

    if args.api_url:
        rows = run_audit_via_api(
            api_url=args.api_url,
            email=args.email,
            password=args.password,
            min_age_days=args.min_age_days,
        )
        source = f"API {args.api_url}"
    else:
        rows = run_audit(min_age_days=args.min_age_days)
        source = "local DATABASE_URL"

    write_csv(output, rows)

    print(f"Source: {source}")
    print(f"Audit date (IST): {today.isoformat()}")
    print(f"Missing-log cutoff (session date on or before): {cutoff.isoformat()}")
    print(f"Therapists with active assignments and overdue missing logs: {len(rows)}")
    print(f"Wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
