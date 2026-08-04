"""Client billing visibility gate: therapist sees none; parent sees own case only.

Run before client-billing loop changes to pin role serializers at the API boundary.
"""
from __future__ import annotations

import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.client_billing import ClientInvoice
from app.models.parent import ParentGuardian
from app.models.user import User
from app.core.permissions import RoleName
from app.seed.demo_seed import get_or_create_user, run as seed_run
from sqlalchemy import select

client = TestClient(app)

# Keys that must never appear in therapist-facing JSON (client money-IN domain).
THERAPIST_FORBIDDEN_CLIENT_BILLING_KEYS = frozenset(
    {
        "client_invoice",
        "clientInvoice",
        "client_invoice_id",
        "clientInvoiceId",
        "client_invoices",
        "clientInvoices",
        "client_payment",
        "clientPayment",
        "client_payments",
        "clientPayments",
        "care_package",
        "carePackage",
        "care_packages",
        "carePackages",
        "billing_dispute",
        "billingDispute",
        "billing_disputes",
        "billingDisputes",
        "package_amount_inr",
        "packageAmountInr",
        "client_rate_per_session_inr",
        "clientRatePerSessionInr",
        "client_monthly_rate_inr",
        "clientMonthlyRateInr",
        "client_billing_mode",
        "clientBillingMode",
        "insighte_margin_inr",
        "insighteMarginInr",
        "margin_inr",
        "marginInr",
        "estimated_margin",
        "estimatedMargin",
        "estimatedmargin",
        "payout_amount_inr",
        "payoutAmountInr",
        "amount_paid_inr",
        "amountPaidInr",
        "gateway_payment_url",
        "gatewayPaymentUrl",
        "parent_user_id",
        "parentUserId",
    }
)

# Substrings in serialized JSON (case-insensitive, underscores stripped) forbidden for therapists.
THERAPIST_FORBIDDEN_SUBSTRINGS = (
    "clientinvoice",
    "clientpayment",
    "carepackage",
    "billingdispute",
    "insightemargin",
    "estimatedmargin",
    "clientratepersession",
    "packageamountinr",
)

# Parent must not see finance margin / payout / other-family identifiers.
PARENT_FORBIDDEN_KEYS = frozenset(
    {
        "insighte_margin_inr",
        "insighteMarginInr",
        "margin_inr",
        "marginInr",
        "estimated_margin",
        "estimatedMargin",
        "payout_amount_inr",
        "payoutAmountInr",
        "therapist_payout",
        "therapistPayout",
        "pay_share_amount_inr",
        "pay_share_amount",
        "client_rate_per_session_inr",
        "clientRatePerSessionInr",
        "package_amount_inr",
        "packageAmountInr",
        "parent_user_id",
        "parentUserId",
    }
)

