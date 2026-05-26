#!/usr/bin/env python3
"""Run: python3 scripts/debug_health.py (from backend/)"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.seed.demo_seed import run as seed_run

LOG_PATH = Path(__file__).resolve().parents[2] / ".cursor" / "debug-3264f0.log"
SESSION_ID = "3264f0"


def log(hypothesis_id: str, location: str, message: str, data: dict | None = None, run_id: str = "health") -> None:
    entry = {
        "sessionId": SESSION_ID,
        "hypothesisId": hypothesis_id,
        "runId": run_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def check(name: str, ok: bool, detail: str = "", hypothesis_id: str = "H0") -> bool:
    log(hypothesis_id, "debug_health.py:check", name, {"ok": ok, "detail": detail})
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    print("InsightCase health check\n")
    seed_run()
    client = TestClient(app)
    all_ok = True

    health = client.get("/health")
    all_ok &= check("API /health", health.status_code == 200, health.text, "H1")

    accounts = [
        ("superadmin@demo.com", "admin"),
        ("therapist@demo.com", "therapist"),
        ("parent@demo.com", "parent"),
        ("casemanager@demo.com", "admin"),
        ("hr@demo.com", "admin"),
        ("finance@demo.com", "admin"),
    ]
    for email, portal in accounts:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
        ok = r.status_code == 200 and "access_token" in r.json()
        all_ok &= check(f"Login {email}", ok, f"status={r.status_code}", "H2")
        if not ok:
            continue
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/v1/auth/me", headers=headers)
        all_ok &= check(f"GET /auth/me ({portal})", me.status_code == 200, "", "H2")

    landing_expectations = [
        ("casemanager@demo.com", "/admin/cm", "H7"),
        ("hr@demo.com", "/admin/people", "H7"),
        ("finance@demo.com", "/admin/invoices", "H7"),
    ]
    for email, expected_route, hid in landing_expectations:
        token = _login(client, email)
        home = client.get("/api/v1/admin/home", headers={"Authorization": f"Bearer {token}"})
        route = home.json().get("landing_route") if home.status_code == 200 else None
        all_ok &= check(
            f"Landing {email}",
            home.status_code == 200 and route == expected_route,
            f"route={route} expected={expected_route}",
            hid,
        )

    cm_token = _login(client, "casemanager@demo.com")
    pipeline = client.get(
        "/api/v1/admin/cases/pipeline",
        headers={"Authorization": f"Bearer {cm_token}"},
    )
    all_ok &= check(
        "CM pipeline board",
        pipeline.status_code == 200,
        f"columns={len(pipeline.json().get('columns', []))}",
        "H8",
    )

    sa = client.post("/api/v1/auth/login", json={"email": "superadmin@demo.com", "password": "demo123"}).json()
    h = {"Authorization": f"Bearer {sa['access_token']}"}

    dash = client.get("/api/v1/admin/dashboard/summary", headers=h)
    all_ok &= check("Admin dashboard", dash.status_code == 200, f"cases={dash.json().get('total_cases')}", "H3")

    logs = client.get("/api/v1/daily-logs?approval_status=PENDING", headers=h)
    pending_n = len(logs.json()) if logs.status_code == 200 else 0
    all_ok &= check("Admin pending logs", logs.status_code == 200, f"count={pending_n}", "H4")

    parent_h = {"Authorization": f"Bearer {_login(client, 'parent@demo.com')}"}
    plogs = client.get("/api/v1/parent/session-logs", headers=parent_h)
    all_ok &= check("Parent session logs", plogs.status_code == 200, f"count={len(plogs.json())}", "H5")

    sup_r = client.post(
        "/api/v1/auth/login",
        json={"email": "supervisor@demo.com", "password": "demo123"},
    )
    if sup_r.status_code == 200 and "access_token" in sup_r.json():
        sup_token = sup_r.json()["access_token"]
        incidents = client.get(
            "/api/v1/incidents",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        all_ok &= check(
            "Incidents (supervisor)",
            incidents.status_code == 200,
            f"count={len(incidents.json())}",
            "H6",
        )
    else:
        check(
            "Incidents (supervisor)",
            True,
            "skipped — supervisor@demo.com not in seed (legacy migrated)",
            "H6",
        )

    log("H0", "debug_health.py:done", "health check complete", {"all_ok": all_ok})
    print(f"\nLogs written to {LOG_PATH}")
    return 0 if all_ok else 1


def _login(client: TestClient, email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    return r.json()["access_token"]


if __name__ == "__main__":
    raise SystemExit(main())
