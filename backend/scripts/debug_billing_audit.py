"""One-shot billing regression audit; appends NDJSON to session debug log."""
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

LOG_PATH = Path(__file__).resolve().parents[2] / ".cursor" / "debug-3264f0.log"
SESSION = "3264f0"


def log(hypothesis_id: str, location: str, message: str, data: dict, run_id: str = "api-audit"):
    entry = {
        "sessionId": SESSION,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def login(client: TestClient, email: str):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    if r.status_code != 200:
        log("E", "debug_billing_audit.login", "auth failed", {"email": email, "status": r.status_code})
        return None
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def probe(client: TestClient, hypothesis_id: str, portal: str, path: str, headers: dict):
    r = client.get(path, headers=headers)
    ok = r.status_code < 400
    log(
        hypothesis_id,
        f"debug_billing_audit.{portal}",
        "billing endpoint probe",
        {"path": path, "status": r.status_code, "ok": ok, "detail": (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)[:200] if not ok else None},
    )
    return ok


def main():
    client = TestClient(app)
    checks = []

    parent_h = login(client, "parent@demo.com")
    if parent_h:
        checks.append(probe(client, "C", "parent", "/api/v1/parent/billing/dashboard", parent_h))
        checks.append(probe(client, "C", "parent", "/api/v1/parent/billing/invoices?payment_bucket=needs_payment", parent_h))

    therapist_h = login(client, "therapist@demo.com")
    if therapist_h:
        checks.append(probe(client, "D", "therapist", "/api/v1/invoices", therapist_h))
        checks.append(probe(client, "D", "therapist", "/api/v1/invoices/preview?month=2026-05", therapist_h))

    finance_h = login(client, "finance@demo.com")
    if finance_h:
        checks.append(probe(client, "B", "admin", "/api/v1/admin/finance-overview/summary", finance_h))
        checks.append(probe(client, "B", "admin", "/api/v1/invoices?status=IN_REVIEW", finance_h))
        checks.append(probe(client, "B", "admin", "/api/v1/admin/client-billing/invoices", finance_h))

    super_h = login(client, "superadmin@demo.com")
    if super_h:
        ov = client.get("/api/v1/admin/finance-overview/summary", headers=super_h)
        links = ov.json().get("links", {}) if ov.status_code == 200 else {}
        log(
            "A",
            "debug_billing_audit.links",
            "finance overview payout link",
            {"therapistPayouts": links.get("therapistPayouts"), "ok": links.get("therapistPayouts", "").startswith("/admin/therapist-payouts")},
        )

    log("E", "debug_billing_audit.summary", "audit complete", {"all_ok": all(checks) if checks else False, "check_count": len(checks)})
    print("Billing audit:", "PASS" if all(checks) else "FAIL", f"({len(checks)} checks)")


if __name__ == "__main__":
    main()
