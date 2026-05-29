#!/usr/bin/env python3
"""Production API flow smoke (Railway). Creates a throwaway family/case and verifies core APIs.

Usage:
  API_BASE_URL=https://case-manager-new-production.up.railway.app python3 scripts/production_api_flow_smoke.py
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta

import httpx

API = os.environ.get("API_BASE_URL", "https://case-manager-new-production.up.railway.app").rstrip("/")
PASSWORD = os.environ.get("SMOKE_TEST_PASSWORD", "demo123")
ADMIN_EMAIL = os.environ.get("SMOKE_ADMIN_EMAIL", "superadmin@demo.com")
CM_EMAIL = os.environ.get("SMOKE_CM_EMAIL", "casemanager@demo.com")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def _login(client: httpx.Client, email: str) -> str:
    r = client.post(f"{API}/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        _fail(f"login {email}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{API}/health")
        if health.status_code != 200:
            _fail(f"health {health.status_code}")
        h = health.json()
        _ok(f"health db_migration={h.get('db_migration')} redis={h.get('redis')}")

        admin_token = _login(client, ADMIN_EMAIL)
        ah = {"Authorization": f"Bearer {admin_token}"}

        th_token = _login(client, "therapist@demo.com")
        th_me = client.get(f"{API}/api/v1/auth/me", headers={"Authorization": f"Bearer {th_token}"})
        if th_me.status_code != 200:
            _fail(f"therapist me: {th_me.status_code}")
        therapist_id = th_me.json()["id"]
        therapist_email = "therapist@demo.com"
        _ok(f"therapist {therapist_email} id={therapist_id}")

        fam = client.post(
            f"{API}/api/v1/admin/families",
            headers=ah,
            json={
                "parent_email": f"smoke-parent-{suffix}@demo.com",
                "parent_full_name": "Smoke Parent",
                "child": {"first_name": "Smoke", "last_name": suffix},
                "send_invite": False,
            },
        )
        if fam.status_code != 201:
            _fail(f"create family: {fam.text[:300]}")
        child_id = fam.json()["childId"]
        _ok(f"family child_id={child_id}")

        cm_token = _login(client, CM_EMAIL)
        ch = {"Authorization": f"Bearer {cm_token}"}
        allot = client.post(
            f"{API}/api/v1/admin/cases/allot",
            headers=ch,
            json={
                "child_id": child_id,
                "service_type": "Homecare",
                "product_module": "homecare",
                "billing_type": "PER_SESSION",
                "compensation_mode": "PERCENTAGE",
                "client_billing_mode": "POSTPAID",
                "client_rate_per_session_inr": 1200,
                "pay_share_pct": 60,
                "therapist_user_id": therapist_id,
            },
        )
        if allot.status_code != 201:
            _fail(f"allot: {allot.text[:300]}")
        case_id = allot.json()["case"]["id"]
        assert allot.json()["case"]["status"] == "PENDING_ALLOTMENT"
        _ok(f"allot case_id={case_id} PENDING_ALLOTMENT")

        activate = client.post(
            f"{API}/api/v1/admin/cases/{case_id}/activate-allotment",
            headers=ah,
            timeout=120.0,
        )
        if activate.status_code != 200:
            _fail(f"activate: {activate.text[:300]}")
        assert activate.json()["case"]["status"] == "ACTIVE"
        _ok("activate-allotment → ACTIVE")

        preview = client.get(f"{API}/api/v1/admin/cases/{case_id}/allotment-preview", headers=ah)
        if preview.status_code != 200:
            _fail(f"allotment-preview: {preview.text[:200]}")
        _ok(f"allotment-preview sessions={len(preview.json().get('upcoming_sessions') or [])}")

        th = {"Authorization": f"Bearer {th_token}"}
        start = date.today() + timedelta(days=14)
        while start.weekday() != 0:
            start += timedelta(days=1)
        end = start + timedelta(days=13)
        client.post(
            f"{API}/api/v1/slots/materialize",
            headers=th,
            json={"from_date": start.isoformat(), "to_date": end.isoformat()},
        )
        recur = client.post(
            f"{API}/api/v1/scheduling/assign-recurring",
            headers=th,
            json={
                "case_id": case_id,
                "therapist_user_id": therapist_id,
                "weekdays": ["mon"],
                "start_time": "10:00:00",
                "end_time": "11:00:00",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )
        if recur.status_code not in (200, 201):
            _fail(f"assign-recurring: {recur.text[:300]}")
        _ok(f"recurring booked count={recur.json().get('booked_slot_count', 0)}")

        sessions = client.get(f"{API}/api/v1/sessions", params={"case_id": case_id, "page_size": 20}, headers=ah)
        if sessions.status_code != 200:
            _fail(f"sessions list: {sessions.text[:200]}")
        items = sessions.json().get("items", sessions.json())
        dated = [s for s in items if s.get("scheduled_date")]
        _ok(f"sessions with scheduled_date: {len(dated)}")

        incidents = client.get(f"{API}/api/v1/incidents", headers=ah)
        if incidents.status_code != 200:
            _fail(f"incidents list: {incidents.status_code}")
        _ok("incidents API reachable")

        invoices = client.get(f"{API}/api/v1/invoices", headers=ah)
        if invoices.status_code != 200:
            _fail(f"invoices list: {invoices.status_code}")
        _ok("invoices API reachable")

    print("\nAll production API flow checks passed.")


if __name__ == "__main__":
    main()