PARENT_FORBIDDEN_SUBSTRINGS = (
    "insightemargin",
    "estimatedmargin",
    "therapistpayout",
    "payoutamountinr",
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _walk_forbidden_keys(payload: Any, forbidden: frozenset[str], *, path: str = "root") -> list[str]:
    hits: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden:
                hits.append(f"{path}.{key}")
            hits.extend(_walk_forbidden_keys(value, forbidden, path=f"{path}.{key}"))
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            hits.extend(_walk_forbidden_keys(item, forbidden, path=f"{path}[{idx}]"))
    return hits


def _assert_no_substrings(text: str, substrings: tuple[str, ...], *, label: str) -> None:
    normalized = text.lower().replace("_", "")
    for sub in substrings:
        assert sub not in normalized, f"{label}: forbidden substring {sub!r} found in payload"


def _therapist_probe_endpoints(headers: dict[str, str]) -> list[tuple[str, int, Any]]:
    """Endpoints a therapist commonly hits; none should expose client billing."""
    probes: list[tuple[str, int, Any]] = []
    specs = [
        ("GET", "/api/v1/therapist/home"),
        ("GET", "/api/v1/therapist/my-cases"),
        ("GET", "/api/v1/therapist/sessions/workspace"),
        ("GET", "/api/v1/therapist/reports/pipeline"),
        ("GET", "/api/v1/invoices"),
        ("GET", "/api/v1/invoices/preview?month=2026-05"),
        ("GET", "/api/v1/parent/billing/dashboard"),
        ("GET", "/api/v1/admin/client-billing/invoices"),
    ]
    for method, path in specs:
        if method == "GET":
            r = client.get(path, headers=headers)
        else:
            continue
        probes.append((path, r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text))
    # Invoice breakdown when therapist has a payout invoice
    listed = client.get("/api/v1/invoices", headers=headers)
    if listed.status_code == 200 and listed.json():
        inv_id = listed.json()[0]["id"]
        br = client.get(f"/api/v1/invoices/{inv_id}/breakdown", headers=headers)
        probes.append((f"/api/v1/invoices/{inv_id}/breakdown", br.status_code, br.json() if br.status_code == 200 else br.text))
    return probes


def test_therapist_endpoints_reject_or_omit_client_billing():
    headers = _login("therapist@demo.com")
    probes = _therapist_probe_endpoints(headers)

    for path, status, body in probes:
        if path.startswith("/api/v1/parent/billing") or path.startswith("/api/v1/admin/client-billing"):
            assert status in (403, 404), f"Therapist must not access client billing route {path} (got {status})"
            continue
        assert status == 200, f"Expected 200 from {path}, got {status}: {body}"
        text = json.dumps(body) if not isinstance(body, str) else body
        key_hits = _walk_forbidden_keys(body if isinstance(body, (dict, list)) else {}, THERAPIST_FORBIDDEN_CLIENT_BILLING_KEYS)
        assert not key_hits, f"Therapist payload leaked client billing keys at {path}: {key_hits}"
        _assert_no_substrings(text, THERAPIST_FORBIDDEN_SUBSTRINGS, label=f"therapist {path}")


def test_therapist_cannot_access_parent_billing_routes():
    headers = _login("therapist@demo.com")
    for path in (
        "/api/v1/parent/billing/dashboard",
        "/api/v1/parent/billing/invoices",
        "/api/v1/parent/billing/packages",
    ):
        r = client.get(path, headers=headers)
        assert r.status_code == 403, f"Therapist should be forbidden from {path}, got {r.status_code}"


def _parent_billing_endpoints(headers: dict[str, str]) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    dash = client.get("/api/v1/parent/billing/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    out.append(("/api/v1/parent/billing/dashboard", dash.json()))
    listed = client.get("/api/v1/parent/billing/invoices", headers=headers)
    assert listed.status_code == 200
    out.append(("/api/v1/parent/billing/invoices", listed.json()))
    for inv in listed.json()[:3]:
        detail = client.get(f"/api/v1/parent/billing/invoices/{inv['id']}", headers=headers)
        assert detail.status_code == 200
        out.append((f"/api/v1/parent/billing/invoices/{inv['id']}", detail.json()))
        for line in detail.json().get("lines") or [][:2]:
            sess = client.get(f"/api/v1/parent/billing/lines/{line['id']}/session", headers=headers)
            if sess.status_code == 200:
                out.append((f"/api/v1/parent/billing/lines/{line['id']}/session", sess.json()))
    pkgs = client.get("/api/v1/parent/billing/packages", headers=headers)
    if pkgs.status_code == 200:
        out.append(("/api/v1/parent/billing/packages", pkgs.json()))
    return out


def test_parent_billing_payloads_exclude_margin_and_payout_fields():
    headers = _login("parent@demo.com")
    for path, body in _parent_billing_endpoints(headers):
        text = json.dumps(body)
        key_hits = _walk_forbidden_keys(body, PARENT_FORBIDDEN_KEYS)
        assert not key_hits, f"Parent billing leaked finance keys at {path}: {key_hits}"
        _assert_no_substrings(text, PARENT_FORBIDDEN_SUBSTRINGS, label=f"parent {path}")


def test_parent_billing_scoped_to_own_cases_only():
    db = SessionLocal()
    try:
        other = get_or_create_user(
            db,
            "parent-other-billing@demo.com",
            "demo123",
            "Other Parent Billing",
            RoleName.PARENT.value,
        )
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == other.id)).first()
        if not pg:
            pg = ParentGuardian(user_id=other.id)
            db.add(pg)
            db.flush()
        primary_inv = db.scalars(select(ClientInvoice).limit(1)).first()
        assert primary_inv is not None, "Seed should include client invoices"
        db.commit()
        foreign_invoice_id = primary_inv.id
    finally:
        db.close()

    other_headers = _login("parent-other-billing@demo.com")
    other_cases = client.get("/api/v1/parent/cases", headers=other_headers).json()
    other_case_db_ids = {c["id"] for c in other_cases}

    primary_headers = _login("parent@demo.com")
    primary_cases = {c["id"] for c in client.get("/api/v1/parent/cases", headers=primary_headers).json()}
    primary_dash = client.get("/api/v1/parent/billing/dashboard", headers=primary_headers).json()
    for inv in primary_dash.get("invoices") or []:
        case_db_id = inv.get("caseDbId")
        if case_db_id is not None:
            assert case_db_id in primary_cases, f"Invoice {inv.get('id')} references foreign case {case_db_id}"

    other_list = client.get("/api/v1/parent/billing/invoices", headers=other_headers).json()
    other_ids = {i["id"] for i in other_list}
    if not other_case_db_ids:
        assert foreign_invoice_id not in other_ids

    if foreign_invoice_id and not other_case_db_ids:
        r = client.get(f"/api/v1/parent/billing/invoices/{foreign_invoice_id}", headers=other_headers)
        assert r.status_code == 404


def test_parent_home_billing_summary_excludes_margin():
    headers = _login("parent@demo.com")
    home = client.get("/api/v1/parent/home", headers=headers)
    assert home.status_code == 200
    text = home.text.lower().replace("_", "")
    assert "estimatedmargin" not in text
    assert "insightemargin" not in text
    assert "therapistpayout" not in text
