from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.seed.demo_seed import run as seed_run
from app.services import case_code_service
from app.core.database import SessionLocal


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_module_token_b2b():
    assert case_code_service.module_token("b2b") == "B2"
    assert case_code_service.module_token("B2B") == "B2"


def test_b2b_case_code_increments():
    db = SessionLocal()
    year = datetime.now().year
    first_code = f"IC-{year}-B2-901"
    second_code = f"IC-{year}-B2-902"
    try:
        child = db.scalars(select(Child).limit(1)).first()
        assert child is not None

        for code in (first_code, second_code):
            existing = db.scalars(select(Case).where(Case.case_code == code)).first()
            if existing:
                db.delete(existing)
        db.commit()

        db.add(
            Case(
                case_code=first_code,
                child_id=child.id,
                service_type="B2B",
                product_module="b2b",
                status=CaseStatus.PENDING_ALLOTMENT,
            )
        )
        db.commit()

        found = db.scalars(select(Case.case_code).where(Case.case_code == first_code)).first()
        assert found == first_code

        next_code = case_code_service.generate_case_code(db, "b2b")
        assert next_code == second_code

        again = case_code_service.generate_case_code(db, "B2B")
        assert again == second_code
    finally:
        for code in (first_code, second_code):
            row = db.scalars(select(Case).where(Case.case_code == code)).first()
            if row:
                db.delete(row)
        db.commit()
        db.close()
