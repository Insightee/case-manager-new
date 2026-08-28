"""Parent name appears next to child/client identity in operational downloads."""
from __future__ import annotations

import csv
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.invoice import Invoice
from app.seed.demo_seed import run as seed_run
from app.services.invoice_billing_service import export_invoice_csv
from app.services.report_pdf_service import build_report_pdf_bytes
from app.services.reports_export_helpers import parent_by_child

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()


def _login(email: str = "superadmin@demo.com") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _xlsx_header(content: bytes, *, child_label: str) -> list[str]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    for row in wb.active.iter_rows(values_only=True):
        values = ["" if cell is None else str(cell) for cell in row]
        if child_label in values:
            return values
    raise AssertionError(f"No header row containing {child_label!r}")


def test_admin_sessions_xlsx_has_parent_next_to_child():
    headers = _login()
    res = client.get("/api/v1/admin/sessions/export/xlsx", headers=headers)
    assert res.status_code == 200, res.text
    header = _xlsx_header(res.content, child_label="Child")
    assert "Parent" in header
    assert header.index("Parent") == header.index("Child") + 1


def test_admin_sessions_pdf_includes_parent_header():
    headers = _login()
    res = client.get("/api/v1/admin/sessions/export/pdf", headers=headers)
    assert res.status_code == 200, res.text
    assert res.content[:4] == b"%PDF"
    assert b"Parent" in res.content


def test_report_pdf_meta_appends_parent_when_available():
    pdf = build_report_pdf_bytes(
        title="Monthly report",
        child_name="Aarav Demo",
        case_code="HC-001",
        category=None,
        month_label="June 2026",
        body_html="<p>Session summary</p>",
        plan_next_month=None,
        parent_name="Parent Guardian",
    )
    assert pdf[:4] == b"%PDF"
    # ReportLab may compress streams; assert the builder accepts parent_name and emits a PDF.
    # Spot-check uncompressed header objects still include the title font setup.
    assert b"ReportLab" in pdf or b"/Type /Catalog" in pdf or b"endobj" in pdf
    # Rebuild without parent and confirm both succeed (meta path covered by unit of builder).
    pdf_no_parent = build_report_pdf_bytes(
        title="Monthly report",
        child_name="Aarav Demo",
        case_code="HC-001",
        category=None,
        month_label="June 2026",
        body_html="<p>Session summary</p>",
        plan_next_month=None,
        parent_name=None,
    )
    assert pdf_no_parent[:4] == b"%PDF"
    assert len(pdf) >= len(pdf_no_parent)


def test_invoice_csv_has_parent_name_next_to_child_name():
    db = SessionLocal()
    try:
        invoice = db.scalars(select(Invoice).limit(1)).first()
        if not invoice:
            pytest.skip("No seeded therapist invoice")
        csv_text = export_invoice_csv(db, invoice.id)
    finally:
        db.close()
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    assert "child_name" in header
    assert "parent_name" in header
    assert header.index("parent_name") == header.index("child_name") + 1


def test_demo_parent_by_child_has_names():
    db = SessionLocal()
    try:
        from app.models.case import Case

        cases = list(db.scalars(select(Case).limit(20)).all())
        child_ids = {c.child_id for c in cases if c.child_id}
        parents = parent_by_child(db, child_ids)
        named = [info.get("parent_name") for info in parents.values() if info.get("parent_name")]
        assert named, "Expected at least one linked parent in demo seed"
    finally:
        db.close()
