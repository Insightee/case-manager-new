#!/usr/bin/env python3
"""Production readiness smoke checks (run against Railway or local with production env).

Usage:
  cd backend && python scripts/production_smoke.py
  API_BASE_URL=https://your-api.up.railway.app python scripts/production_smoke.py

Optional:
  SMOKE_TEST_EMAIL=admin@example.com SMOKE_TEST_PASSWORD=...  # login + optional email send
  SMOKE_SKIP_EMAIL=1  # skip ZeptoMail send probe
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
# migration_util is imported by some Alembic revision modules
_alembic_dir = _BACKEND / "alembic"
if str(_alembic_dir) not in sys.path:
    sys.path.insert(0, str(_alembic_dir))

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.production_checks import validate_production_settings
from app.storage.factory import get_storage_backend, reset_storage_backend_for_tests
from app.storage.object_io import is_object_store_key, put_stored_bytes, read_stored_bytes


def _step(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    if not ok:
        raise SystemExit(1)


def _check_production_config() -> None:
    try:
        validate_production_settings()
        _step("Production config validation", True)
    except RuntimeError as exc:
        _step("Production config validation", False, str(exc).split("\n")[0])


def _check_db_and_migrations() -> None:
    url = settings.database_url
    if settings.is_sqlite:
        _step("DATABASE_URL is Postgres", False, "still SQLite")
        return
    _step("DATABASE_URL is Postgres", True)

    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    _step("Database connection", True)

    cfg = Config(str(_BACKEND / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    with engine.connect() as conn:
        try:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
            current = row[0] if row else None
        except Exception:
            current = None
    _step("Alembic migrations at head", current == head, f"current={current} head={head}")


def _check_r2_roundtrip() -> None:
    provider = (settings.storage_provider or "local").strip().lower()
    if settings.is_development:
        key, _ = put_stored_bytes(
            "smoke",
            "local",
            filename="ping.bin",
            data=b"local-smoke",
            content_type="application/octet-stream",
        )
        ok = read_stored_bytes(key) == b"local-smoke"
        get_storage_backend().delete(key)
        _step("Local storage upload + download (dev)", ok)
        return
    if provider != "r2":
        _step("STORAGE_PROVIDER is r2", False, f"got {provider}")
        return
    _step("STORAGE_PROVIDER is r2", True)
    reset_storage_backend_for_tests()
    payload = b"smoke-r2-" + os.urandom(8)
    key, prov = put_stored_bytes(
        "smoke",
        "connectivity",
        filename="ping.bin",
        data=payload,
        content_type="application/octet-stream",
    )
    assert is_object_store_key(key)
    backend = get_storage_backend()
    got = read_stored_bytes(key)
    _step("R2 upload + download", got == payload, f"provider={prov} backend={backend.provider}")
    try:
        backend.delete(key)
    except Exception:
        pass


def _check_no_legacy_upload_dirs_in_prod() -> None:
    """Warn if ephemeral upload dirs exist on disk in production (Railway should use R2 only)."""
    if settings.is_development:
        _step("Legacy uploads/ dirs (skipped in dev)", True)
        return
    if not os.environ.get("RAILWAY_REPLICA_ID"):
        _step("Legacy uploads/ dirs (skipped outside Railway container)", True)
        return
    legacy_roots = [
        _BACKEND / "uploads" / "tickets",
        _BACKEND / "uploads" / "incidents",
        _BACKEND / "uploads" / "billing",
        _BACKEND / "uploads" / "avatars",
        _BACKEND / "uploads" / "iep",
    ]
    found = [str(p.relative_to(_BACKEND)) for p in legacy_roots if p.is_dir() and any(p.iterdir())]
    _step(
        "No legacy uploads/* content on disk",
        not found,
        ", ".join(found) if found else "clean",
    )


def _check_api_health(base: str) -> None:
    r = httpx.get(f"{base.rstrip('/')}/health", timeout=30.0)
    _step("GET /health", r.status_code == 200, r.text[:120])


def _check_email_optional(base: str) -> None:
    if os.environ.get("SMOKE_SKIP_EMAIL", "").strip().lower() in ("1", "true", "yes"):
        _step("ZeptoMail probe (skipped)", True)
        return
    from app.services.email.service import is_smtp_configured, send_email

    if not is_smtp_configured():
        _step("SMTP configured for ZeptoMail", False, "is_smtp_configured() false")
        return
    _step("SMTP configured for ZeptoMail", True)

    to = (os.environ.get("SMOKE_TEST_EMAIL") or "").strip()
    if not to:
        _step("ZeptoMail send probe (skipped, set SMOKE_TEST_EMAIL)", True)
        return
    ok = send_email(
        to=to,
        subject="Insighte production smoke test",
        body_text="If you received this, ZeptoMail SMTP is working.",
    )
    _step("ZeptoMail send probe", ok, to)


def main() -> None:
    base = (os.environ.get("API_BASE_URL") or os.environ.get("PUBLIC_API_URL") or "").strip()
    print(f"APP_ENV={settings.app_env} STORAGE_PROVIDER={settings.storage_provider}")
    if not settings.is_development:
        _check_production_config()
    else:
        print("[INFO] APP_ENV is development — skipping strict production validation")
    _check_db_and_migrations()
    _check_r2_roundtrip()
    _check_no_legacy_upload_dirs_in_prod()
    if base:
        _check_api_health(base)
        _check_email_optional(base)
    else:
        print("[INFO] Set API_BASE_URL to probe /health on a deployed API")
        _check_email_optional("")
    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
