from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.seed.demo_seed import run as seed_run
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_forgot_password_always_200():
    r = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert r.status_code == 200
    assert "account exists" in r.json()["message"].lower()


@patch("app.services.password_reset_service.enqueue_password_reset_email", return_value=1)
def test_password_reset_flow(mock_enqueue_email):
    email = "therapist@demo.com"
    new_password = "newpass456"

    r = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert mock_enqueue_email.called
    reset_url = mock_enqueue_email.call_args.kwargs["reset_url"]
    plain_token = reset_url.rstrip("/").split("/")[-1]

    preview = client.get(f"/api/v1/auth/reset-password/{plain_token}/preview")
    assert preview.status_code == 200
    assert "@" in preview.json()["email"]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain_token, "password": new_password},
    )
    assert reset.status_code == 200

    login_old = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert login_old.status_code == 401

    login_new = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    assert login_new.status_code == 200

    # restore demo password for other tests
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == email)).first()
        from app.core.security import hash_password

        user.password_hash = hash_password("demo123")
        db.commit()
    finally:
        db.close()


def test_reset_token_rejected_when_used():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        from app.services import password_reset_service

        plain = password_reset_service.create_reset_token(db, user)
        password_reset_service.reset_password(db, plain, "onceonly1")
        db.commit()
    finally:
        db.close()

    again = client.post(
        "/api/v1/auth/reset-password",
        json={"token": plain, "password": "onceonly2"},
    )
    assert again.status_code == 400

    preview = client.get(f"/api/v1/auth/reset-password/{plain}/preview")
    assert preview.status_code == 404

    # restore parent password
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        from app.core.security import hash_password

        user.password_hash = hash_password("demo123")
        rows = db.scalars(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        ).all()
        for row in rows:
            db.delete(row)
        db.commit()
    finally:
        db.close()


@patch("app.services.email.service.send_email", return_value=True)
def test_email_layer_invoked_when_smtp_configured(mock_send):
    from app.services import email_service

    with (
        patch("app.services.email.service.is_smtp_configured", return_value=True),
        patch.object(email_service.settings, "smtp_host", "smtp.example.com"),
        patch.object(email_service.settings, "smtp_from", "noreply@example.com"),
    ):
        email_service.password_reset_email(
            to="test@example.com",
            full_name="Test",
            reset_url="http://localhost/reset",
        )
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs.get("body_html")
