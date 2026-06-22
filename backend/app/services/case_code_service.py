from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case

MODULE_TOKENS: dict[str, str] = {
    "homecare": "HC",
    "shadow_support": "SS",
    "b2b": "B2",
}

_CODE_PATTERN = re.compile(r"^IC-(\d{4})-([A-Z0-9]{2})-(\d+)$")


def normalize_product_module(product_module: str) -> str:
    return str(product_module or "").strip().lower()


def module_token(product_module: str) -> str:
    slug = normalize_product_module(product_module)
    if slug in MODULE_TOKENS:
        return MODULE_TOKENS[slug]
    return slug[:2].upper() if slug else "XX"


def preview_case_code(product_module: str, year: int | None = None) -> str:
    y = year or datetime.now().year
    mod = module_token(normalize_product_module(product_module))
    return f"IC-{y}-{mod}-###"


def generate_case_code(db: Session, product_module: str) -> str:
    year = datetime.now().year
    mod = module_token(normalize_product_module(product_module))
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
