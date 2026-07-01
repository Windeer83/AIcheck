from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    verification_mode: str = "strict_paper"


class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    verification_mode: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VersionRead(BaseModel):
    backend_version: str
    build_sha: str | None
    build_time: str | None
    database_revision: str | None
    environment: str


class DocumentRead(BaseModel):
    id: UUID
    project_id: UUID
    title: str | None
    authors: list[str] | None
    year: int | None
    doi: str | None
    source_type: str
    file_name: str
    parse_status: str
    parse_error: str | None
    metadata_confidence: float
    chunks_count: int = 0
    citation_index: int | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class InputTextCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    raw_text: str = Field(min_length=1)
    section_type: str | None = "related_work"
    citation_style: str | None = "numeric"


class InputTextRead(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    raw_text: str
    section_type: str | None
    citation_style: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerifyRequest(BaseModel):
    mode: str = "strict_paper"
    retrieval_top_k: int = Field(default=12, ge=1, le=50)
    evidence_top_n: int = Field(default=5, ge=1, le=20)
    external_search_enabled: bool = False
    check_citations: bool = True
    check_reference_authenticity: bool = True


class RunLogRead(BaseModel):
    id: UUID
    run_id: UUID
    step: str
    level: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunRead(BaseModel):
    id: UUID
    input_text_id: UUID
    status: str
    progress: float
    current_step: str
    claims_total: int
    claims_checked: int
    config: dict[str, Any] | None
    report_path: str | None
    error: str | None
    logs: list[RunLogRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewUpdate(BaseModel):
    review_status: str = Field(pattern="^(unreviewed|confirmed|suppressed)$")
    review_note: str | None = Field(default=None, max_length=1000)


class EvidenceRead(BaseModel):
    id: UUID
    document_id: UUID
    chunk_id: UUID
    document_title: str | None
    evidence_text: str
    page_start: int
    page_end: int
    retrieval_score: float
    rerank_score: float
    relation: str | None
    relevance_score: float
    entailment_score: float
    numeric_match: bool | None
    explanation: str | None
    risk_flags: list[str] | None


class ClaimResultRead(BaseModel):
    result_id: UUID
    claim_id: UUID
    original_sentence: str
    atomic_claim: str
    claim_type: str
    citation_refs: list[str] | None
    paragraph_index: int
    sentence_index: int
    char_start: int
    char_end: int
    check_required: bool
    verdict: str
    confidence: float
    risk_level: str
    risk_flags: list[str]
    explanation: str | None
    review_status: str
    review_note: str | None
    reviewed_at: datetime | None
    evidences: list[EvidenceRead]


class ResultsSummary(BaseModel):
    total_claims: int
    checked_claims: int
    supported: int
    partially_supported: int
    insufficient_evidence: int
    citation_mismatch: int
    fabricated_reference: int
    refuted: int
    high_risk: int
    critical_risk: int
    suppressed: int


class RunResultsRead(BaseModel):
    summary: ResultsSummary
    claims: list[ClaimResultRead]

