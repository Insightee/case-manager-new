"""Dynamic service categories and multi-module product registration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.rbac_access import build_module_registry
from app.main import app
from app.models.service_category import ServiceCategory
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services.service_category_service import resolved_product_modules

client = TestClient(app)

SERVICE_ID = "test_ot_svc"
PM_HOME = "test_ot_home"
PM_SCHOOL = "test_ot_school"


def _reset_sqlite_db() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return
    rel = url.replace("sqlite:///", "")
    db_path = Path(rel) if os.path.isabs(rel) else Path(__file__).resolve().parents[2] / rel.lstrip("./")
    engine.dispose()
    for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        if path.exists():
            path.unlink()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    _reset_sqlite_db()
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_test_ot_service(admin_h: dict[str, str]) -> dict:
    r = client.post(
        "/api/v1/admin/service-categories",
        headers=admin_h,
        json={
            "id": SERVICE_ID,
            "label": "Test OT",
            "description": "Dual-module test service",
            "sort_order": 99,
            "product_modules": [
                {"id": PM_HOME, "label": "OT — Home"},
                {"id": PM_SCHOOL, "label": "OT — School"},
            ],
        },
    )
    if r.status_code == 400 and "already exists" in r.text:
        listed = client.get("/api/v1/admin/service-categories", headers=admin_h)
        assert listed.status_code == 200
        for row in listed.json():
            if row["id"] == SERVICE_ID:
                return row
        raise AssertionError(r.text)
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["product_modules"]) == 2
    ids = {pm["id"] for pm in body["product_modules"]}
    assert ids == {PM_HOME, PM_SCHOOL}
    return body


def test_create_service_category_with_two_product_modules():
    admin_h = _headers(_login("superadmin@demo.com"))
    _create_test_ot_service(admin_h)

    catalog = client.get("/api/v1/admin/modules", headers=admin_h)
    assert catalog.status_code == 200
    module_ids = {m["id"] for m in catalog.json()["modules"]}
    assert PM_HOME in module_ids
    assert PM_SCHOOL in module_ids


def test_registry_includes_both_product_modules():
    db = SessionLocal()
    try:
        cat = db.get(ServiceCategory, SERVICE_ID)
        if not cat:
            admin_h = _headers(_login("superadmin@demo.com"))
            _create_test_ot_service(admin_h)
            cat = db.get(ServiceCategory, SERVICE_ID)
        assert cat is not None
        registry = build_module_registry(db)
        assert PM_HOME in registry
        assert PM_SCHOOL in registry
        assert registry[PM_HOME].case_product_modules == (PM_HOME,)
    finally:
        db.close()


def test_resolved_product_modules_fallback_for_legacy_row():
    db = SessionLocal()
    try:
        cat = ServiceCategory(
            id="legacy_svc_only",
            label="Legacy Service",
            description="",
            sort_order=0,
            product_modules=None,
            is_active=True,
        )
        db.merge(cat)
        db.commit()
        pms = resolved_product_modules(cat)
        assert pms == [{"id": "legacy_svc_only", "label": "Legacy Service"}]
    finally:
        legacy = db.get(ServiceCategory, "legacy_svc_only")
        if legacy:
            db.delete(legacy)
            db.commit()
        db.close()


def test_superadmin_me_and_clinical_modules_include_dynamic_modules():
    admin_h = _headers(_login("superadmin@demo.com"))
    _create_test_ot_service(admin_h)

    me = client.get("/api/v1/auth/me", headers=admin_h)
    assert me.status_code == 200
    me_modules = {m["id"] for m in me.json()["modules"]}
    assert PM_HOME in me_modules
    assert PM_SCHOOL in me_modules

    clinical = client.get("/api/v1/auth/clinical-product-modules", headers=admin_h)
    assert clinical.status_code == 200
    clinical_ids = {row["id"] for row in clinical.json()}
    assert PM_HOME in clinical_ids
    assert PM_SCHOOL in clinical_ids


def test_assigned_case_manager_sees_assigned_product_modules_only():
    admin_h = _headers(_login("superadmin@demo.com"))
    _create_test_ot_service(admin_h)

    db = SessionLocal()
    try:
        cm = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        assert cm is not None
        cm_id = cm.id
        prior = list(cm.module_assignments or [])
    finally:
        db.close()

    patch = client.patch(
        f"/api/v1/admin/users/{cm_id}",
        headers=admin_h,
        json={"module_assignments": prior + [PM_HOME, PM_SCHOOL]},
    )
    assert patch.status_code == 200

    cm_token = _login("casemanager@demo.com")
    cm_h = _headers(cm_token)

    me = client.get("/api/v1/auth/me", headers=cm_h)
    assert me.status_code == 200
    me_ids = {m["id"] for m in me.json()["modules"]}
    assert PM_HOME in me_ids
    assert PM_SCHOOL in me_ids

    clinical = client.get("/api/v1/auth/clinical-product-modules", headers=cm_h)
    assert clinical.status_code == 200
    clinical_ids = {row["id"] for row in clinical.json()}
    assert PM_HOME in clinical_ids
    assert PM_SCHOOL in clinical_ids
    assert "homecare" in clinical_ids
