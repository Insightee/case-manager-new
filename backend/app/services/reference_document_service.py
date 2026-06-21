"""Clinical reference document management."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_reference import ClinicalReferenceChunk, ClinicalReferenceDocument

CHUNK_SIZE = 1200


def create_document(
    db: Session,
    *,
    title: str,
    document_type: str,
    raw_text: str,
    uploaded_by: int,
    description: str | None = None,
    version: str = "1",
) -> ClinicalReferenceDocument:
    doc = ClinicalReferenceDocument(
        title=title,
        document_type=document_type,
        description=description,
        raw_text=raw_text,
        version=version,
        status="draft",
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def chunk_document(db: Session, document_id: int) -> list[ClinicalReferenceChunk]:
    doc = db.get(ClinicalReferenceDocument, document_id)
    if not doc:
        raise ValueError("Document not found")

    existing = db.scalars(
        select(ClinicalReferenceChunk).where(ClinicalReferenceChunk.document_id == document_id)
    ).all()
    for c in existing:
        db.delete(c)

    text = doc.raw_text or ""
    chunks: list[ClinicalReferenceChunk] = []
    idx = 0
    pos = 0
    while pos < len(text):
        piece = text[pos : pos + CHUNK_SIZE]
        ch = ClinicalReferenceChunk(
            document_id=document_id,
            chunk_index=idx,
            chunk_title=f"{doc.title} — part {idx + 1}",
            chunk_text=piece,
            token_estimate=max(1, len(piece.split())),
        )
        db.add(ch)
        chunks.append(ch)
        idx += 1
        pos += CHUNK_SIZE
    db.commit()
    return chunks


def activate_document(db: Session, document_id: int, approved_by: int) -> ClinicalReferenceDocument:
    doc = db.get(ClinicalReferenceDocument, document_id)
    if not doc:
        raise ValueError("Document not found")
    doc.status = "active"
    doc.approved_by = approved_by
    db.commit()
    db.refresh(doc)
    return doc


def archive_document(db: Session, document_id: int) -> None:
    doc = db.get(ClinicalReferenceDocument, document_id)
    if doc:
        doc.status = "archived"
        db.commit()


def list_documents(db: Session, status: str | None = None) -> list[dict[str, Any]]:
    q = select(ClinicalReferenceDocument).order_by(ClinicalReferenceDocument.id.desc())
    if status:
        q = q.where(ClinicalReferenceDocument.status == status)
    return [
        {
            "id": d.id,
            "title": d.title,
            "document_type": d.document_type,
            "status": d.status,
            "version": d.version,
            "description": d.description,
        }
        for d in db.scalars(q).all()
    ]


def document_to_dict(db: Session, doc: ClinicalReferenceDocument) -> dict[str, Any]:
    chunks = db.scalars(
        select(ClinicalReferenceChunk)
        .where(ClinicalReferenceChunk.document_id == doc.id)
        .order_by(ClinicalReferenceChunk.chunk_index)
    ).all()
    return {
        "id": doc.id,
        "title": doc.title,
        "document_type": doc.document_type,
        "status": doc.status,
        "version": doc.version,
        "description": doc.description,
        "chunks": [
            {"id": c.id, "chunk_index": c.chunk_index, "chunk_title": c.chunk_title, "token_estimate": c.token_estimate}
            for c in chunks
        ],
    }
