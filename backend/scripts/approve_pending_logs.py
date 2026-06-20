#!/usr/bin/env python3
"""Approve all pending session logs up to a given date (default: today IST).

Usage (from backend/):
  python scripts/approve_pending_logs.py
  python scripts/approve_pending_logs.py --api-url https://case-manager-new-production.up.railway.app
  python scripts/approve_pending_logs.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.timezone import today_ist  # noqa: E402


def login(client: httpx.Client, email: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    res.raise_for_status()
    return res.json()["access_token"]


def fetch_pending(client: httpx.Client, headers: dict, to_date: str) -> list[dict]:
    pending: list[dict] = []
    page = 1
    while True:
        res = client.get(
            "/api/v1/admin/session-logs",
            params={"status": "pending", "to_date": to_date, "page": page, "page_size": 200},
            headers=headers,
        )
        res.raise_for_status()
        data = res.json()
        pending.extend(data["items"])
        if page >= data["pages"]:
            break
        page += 1
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-approve pending session logs through a date.")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--email", default="casemanager@demo.com", help="Admin account email")
    parser.add_argument("--password", default="demo123", help="Admin account password")
    parser.add_argument("--to-date", default=today_ist().isoformat(), help="Approve logs with session date on/before this (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="List pending logs without approving")
    args = parser.parse_args()

    print(f"API: {args.api_url}")
    print(f"Cutoff date: {args.to_date}")

    with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=120.0) as client:
        token = login(client, args.email, args.password)
        headers = {"Authorization": f"Bearer {token}"}
        pending = fetch_pending(client, headers, args.to_date)

    print(f"Found {len(pending)} pending log(s)")
    if not pending:
        return 0

    if args.dry_run:
        for log in pending[:20]:
            print(f"  would approve log {log['id']} ({log.get('case_code')} / {log.get('scheduled_date')})")
        if len(pending) > 20:
            print(f"  ... and {len(pending) - 20} more")
        return 0

    ok = fail = 0
    with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=120.0) as client:
        token = login(client, args.email, args.password)
        headers = {"Authorization": f"Bearer {token}"}
        for log in pending:
            res = client.post(f"/api/v1/daily-logs/{log['id']}/approve", headers=headers)
            if res.status_code == 200:
                ok += 1
                if ok <= 10 or ok % 25 == 0 or ok == len(pending):
                    print(f"  approved log {log['id']} ({log.get('case_code')} / {log.get('scheduled_date')}) [{ok}/{len(pending)}]")
            else:
                fail += 1
                print(f"  FAILED log {log['id']}: {res.status_code} {res.text[:200]}")

    print(f"Done: {ok} approved, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
