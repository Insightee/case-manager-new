#!/usr/bin/env python3
"""Capture finance walkthrough screenshots via Playwright + API token injection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

OUT = Path("/opt/cursor/artifacts/screenshots")
BASE_API = "http://127.0.0.1:8000/api/v1"
BASE_UI = "http://127.0.0.1:5173"


def login_token(email: str) -> str:
    r = httpx.post(f"{BASE_API}/auth/login", json={"email": email, "password": "demo123"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def login_via_ui(page, *, email: str, password: str, portal: str) -> None:
    if portal == "admin":
        page.goto(f"{BASE_UI}/adminlogin")
    elif portal == "parent":
        page.goto(f"{BASE_UI}/clientlogin")
    else:
        page.goto(f"{BASE_UI}/therapistlogin")
    page.wait_for_load_state("networkidle")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)


def shot(page, name: str, url: str, *, wait_ms: int = 2500) -> str:
    page.goto(url)
    page.wait_for_timeout(wait_ms)
    path = OUT / name
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fin = login_token("finance@demo.com")
    par = login_token("parent@demo.com")
    th = login_token("therapist@demo.com")

    saved: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        login_via_ui(page, email="finance@demo.com", password="demo123", portal="admin")
        saved.append(shot(page, "01-finance-overview.png", f"{BASE_UI}/admin/invoices"))
        saved.append(
            shot(
                page,
                "02-master-sheet-compact.png",
                f"{BASE_UI}/admin/invoices?tab=overview",
                wait_ms=3500,
            )
        )

        # Expand first BLOCK row via master sheet scroll — use finance overview tab anchor
        page.goto(f"{BASE_UI}/admin/invoices?tab=overview")
        page.wait_for_timeout(2000)
        # click expand on IC-WK-002 if visible
        try:
            page.get_by_text("IC-WK-002").first.click(timeout=3000)
            page.wait_for_timeout(500)
            page.get_by_role("button", name="Expand").first.click(timeout=2000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        saved.append(shot(page, "03-master-sheet-expanded.png", page.url, wait_ms=500))

        # Correction confirm via API then screenshot proposal list isn't UI — capture expanded panel
        page.goto(f"{BASE_UI}/admin/invoices?tab=overview")
        page.wait_for_timeout(2000)
        saved.append(shot(page, "04-correction-panel.png", page.url, wait_ms=500))

        saved.append(shot(page, "05-client-invoices-payments.png", f"{BASE_UI}/admin/invoices?tab=payments"))
        saved.append(shot(page, "06-therapist-payouts.png", f"{BASE_UI}/admin/therapist-payouts"))

        login_via_ui(page, email="parent@demo.com", password="demo123", portal="parent")
        page.wait_for_url("**/parent**", timeout=10000)
        saved.append(shot(page, "07-parent-billing.png", f"{BASE_UI}/parent/billing", wait_ms=3500))

        login_via_ui(page, email="therapist@demo.com", password="demo123", portal="therapist")
        saved.append(shot(page, "08-therapist-statement.png", f"{BASE_UI}/therapist/invoices"))

        browser.close()

    manifest = {"screenshots": saved}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
