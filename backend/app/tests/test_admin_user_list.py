"""Admin user list search, filters, and pagination."""

import secrets

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_list_users_search_by_email():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/users?search=admin@demo.com", headers=headers)
    assert res.status_code == 200
    body = res.json()
    emails = [u["email"] for u in body["items"]]
    assert "admin@demo.com" in emails


def test_list_users_exclude_roles():
    headers = _login("superadmin@demo.com")
    res = client.get(
        "/api/v1/admin/users?exclude_roles=THERAPIST,PARENT&page_size=100",
        headers=headers,
    )
    assert res.status_code == 200
    for u in res.json()["items"]:
        roles = set(u.get("roles") or [])
        assert "THERAPIST" not in roles
        assert "PARENT" not in roles


def test_list_users_pagination_page_two():
    headers = _login("superadmin@demo.com")
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.services import auth_service

    tag = secrets.token_hex(4)
    with SessionLocal() as db:
        for i in range(105):
            auth_service.create_user(
                db,
                email=f"paginate.{tag}.{i:03d}@demo.com",
                password="demo123",
                full_name=f"Paginate User {i}",
                role_names=["VIEWER"],
            )
        db.commit()

    page1 = client.get("/api/v1/admin/users?page=1&page_size=100&sort=email_asc", headers=headers)
    page2 = client.get("/api/v1/admin/users?page=2&page_size=100&sort=email_asc", headers=headers)
    assert page1.status_code == 200
    assert page2.status_code == 200
    ids1 = {u["id"] for u in page1.json()["items"]}
    ids2 = {u["id"] for u in page2.json()["items"]}
    assert page1.json()["total"] >= 105
    assert len(ids1) == 100
    assert len(ids2) >= 5
    assert not ids1.intersection(ids2)


def test_case_manager_can_list_users_with_user_read():
    headers = _login("casemanager@demo.com")
    res = client.get("/api/v1/admin/users?page_size=10", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1


def test_list_users_sort_created_at_desc():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/users?page_size=5&sort=created_at_desc", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) <= 5
