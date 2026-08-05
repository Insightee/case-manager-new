"""Finance KPI consistency — overview, summary, and receivables must agree on the same scope."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sum_balance(rows: list[dict]) -> float:
    return round(sum(float(r.get("balanceInr") or 0) for r in rows), 2)


def test_summary_matches_receivables_global_scope():
    seed_run()
    headers = _login("finance@demo.com")

    rec = client.get("/api/v1/admin/client-billing/receivables", headers=headers)
    assert rec.status_code == 200, rec.text
    rec_body = rec.json()
    totals = rec_body["totals"]

    summary = client.get("/api/v1/admin/client-billing/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    s_body = summary.json()

    assert s_body["source"] == "admin_receivables_summary"
    assert s_body["totalOutstandingInr"] == totals["outstandingInr"]
    assert s_body["overdueCount"] == totals["overdueCount"]
    assert s_body["overdueInr"] == totals["overdueInr"]
    assert s_body["totalOutstandingInr"] == _sum_balance(rec_body["invoices"])

    brief = client.get("/api/v1/admin/finance-overview/monday-brief", headers=headers)
    assert brief.status_code == 200, brief.text
    money_in = brief.json()["moneyIn"]
    assert money_in["collectibleOutstandingInr"] == totals["outstandingInr"]
    assert money_in["overdueCount"] == totals["overdueCount"]


def test_summary_matches_receivables_month_scope():
    seed_run()
    headers = _login("finance@demo.com")
    month = "2026-05"

    rec = client.get(f"/api/v1/admin/client-billing/receivables?month={month}", headers=headers)
    assert rec.status_code == 200, rec.text
    rec_body = rec.json()

    summary = client.get(f"/api/v1/admin/client-billing/summary?month={month}", headers=headers)
    assert summary.status_code == 200, summary.text
    s_body = summary.json()

    assert s_body["totalOutstandingInr"] == rec_body["totals"]["outstandingInr"]
    assert s_body["totalOutstandingInr"] == _sum_balance(rec_body["invoices"])

    empty_month = client.get("/api/v1/admin/client-billing/receivables?month=2026-08", headers=headers)
    assert empty_month.status_code == 200
    empty_body = empty_month.json()
    empty_summary = client.get("/api/v1/admin/client-billing/summary?month=2026-08", headers=headers).json()
    assert empty_summary["totalOutstandingInr"] == empty_body["totals"]["outstandingInr"]
    assert empty_summary["totalOutstandingInr"] == _sum_balance(empty_body["invoices"])
