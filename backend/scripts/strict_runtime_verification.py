#!/usr/bin/env python3
"""Strict runtime verification for key operational flows.

Checks:
- Open Slots
- Book Recurring
- Session Logs
- Reports
- signed-upload finalize (skipped for local storage provider)
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path
import sys

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import settings

BASE = "http://127.0.0.1:8000/api/v1"


def req(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, dict | list]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as resp:
        raw = resp.read().decode()
        return resp.status, json.loads(raw) if raw else {}


def login(email: str, password: str) -> str:
    _, payload = req("POST", "/auth/login", body={"email": email, "password": password})
    return payload["access_token"]


def unwrap_items(payload: dict | list) -> list[dict]:
    if isinstance(payload, dict):
        return payload.get("items", []) or []
    return payload if isinstance(payload, list) else []


def main() -> int:
    therapist = login("therapist@demo.com", "demo123")
    admin = login("superadmin@demo.com", "demo123")

    _, me = req("GET", "/auth/me", therapist)
    therapist_id = me["id"]

    _, therapist_cases = req("GET", "/cases?assigned=true", therapist)
    case_id = unwrap_items(therapist_cases)[0]["id"]

    failures: list[str] = []

    # Open Slots
    try:
        slot_day = (date.today() + timedelta(days=2)).isoformat()
        _, created = req(
            "POST",
            "/scheduling/slots",
            therapist,
            {"slot_date": slot_day, "start_time": "16:00:00", "end_time": "17:00:00", "notes": "strict-open-slot"},
        )
        slot_id = created["id"]
        req("GET", f"/scheduling/calendar?from_date={slot_day}&to_date={slot_day}", therapist)
        req("DELETE", f"/scheduling/slots/{slot_id}", therapist)
        print(f"[PASS] Open Slots: slot_id={slot_id}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Open Slots: {exc}")
        print(f"[FAIL] Open Slots: {exc}")

    # Book Recurring
    try:
        start = date.today() + timedelta(days=1)
        payload = {
            "case_id": case_id,
            "therapist_user_id": therapist_id,
            "weekdays": [start.strftime("%a").upper()[:3]],
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=7)).isoformat(),
        }
        req("POST", "/scheduling/assign-recurring/preview", therapist, payload)
        _, assigned = req("POST", "/scheduling/assign-recurring", therapist, payload)
        print(f"[PASS] Book Recurring: booked={assigned.get('booked_slot_count', 0)}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Book Recurring: {exc}")
        print(f"[FAIL] Book Recurring: {exc}")

    # Session Logs
    try:
        today = date.today().isoformat()
        _, session = req(
            "POST",
            "/sessions/manual",
            therapist,
            {
                "case_id": case_id,
                "scheduled_date": today,
                "actual_start_at": f"{today}T09:00:00+00:00",
                "actual_end_at": f"{today}T10:00:00+00:00",
                "mode": "HOME",
            },
        )
        _, log = req(
            "POST",
            "/daily-logs",
            therapist,
            {
                "session_id": session["id"],
                "attendance_status": "PRESENT",
                "session_notes": "strict runtime log",
                "activities_done": "A",
                "goals_addressed": "G",
                "observations": "O",
                "follow_ups": "F",
                "parent_notes": "P",
            },
        )
        req("PATCH", f"/daily-logs/{log['id']}", therapist, {"session_notes": "strict runtime log edited"})
        req("POST", f"/daily-logs/{log['id']}/approve", admin)
        print(f"[PASS] Session Logs: log_id={log['id']}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Session Logs: {exc}")
        print(f"[FAIL] Session Logs: {exc}")

    # Reports
    try:
        month_label = date.today().strftime("%B %Y")
        _, report = req("POST", "/reports/monthly", therapist, {"case_id": case_id, "month": month_label, "summary": "strict runtime report"})
        report_id = report["id"]
        req("PATCH", f"/reports/monthly/{report_id}", therapist, {"summary": "strict runtime report edited"})
        req("POST", f"/reports/monthly/{report_id}/submit", therapist)
        req("GET", f"/admin/reports/monthly/{report_id}", admin)
        print(f"[PASS] Reports: report_id={report_id}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Reports: {exc}")
        print(f"[FAIL] Reports: {exc}")

    # signed-upload finalize
    provider = (settings.storage_provider or "local").strip().lower()
    if provider == "local":
        print("[SKIP] signed-upload finalize: provider=local")
    else:
        try:
            _, all_cases = req("GET", "/cases?limit=1", admin)
            any_case_id = unwrap_items(all_cases)[0]["id"]
            _, signed = req(
                "POST",
                "/attachments/signed-url",
                admin,
                {
                    "case_id": any_case_id,
                    "entity_type": "iep",
                    "file_name": "strict-signed-upload.txt",
                    "content_type": "text/plain",
                    "visibility_status": "INTERNAL_ONLY",
                },
            )
            put_request = urllib.request.Request(
                signed["upload_url"],
                data=b"strict-runtime-upload",
                method="PUT",
                headers={"Content-Type": "text/plain"},
            )
            with urllib.request.urlopen(put_request, timeout=30):
                pass
            _, finalized = req("POST", "/attachments/signed-url/finalize", admin, {"upload_token": signed["upload_token"]})
            print(f"[PASS] signed-upload finalize: attachment_id={finalized['id']}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"signed-upload finalize: {exc}")
            print(f"[FAIL] signed-upload finalize: {exc}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nAll strict runtime checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
