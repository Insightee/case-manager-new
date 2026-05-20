from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case

MODULE_TOKENS: dict[str, str] = {
    "homecare": "HC",
    "shadow_support": "SS",
}

_CODE_PATTERN = re.compile(r"^IC-(\d{4})-([A-Z]{2})-(\d+)$")


def module_token(product_module: str) -> str:
    return MODULE_TOKENS.get(product_module, product_module[:2].upper())


def preview_case_code(product_module: str, year: int | None = None) -> str:
    y = year or datetime.now().year
    mod = module_token(product_module)
    return f"IC-{y}-{mod}-###"


def generate_case_code(db: Session, product_module: str) -> str:
    year = datetime.now().year
    mod = module_token(product_module)
    prefix = f"IC-{year}-{mod}-"
    rows = db.scalars(select(Case.case_code).where(Case.case_code.like(f"{prefix}%"))).all()
    max_seq = 0
    for code in rows:
        m = _CODE_PATTERN.match(code)
        if m and m.group(1) == str(year) and m.group(2) == mod:
            max_seq = max(max_seq, int(m.group(3)))
    return f"{prefix}{max_seq + 1:03d}"


def ensure_unique_case_code(db: Session, case_code: str) -> None:
    existing = db.scalars(select(Case.id).where(Case.case_code == case_code)).first()
    if existing:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail=f"Case code {case_code} already exists")
