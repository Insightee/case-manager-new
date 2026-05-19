#!/usr/bin/env python3
"""Smoke-test therapist → admin flows against a running API (localhost:8000)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def req(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail}") from e


def login(email: str, password: str) -> str:
    _, data = req("POST", "/auth/login", body={"email": email, "password": password})
    return data["access_token"]


def main() -> int:
    print("=== InsightCase therapist flow smoke test ===\n")
    th = login("therapist@demo.com", "demo123")
    admin = login("superadmin@demo.com", "demo123")
    print("✓ Login (therapist + admin)")

    _, cases = req("GET", "/cases?assigned=true", th)
    assert cases, "No assigned cases for therapist"
    case = cases[0]
    case_id = case["id"]
    print(f"✓ Assigned cases ({len(cases)}), using {case['case_code']}")

    _, upcoming = req("GET", "/sessions/upcoming?days=14", th)
    session_id = None
    if upcoming:
        session_id = upcoming[0]["id"]
        req("POST", f"/sessions/{session_id}/start", th)
        req("POST", f"/sessions/{session_id}/end", th)
        print(f"✓ Start/end session {session_id}")
    else:
        _, manual = req(
            "POST",
            "/sessions/manual",
            th,
            {
                "case_id": case_id,
                "scheduled_date": "2026-05-19",
                "actual_start_at": "2026-05-19T10:00:00+00:00",
                "actual_end_at": "2026-05-19T11:00:00+00:00",
                "mode": "IN_PERSON",
            },
        )
        session_id = manual["id"]
        print(f"✓ Manual session {session_id}")

    _, log = req(
        "POST",
        "/daily-logs",
        th,
        {
            "session_id": session_id,
            "attendance_status": "PRESENT",
            "session_notes": "Smoke test session notes",
            "activities_done": "Structured play",
            "goals_addressed": "Communication",
            "observations": "Engaged well",
            "follow_ups": "Continue weekly",
            "parent_notes": "Good progress at home",
        },
    )
    log_id = log["id"]
    print(f"✓ Daily log created {log_id}")

    _, approved_log = req("POST", f"/daily-logs/{log_id}/approve", admin)
    assert approved_log["status"] == "approved"
    print("✓ Admin approved daily log")

    month_label = "May 2026"
    _, report = req(
        "POST",
        "/reports/monthly",
        th,
        {"case_id": case_id, "month": month_label, "summary": "Smoke test monthly summary for May."},
    )
    report_id = report["id"]
    print(f"✓ Monthly report draft {report_id}")

    _, submitted = req("POST", f"/reports/monthly/{report_id}/submit", th)
    assert submitted["status"] == "under_review"
    print("✓ Report submitted for review")

    _, approved_report = req(
        "POST",
        f"/reports/monthly/{report_id}/approve",
        admin,
        {"comment": "Approved in smoke test", "visibility_status": "APPROVED_FOR_PARENT"},
    )
    assert approved_report["status"] == "approved"
    print("✓ Admin approved monthly report")

    _, preview = req("GET", "/invoices/preview?month=2026-05", th)
    print(f"✓ Invoice preview (sessions={preview.get('sessions_count', '?')})")

    _, invoices = req("GET", "/invoices", th)
    print(f"✓ List invoices ({len(invoices)} rows)")

    print("\n=== All smoke checks passed ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n✗ FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
