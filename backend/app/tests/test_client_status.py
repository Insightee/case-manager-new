"""Tests for client status management."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.case import Case, CaseStatus
from app.services import client_status_service


# ---- helpers ----

def _get_admin_token(client: TestClient) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "superadmin@demo.com", "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---- service unit tests ----

class TestAdminAllowedTransitions:
    def test_active_to_suspended_allowed(self):
        assert CaseStatus.SUSPENDED.value in client_status_service.ADMIN_ALLOWED_TRANSITIONS[CaseStatus.ACTIVE.value]

    def test_active_to_pending_replacement_allowed(self):
        assert CaseStatus.PENDING_REPLACEMENT.value in client_status_service.ADMIN_ALLOWED_TRANSITIONS[CaseStatus.ACTIVE.value]

    def test_active_to_deactivated_allowed(self):
        assert CaseStatus.DEACTIVATED.value in client_status_service.ADMIN_ALLOWED_TRANSITIONS[CaseStatus.ACTIVE.value]

    def test_deactivated_is_terminal(self):
        assert client_status_service.ADMIN_ALLOWED_TRANSITIONS[CaseStatus.DEACTIVATED.value] == []

    def test_closed_is_terminal(self):
        assert client_status_service.ADMIN_ALLOWED_TRANSITIONS[CaseStatus.CLOSED.value] == []


class TestBillingCutoff:
    def _make_case(self, status: str, eff_date=None):
        class MockCase:
            pass
        c = MockCase()
        c.status = CaseStatus(status)
        c.status_effective_date = eff_date
        return c

    def test_active_returns_none(self):
        c = self._make_case("ACTIVE")
        assert client_status_service.get_case_billing_cutoff(c) is None

    def test_suspended_returns_effective_date(self):
        d = date(2026, 6, 1)
        c = self._make_case("SUSPENDED", d)
        assert client_status_service.get_case_billing_cutoff(c) == d

    def test_pending_replacement_returns_effective_date(self):
        d = date(2026, 6, 10)
        c = self._make_case("PENDING_REPLACEMENT", d)
        assert client_status_service.get_case_billing_cutoff(c) == d

    def test_deactivated_returns_effective_date(self):
        d = date(2026, 6, 15)
        c = self._make_case("DEACTIVATED", d)
        assert client_status_service.get_case_billing_cutoff(c) == d


# ---- API integration tests ----

class TestClientStatusAPI:
    def test_change_status_requires_auth(self, client: TestClient):
        r = client.post("/api/v1/cases/1/client-status", json={
            "new_status": "SUSPENDED",
            "effective_date": str(date.today()),
            "reason": "Test reason",
        })
        assert r.status_code in (401, 403)

    def test_missing_effective_date_returns_422(self, client: TestClient):
        token = _get_admin_token(client)
        r = client.post("/api/v1/cases/1/client-status",
            json={"new_status": "SUSPENDED", "reason": "Test reason"},
            headers=_auth(token)
        )
        assert r.status_code == 422

    def test_short_reason_returns_422(self, client: TestClient):
        token = _get_admin_token(client)
        r = client.post("/api/v1/cases/1/client-status",
            json={"new_status": "SUSPENDED", "effective_date": str(date.today()), "reason": "ab"},
            headers=_auth(token)
        )
        assert r.status_code == 422

    def test_audit_trail_endpoint_requires_auth(self, client: TestClient):
        r = client.get("/api/v1/cases/1/client-status/audit")
        assert r.status_code in (401, 403)

    def test_audit_trail_returns_structure(self, client: TestClient):
        token = _get_admin_token(client)
        # Use case 1 which should exist from seed
        r = client.get("/api/v1/cases/1/client-status/audit", headers=_auth(token))
        if r.status_code == 404:
            pytest.skip("Case 1 not found in test DB")
        assert r.status_code == 200
        data = r.json()
        assert "currentStatus" in data
        assert "audit" in data
        assert isinstance(data["audit"], list)

    def test_status_report_requires_permission(self, client: TestClient):
        r = client.get("/api/v1/admin/reports/client-status")
        assert r.status_code in (401, 403)

    def test_status_report_accessible_to_admin(self, client: TestClient):
        token = _get_admin_token(client)
        r = client.get("/api/v1/admin/reports/client-status", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
