from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services.llm import LLMProvider
from app.services.text import cosine_similarity, extract_numbers, keyword_score


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    retrieval_score: float
    rerank_score: float
    source_priority: str


def retrieve_chunks(
    db: Session,
    project_id: UUID,
    claim_text: str,
    provider: LLMProvider,
    citation_document_ids: set[UUID] | None = None,
    top_k: int = 12,
    top_n: int = 5,
) -> list[RetrievedChunk]:
    query_vector = provider.embed([claim_text])[0]
    query_numbers = extract_numbers(claim_text)
    chunks = (
        db.query(DocumentChunk)
        .join(DocumentChunk.document)
        .filter(Document.project_id == project_id, Document.parse_status == "completed")
        .all()
    )
    ranked: list[RetrievedChunk] = []
    for chunk in chunks:
        keyword = keyword_score(claim_text, chunk.chunk_text)
        semantic = cosine_similarity(query_vector, list(chunk.embedding or []))
        metadata = 0.0
        priority = "project_library"
        if citation_document_ids and chunk.document_id in citation_document_ids:
            metadata = 1.0
            priority = "cited_document"
        numeric_bonus = 0.08 if query_numbers and query_numbers & extract_numbers(chunk.chunk_text) else 0.0
        retrieval_score = min(1.0, 0.45 * keyword + 0.45 * semantic + 0.10 * metadata + numeric_bonus)
        rerank_score = min(1.0, retrieval_score + (0.06 if priority == "cited_document" else 0))
        ranked.append(
            RetrievedChunk(
                chunk=chunk,
                retrieval_score=round(retrieval_score, 4),
                rerank_score=round(rerank_score, 4),
                source_priority=priority,
            )
        )
    ranked.sort(key=lambda item: item.rerank_score, reverse=True)
    return ranked[: max(top_n, min(top_k, len(ranked)))]


