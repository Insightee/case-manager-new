#!/usr/bin/env python3
"""End-to-end API flow against production (Railway + seeded admin)."""
from __future__ import annotations

import json
import sys
import time
from datetime import date, time as dt_time

import httpx

API = "https://case-manager-new-production.up.railway.app"
ADMIN_EMAIL = "superadmin@demo.com"
ADMIN_PASSWORD = "demo123"
TS = int(time.time())


def login(email: str, password: str) -> dict:
    r = httpx.post(
        f"{API}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=60.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Login failed {email}: {r.status_code} {r.text[:300]}")
    return r.json()


def client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )


def step(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    therapist_email = f"e2e.therapist.{TS}@insighte.com"
    parent_email = f"e2e.parent.{TS}@insighte.com"
    therapist_password = "E2eTherapist1!"
    parent_password = "E2eParent1!"

    print(f"API: {API}\n")

    # --- Admin ---
    admin = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_tok = admin["access_token"]
    ac = client(admin_tok)

    me = ac.get("/api/v1/auth/me")
    step("Admin /auth/me", me.status_code == 200, me.json().get("email", ""))

    dash = ac.get("/api/v1/admin/workbench/summary")
    step("Admin workbench summary", dash.status_code == 200)

    th = ac.post(
        "/api/v1/admin/therapists/onboard",
        json={
            "email": therapist_email,
            "full_name": f"E2E Therapist {TS}",
            "phone": "+919999990001",
            "mode": "direct",
            "password": therapist_password,
            "send_email": False,
            "module_assignments": ["homecare", "shadow_support"],
            "services_offered": ["homecare"],
            "short_bio": "E2E test therapist",
        },
    )
    step("Admin onboard therapist", th.status_code in (200, 201), th.text[:200] if th.status_code >= 400 else "")
    therapist_user_id = th.json().get("user_id")

    fam = ac.post(
        "/api/v1/admin/families",
        json={
            "parent_email": parent_email,
            "parent_full_name": f"E2E Parent {TS}",
            "parent_phone": "+919999990002",
            "child": {"first_name": "E2E", "last_name": f"Child{TS}"},
            "send_invite": False,
            "password": parent_password,
        },
    )
    step("Admin create family", fam.status_code in (200, 201), fam.text[:200] if fam.status_code >= 400 else "")
    child_id = fam.json()["childId"]
    parent_user_id = fam.json().get("parentUserId")

    allot = ac.post(
        "/api/v1/admin/cases/allot",
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1500,
            "compensation_mode": "PERCENTAGE",
            "pay_share_pct": 60,
            "therapist_user_id": therapist_user_id,
            "service_address_line1": "12 Test Lane",
            "service_city": "Bangalore",
            "service_state": "KA",
            "service_pincode": "560001",
        },
    )
    step("Admin allot case", allot.status_code in (200, 201), allot.text[:300] if allot.status_code >= 400 else "")
    case = allot.json().get("case") or allot.json()
    case_id = case["id"]
    case_code = case.get("case_code", "")
    step("Case has code", bool(case_code), case_code)

    cases_list = ac.get("/api/v1/cases", params={"page_size": 100})
    step("Admin list cases", cases_list.status_code == 200)
    found = any(c.get("id") == case_id for c in (cases_list.json().get("items") or cases_list.json()))
    step("New case in admin list", found)

    pipeline = ac.get("/api/v1/admin/cases/pipeline")
    step("Admin case pipeline", pipeline.status_code == 200)

    ac.close()

    # --- Therapist ---
    th_login = login(therapist_email, therapist_password)
    th_tok = th_login["access_token"]
    tc = client(th_tok)

    th_me = tc.get("/api/v1/auth/me")
    step("Therapist /auth/me", th_me.status_code == 200, th_me.json().get("full_name", ""))

    tp = tc.get("/api/v1/therapist/profile")
    step("Therapist profile", tp.status_code == 200, tp.json().get("display_name", ""))

    my_cases = tc.get("/api/v1/cases", params={"page_size": 50})
    step("Therapist list cases", my_cases.status_code == 200)
    items = my_cases.json().get("items") or my_cases.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    th_case = next((c for c in items if c.get("id") == case_id), None)
    step("Therapist sees assigned case", th_case is not None, case_code)

    today = date.today().isoformat()
    sess = tc.post(
        "/api/v1/sessions",
        json={
            "case_id": case_id,
            "scheduled_date": today,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "mode": "HOME",
        },
    )
    step("Therapist create session", sess.status_code in (200, 201), sess.text[:200] if sess.status_code >= 400 else "")
    session_id = sess.json()["id"]

    start = tc.post(f"/api/v1/sessions/{session_id}/start", json={})
    step("Therapist start session", start.status_code == 200, start.json().get("status", ""))

    end = tc.post(f"/api/v1/sessions/{session_id}/end", json={})
    step("Therapist end session", end.status_code == 200, end.json().get("status", ""))

    log = tc.post(
        "/api/v1/daily-logs",
        json={
            "session_id": session_id,
            "attendance_status": "PRESENT",
            "session_notes": f"E2E session notes {TS}",
            "activities_done": "Fine motor, communication games",
            "observations": "Engaged well throughout",
            "follow_ups": "Continue home practice",
        },
    )
    step("Therapist submit daily log", log.status_code in (200, 201), log.text[:200] if log.status_code >= 400 else "")
    log_id = log.json()["id"]

    tc.close()

    # --- Admin approve log for parent visibility ---
    ac2 = client(admin_tok)
    approve = ac2.post(f"/api/v1/daily-logs/{log_id}/approve")
    step("Admin approve session log", approve.status_code == 200)
    ac2.close()

    # --- Parent ---
    pr_login = login(parent_email, parent_password)
    pr_tok = pr_login["access_token"]
    pc = client(pr_tok)

    pr_me = pc.get("/api/v1/auth/me")
    step("Parent /auth/me", pr_me.status_code == 200)

    pr_cases = pc.get("/api/v1/parent/cases")
    step("Parent list cases", pr_cases.status_code == 200)
    pr_items = pr_cases.json() if isinstance(pr_cases.json(), list) else pr_cases.json().get("items", [])
    step("Parent sees case", any(c.get("id") == case_id for c in pr_items), str(len(pr_items)))

    appts = pc.get("/api/v1/parent/appointments")
    step("Parent appointments", appts.status_code == 200, f"{len(appts.json())} upcoming")

    logs = pc.get("/api/v1/parent/session-logs", params={"case_id": case_id})
    step("Parent session logs", logs.status_code == 200)
    log_items = logs.json()
    step(
        "Parent sees approved session log",
        any(l.get("id") == log_id or "E2E session notes" in (l.get("activities_done") or "") for l in log_items),
        f"count={len(log_items)} log_id={log_id}",
    )

    case_detail = pc.get(f"/api/v1/parent/cases/{case_id}")
    step("Parent case detail", case_detail.status_code == 200)

    pc.close()

    print("\nAll E2E API steps passed.")
    print(f"Therapist login: {therapist_email} / {therapist_password}")
    print(f"Parent login: {parent_email} / {parent_password}")
    print(f"Case: {case_code} (id={case_id})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[E2E ERROR] {e}", file=sys.stderr)
        raise
