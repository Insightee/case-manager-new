"""Insights Engine — data preview, snapshot generation, RBAC."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.user import User
from app.services import clinical_insights_preview_service as preview_svc
from app.services.ai_gateway_service import AIGatewayService

ensure_sqlite_schema_patches()
client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_data_preview_no_ai():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        preview = preview_svc.build_data_preview(db, case.id, month)
        assert preview["case_id"] == case.id
        assert "sessions_available" in preview
        assert "input_hash" in preview
        assert preview["input_hash"]


def test_data_preview_api():
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        r = client.get(f"/api/v1/cases/{case.id}/insights/data-preview?month={month}", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["month"] == month
        assert "logs_missing_details" in body


def test_generate_snapshot_mock():
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        r = client.post(
            f"/api/v1/cases/{case.id}/insights/generate-snapshot",
            headers=headers,
            json={"month": month, "insight_type": "full_snapshot"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ai_output_json") or body.get("ai_output_text")
        assert body["insight_type"] == "full_snapshot"

        r2 = client.post(
            f"/api/v1/cases/{case.id}/insights/generate-snapshot",
            headers=headers,
            json={"month": month, "insight_type": "full_snapshot"},
        )
        assert r2.status_code == 200
        assert r2.json().get("reused") is True


def test_regenerate_requires_force():
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        client.post(
            f"/api/v1/cases/{case.id}/insights/generate-snapshot",
            headers=headers,
            json={"month": month, "insight_type": "goal_suggestions", "force_regenerate": True},
        )
        r = client.post(
            f"/api/v1/cases/{case.id}/insights/generate-snapshot",
            headers=headers,
            json={"month": month, "insight_type": "goal_suggestions", "force_regenerate": True},
        )
        assert r.status_code == 200


def test_parent_blocked_from_snapshots():
    headers = _login("parent@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        r = client.get(f"/api/v1/cases/{case.id}/insights/data-preview?month={month}", headers=headers)
        assert r.status_code == 403


def test_therapist_cannot_approve_snapshot():
    therapist_headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        gen = client.post(
            f"/api/v1/cases/{case.id}/insights/generate-snapshot",
            headers=therapist_headers,
            json={"month": month, "insight_type": "parent_safe_draft", "force_regenerate": True},
        )
        snap_id = gen.json()["id"]
        r = client.post(
            f"/api/v1/cases/{case.id}/insights/snapshots/{snap_id}/approve",
            headers=therapist_headers,
        )
        assert r.status_code == 403


def test_reference_retrieval_keyword_fallback():
    with SessionLocal() as db:
        from app.services import reference_document_service as doc_svc
        from app.services import reference_retrieval_service as ref_svc

        user = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        doc = doc_svc.create_document(
            db,
            title="Transition strategy pool",
            document_type="strategy_pool",
            raw_text="Visual countdown helps classroom transitions. Offer choice of route.",
            uploaded_by=user.id,
        )
        doc_svc.chunk_document(db, doc.id)
        doc_svc.activate_document(db, doc.id, user.id)
        chunks = ref_svc.retrieve_reference_chunks(
            db,
            query="transition visual countdown",
            role="therapist",
            case_id=None,
            user_id=user.id,
            top_k=3,
        )
        assert len(chunks) >= 1


def test_mock_gateway_clinical_snapshot():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        from app.services import clinical_insight_summary_service as summary_svc

        month = datetime.now(timezone.utc).strftime("%Y-%m")
        summary = summary_svc.build_monthly_case_summary(db, case.id, month)
        out = AIGatewayService.generate_clinical_snapshot(
            db,
            user_id=user.id,
            case_id=case.id,
            summary=summary,
            insight_type="full_snapshot",
            role="therapist",
        )
        assert out["output"]["snapshot_summary"]
        assert out["provider"] in ("mock", "openai", "gemini")
