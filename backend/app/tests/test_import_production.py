"""Production CSV import script (dry-run and commit)."""
from __future__ import annotations

import csv
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment
from app.models.case import Case
from app.models.child import Child
from app.models.user import User
from app.seed.demo_seed import run as seed_run

BACKEND = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND / "scripts" / "import_production.py"


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()


def _run_import(import_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        "-m",
        "scripts.import_production",
        "--dir",
        str(import_dir),
        "--actor-email",
        "superadmin@demo.com",
        *extra,
    ]
    return subprocess.run(
        cmd,
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
    )


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


@pytest.fixture
def import_bundle(tmp_path: Path) -> tuple[Path, str]:
    suffix = uuid.uuid4().hex[:8]
    import_dir = tmp_path
    _write_csv(
        tmp_path / "staff.csv",
        ["email", "full_name", "external_employee_id", "role_names", "module_assignments", "password"],
        [[f"cm.import.{suffix}@insighte.in", "Import CM", f"CM-{suffix}", "CASE_MANAGER", "homecare", "ImportPass1!"]],
    )
    _write_csv(
        tmp_path / "therapists.csv",
        [
            "email",
            "full_name",
            "phone",
            "external_employee_id",
            "services_offered",
            "primary_cm_email",
            "password",
        ],
        [
            [
                f"th.import.{suffix}@insighte.in",
                "Import Therapist",
                "+919999999999",
                f"TH-{suffix}",
                "homecare",
                f"cm.import.{suffix}@insighte.in",
                "ImportPass1!",
            ]
        ],
    )
    _write_csv(
        tmp_path / "clients.csv",
        [
            "external_client_id",
            "child_first",
            "child_last",
            "parent_email",
            "parent_full_name",
            "phone",
            "send_invite",
            "password",
        ],
        [
            [
                f"CLI-{suffix}",
                "Import",
                "Child",
                f"parent.import.{suffix}@insighte.in",
                "Import Parent",
                "",
                "false",
                "ImportPass1!",
            ]
        ],
    )
    _write_csv(
        tmp_path / "cases.csv",
        [
            "external_case_ref",
            "external_client_id",
            "therapist_email",
            "cm_email",
            "service_type",
            "product_module",
            "case_code",
        ],
        [
            [
                f"CASE-{suffix}",
                f"CLI-{suffix}",
                f"th.import.{suffix}@insighte.in",
                f"cm.import.{suffix}@insighte.in",
                "Homecare",
                "homecare",
                f"IC-IMP-{suffix}",
            ]
        ],
    )
    return import_dir, suffix


def test_import_dry_run_succeeds(import_bundle: tuple[Path, str]):
    import_dir, _suffix = import_bundle
    proc = _run_import(import_dir, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "cases_created: 1" in proc.stdout
    assert "therapists_created: 1" in proc.stdout


def test_import_dry_run_missing_therapist_reports_error(tmp_path: Path):
    suffix = uuid.uuid4().hex[:8]
    _write_csv(
        tmp_path / "clients.csv",
        ["external_client_id", "child_first", "child_last", "parent_email", "parent_full_name"],
        [[f"CLI-{suffix}", "A", "B", f"p.{suffix}@x.com", "Parent"]],
    )
    _write_csv(
        tmp_path / "cases.csv",
        ["external_case_ref", "external_client_id", "therapist_email", "product_module"],
        [[f"C-{suffix}", f"CLI-{suffix}", "missing.therapist@x.com", "homecare"]],
    )
    proc = _run_import(tmp_path, "--dry-run")
    assert proc.returncode == 1
    assert "therapist not found" in proc.stdout


def test_import_commit_creates_entities(import_bundle: tuple[Path, str]):
    import_dir, suffix = import_bundle
    proc = _run_import(import_dir, "--commit")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "cases_errors: []" in proc.stdout, proc.stdout
    assert "cases_created: 1" in proc.stdout, proc.stdout
    db = SessionLocal()
    try:
        th_email = f"th.import.{suffix}@insighte.in"
        th = db.scalars(select(User).where(User.email == th_email)).first()
        assert th is not None
        assert th.external_employee_id == f"TH-{suffix}"
        child = db.scalars(select(Child).where(Child.external_client_id == f"CLI-{suffix}")).first()
        assert child is not None
        case = db.scalars(select(Case).where(Case.external_case_ref == f"CASE-{suffix}")).first()
        assert case is not None
        assign = db.scalars(select(CaseAssignment).where(CaseAssignment.case_id == case.id)).first()
        assert assign is not None
        assert assign.therapist_user_id == th.id
    finally:
        db.close()
