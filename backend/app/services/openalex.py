from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk
from app.services.llm import LLMProvider

OPENALEX_API_URL = "https://api.openalex.org/works"
OPENALEX_SOURCE_TYPE = "openalex"


@dataclass(frozen=True)
class OpenAlexWork:
    openalex_id: str
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    source_name: str | None
    landing_page_url: str | None
    abstract: str
    cited_by_count: int


def search_openalex_works(query: str, limit: int | None = None) -> list[OpenAlexWork]:
    normalized = " ".join(query.split())
    if not normalized:
        return []

    headers: dict[str, str] = {"User-Agent": _user_agent()}
    if settings.openalex_api_key:
        headers["Authorization"] = f"Bearer {settings.openalex_api_key}"

    params: dict[str, str | int] = {
        "search": normalized[:500],
        "per-page": limit or settings.openalex_per_claim_limit,
        "filter": "has_abstract:true",
        "select": ",".join(
            [
                "id",
                "doi",
                "display_name",
                "publication_year",
                "authorships",
                "abstract_inverted_index",
                "primary_location",
                "open_access",
                "cited_by_count",
            ]
        ),
    }
    if settings.openalex_email:
        params["mailto"] = settings.openalex_email
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key

    response = httpx.get(OPENALEX_API_URL, params=params, headers=headers, timeout=settings.openalex_timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    works: list[OpenAlexWork] = []
    for item in payload.get("results", []):
        work = _work_from_api(item)
        if work:
            works.append(work)
    return works


def ensure_openalex_documents(
    db: Session,
    project_id: UUID,
    works: list[OpenAlexWork],
    provider: LLMProvider,
) -> list[Document]:
    documents: list[Document] = []
    for work in works:
        document = (
            db.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.source_type == OPENALEX_SOURCE_TYPE,
                Document.file_name == work.openalex_id,
                Document.deleted_at.is_(None),
            )
            .one_or_none()
        )
        if not document:
            document = Document(
                project_id=project_id,
                title=work.title,
                authors=work.authors,
                year=work.year,
                doi=work.doi,
                source_type=OPENALEX_SOURCE_TYPE,
                file_path=work.landing_page_url or work.openalex_id,
                file_name=work.openalex_id,
                parse_status="completed",
                metadata_confidence=0.82,
            )
            db.add(document)
            db.flush()
        if not document.chunks:
            evidence_text = build_openalex_evidence_text(work)
            embedding = provider.embed([evidence_text])[0]
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    page_start=1,
                    page_end=1,
                    section_title="OpenAlex metadata and abstract",
                    chunk_text=evidence_text,
                    chunk_type="openalex_abstract",
                    token_count=max(1, len(evidence_text) // 4),
                    embedding=embedding,
                )
            )
            db.flush()
        documents.append(document)
    return documents


def build_openalex_evidence_text(work: OpenAlexWork) -> str:
    parts = [
        f"Title: {work.title}",
        f"Authors: {', '.join(work.authors) if work.authors else 'Unknown'}",
        f"Year: {work.year or 'Unknown'}",
    ]
    if work.doi:
        parts.append(f"DOI: {work.doi}")
    if work.source_name:
        parts.append(f"Source: {work.source_name}")
    if work.landing_page_url:
        parts.append(f"URL: {work.landing_page_url}")
    parts.append(f"Cited by: {work.cited_by_count}")
    parts.append(f"Abstract: {work.abstract}")
    return "\n".join(parts)


def abstract_from_inverted_index(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positioned: list[tuple[int, str]] = []
    for word, positions in index.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned.append((position, str(word)))
    positioned.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned).strip()


def _work_from_api(item: dict[str, Any]) -> OpenAlexWork | None:
    title = str(item.get("display_name") or "").strip()
    abstract = abstract_from_inverted_index(item.get("abstract_inverted_index"))
    openalex_id = str(item.get("id") or "").strip()
    if not openalex_id or not title or not abstract:
        return None

    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    authorships = item.get("authorships") or []
    authors: list[str] = []
    for authorship in authorships[:8]:
        author = (authorship or {}).get("author") or {}
        name = str(author.get("display_name") or "").strip()
        if name:
            authors.append(name)

    return OpenAlexWork(
        openalex_id=openalex_id,
        title=title,
        authors=authors,
        year=_as_int(item.get("publication_year")),
        doi=_clean_doi(item.get("doi")),
        source_name=str(source.get("display_name") or "").strip() or None,
        landing_page_url=str(primary_location.get("landing_page_url") or item.get("doi") or openalex_id).strip(),
        abstract=abstract,
        cited_by_count=_as_int(item.get("cited_by_count")) or 0,
    )


def _clean_doi(value: Any) -> str | None:
    if not value:
        return None
    doi = str(value).strip()
    return doi.removeprefix("https://doi.org/") or None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _user_agent() -> str:
    if settings.openalex_email:
        return f"AIcheck/2.0 ({settings.openalex_email})"
    return "AIcheck/2.0"
