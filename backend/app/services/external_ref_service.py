from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.external_ref import ExternalRef


def get_external_id_db(db: Session, provider: str, entity_type: str, entity_id: int) -> str | None:
    return db.scalar(
        select(ExternalRef.external_id).where(
            ExternalRef.provider == provider,
            ExternalRef.entity_type == entity_type,
            ExternalRef.entity_id == entity_id,
        )
    )


def upsert_external_ref(db: Session, provider: str, entity_type: str, entity_id: int, external_id: str) -> ExternalRef:
    row = db.scalar(
        select(ExternalRef).where(
            ExternalRef.provider == provider,
            ExternalRef.entity_type == entity_type,
            ExternalRef.entity_id == entity_id,
        )
    )
    if row:
        row.external_id = external_id
        db.flush()
        return row
    row = ExternalRef(
        provider=provider,
        entity_type=entity_type,
        entity_id=entity_id,
        external_id=external_id,
    )
    db.add(row)
    db.flush()
    return row
