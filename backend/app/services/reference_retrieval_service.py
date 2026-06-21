"""Retrieve reference chunks — keyword fallback when embeddings unavailable."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_reference import AiRetrievalLog, ClinicalReferenceChunk, ClinicalReferenceDocument


def _score_chunk(query: str, chunk_text: str) -> float:
    q_tokens = set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
    if not q_tokens:
        return 0.0
    text_lower = chunk_text.lower()
    hits = sum(1 for t in q_tokens if t in text_lower)
    return hits / len(q_tokens)


def retrieve_reference_chunks(
    db: Session,
    *,
    query: str,
    role: str,
    case_id: int | None,
    user_id: int,
    top_k: int = 5,
    document_type: str | None = None,
) -> list[dict[str, Any]]:
    q = (
        select(ClinicalReferenceChunk, ClinicalReferenceDocument)
        .join(ClinicalReferenceDocument, ClinicalReferenceChunk.document_id == ClinicalReferenceDocument.id)
        .where(ClinicalReferenceDocument.status == "active")
    )
    if document_type:
        q = q.where(ClinicalReferenceDocument.document_type == document_type)

    rows = db.execute(q).all()
    scored: list[tuple[float, ClinicalReferenceChunk, ClinicalReferenceDocument]] = []
    for chunk, doc in rows:
        score = _score_chunk(query, chunk.chunk_text)
        if score > 0:
            scored.append((score, chunk, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict[str, Any]] = []
    chunk_ids: list[int] = []
    scores: dict[str, float] = {}
    for score, chunk, doc in scored[:top_k]:
        chunk_ids.append(chunk.id)
        scores[str(chunk.id)] = score
        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "chunk_title": chunk.chunk_title or doc.title,
                "chunk_text": chunk.chunk_text[:800],
                "document_type": doc.document_type,
                "score": score,
            }
        )

    log = AiRetrievalLog(
        case_id=case_id,
        user_id=user_id,
        query=query[:500],
        role=role,
        retrieved_chunk_ids_json=json.dumps(chunk_ids),
        retrieval_scores_json=json.dumps(scores),
    )
    db.add(log)
    db.commit()
    return results


def retrieve_strategy_references(db: Session, goal_summary: str, user_id: int, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve_reference_chunks(
        db,
        query=goal_summary,
        role="therapist",
        case_id=None,
        user_id=user_id,
        top_k=top_k,
        document_type="strategy_pool",
    )


def retrieve_goal_references(db: Session, goal_domain: str, user_id: int, top_k: int = 5) -> list[dict[str, Any]]:
    return retrieve_reference_chunks(
        db,
        query=goal_domain,
        role="therapist",
        case_id=None,
        user_id=user_id,
        top_k=top_k,
        document_type="goal_pool",
    )


def retrieve_safety_rules(db: Session, output_type: str, user_id: int) -> list[dict[str, Any]]:
    return retrieve_reference_chunks(
        db,
        query=f"neuro-affirmative safety {output_type}",
        role="system",
        case_id=None,
        user_id=user_id,
        top_k=3,
        document_type="neuroaffirmative_doctrine",
    )
