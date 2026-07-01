from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import func, text
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.deps import require_access_token
from app.models import Claim, Document, Evidence, InputText, Project, Run, RunLog, VerificationResult, utcnow
from app.schemas import (
    ClaimResultRead,
    DocumentRead,
    EvidenceRead,
    InputTextCreate,
    InputTextRead,
    ProjectCreate,
    ProjectRead,
    ResultsSummary,
    ReviewUpdate,
    RunLogRead,
    RunRead,
    RunResultsRead,
    VerifyRequest,
    VersionRead,
)
from app.services.report import build_markdown_report
from app.services.storage import storage
from app.tasks import parse_document_task, verify_input_text_task

router = APIRouter(prefix="/api", dependencies=[Depends(require_access_token)])


@router.get("/version", response_model=VersionRead)
def get_version(db: Session = Depends(get_db)) -> VersionRead:
    revision: str | None = None
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    except Exception:
        revision = None
    return VersionRead(
        backend_version="2.0-dev",
        build_sha=_setting_value("git_sha") or _setting_value("build_sha"),
        build_time=_setting_value("build_time"),
        database_revision=revision,
        environment=settings.app_env,
    )


@router.post("/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(name=payload.name, description=payload.description, verification_mode=payload.verification_mode)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("/projects/{project_id}/documents", response_model=DocumentRead)
def upload_document(
    project_id: UUID,
    file: UploadFile = File(...),
    source_type: str = Form("pdf"),
    manual_title: str | None = Form(None),
    manual_doi: str | None = Form(None),
    db: Session = Depends(get_db),
) -> DocumentRead:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "MVP currently supports PDF uploads")
    document = Document(
        project_id=project.id,
        title=manual_title,
        doi=manual_doi,
        source_type=source_type,
        file_path="pending",
        file_name=file.filename,
        parse_status="queued",
    )
    db.add(document)
    db.flush()
    document.file_path = storage.save_upload(project.id, document.id, file)
    db.commit()
    db.refresh(document)
    parse_document_task.delay(str(document.id))
    return _document_read(db, document, _citation_index(db, document))


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
def list_documents(project_id: UUID, db: Session = Depends(get_db)) -> list[DocumentRead]:
    documents = (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.deleted_at.is_(None), Document.source_type != "openalex")
        .order_by(Document.created_at.asc())
        .all()
    )
    citation_index = {document.id: index for index, document in enumerate(documents, start=1)}
    return [_document_read(db, document, citation_index.get(document.id)) for document in reversed(documents)]


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: UUID, db: Session = Depends(get_db)) -> DocumentRead:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(404, "Document not found")
    return _document_read(db, document, _citation_index(db, document))


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: UUID, db: Session = Depends(get_db)) -> Response:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(404, "Document not found")
    document.deleted_at = utcnow()
    document.parse_error = None
    db.commit()
    return Response(status_code=204)


@router.post("/documents/{document_id}/retry", response_model=DocumentRead)
def retry_document_parse(document_id: UUID, db: Session = Depends(get_db)) -> DocumentRead:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(404, "Document not found")
    document.parse_status = "queued"
    document.parse_error = None
    db.commit()
    db.refresh(document)
    parse_document_task.delay(str(document.id))
    return _document_read(db, document, _citation_index(db, document))


@router.post("/projects/{project_id}/input-texts", response_model=InputTextRead)
def create_input_text(project_id: UUID, payload: InputTextCreate, db: Session = Depends(get_db)) -> InputText:
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    input_text = InputText(
        project_id=project_id,
        title=payload.title,
        raw_text=payload.raw_text,
        section_type=payload.section_type,
        citation_style=payload.citation_style,
    )
    db.add(input_text)
    db.commit()
    db.refresh(input_text)
    return input_text


@router.get("/projects/{project_id}/input-texts", response_model=list[InputTextRead])
def list_input_texts(project_id: UUID, db: Session = Depends(get_db)) -> list[InputText]:
    return db.query(InputText).filter(InputText.project_id == project_id).order_by(InputText.created_at.desc()).all()


@router.post("/input-texts/{input_text_id}/verify", response_model=RunRead)
def start_verification(input_text_id: UUID, payload: VerifyRequest, db: Session = Depends(get_db)) -> RunRead:
    input_text = db.get(InputText, input_text_id)
    if not input_text:
        raise HTTPException(404, "Input text not found")
    run = Run(input_text_id=input_text.id, status="queued", progress=0, current_step="queued", config=payload.model_dump())
    db.add(run)
    db.flush()
    db.add(RunLog(run_id=run.id, step="queued", level="info", message="核查任务已创建，等待 Worker 接收任务。"))
    db.commit()
    db.refresh(run)
    verify_input_text_task.delay(str(input_text.id), str(run.id), payload.model_dump())
    return _run_read(db, run)


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> RunRead:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return _run_read(db, run)


@router.get("/runs/{run_id}/results", response_model=RunResultsRead)
def get_results(run_id: UUID, db: Session = Depends(get_db)) -> RunResultsRead:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    claims = (
        db.query(Claim)
        .options(selectinload(Claim.evidences).selectinload(Evidence.document), selectinload(Claim.result))
        .filter(Claim.run_id == run.id)
        .order_by(Claim.paragraph_index, Claim.sentence_index)
        .all()
    )
    claim_results = [_claim_result_read(claim, claim.result) for claim in claims if claim.result]
    return RunResultsRead(summary=_summary(claim_results), claims=claim_results)


@router.patch("/verification-results/{result_id}/review", response_model=ClaimResultRead)
def review_result(result_id: UUID, payload: ReviewUpdate, db: Session = Depends(get_db)) -> ClaimResultRead:
    result = db.get(VerificationResult, result_id)
    if not result:
        raise HTTPException(404, "Verification result not found")
    result.review_status = payload.review_status
    result.review_note = payload.review_note
    result.reviewed_at = utcnow()
    run = db.get(Run, result.run_id)
    if run:
        run.report_path = None
    db.commit()
    db.refresh(result)
    claim = (
        db.query(Claim)
        .options(selectinload(Claim.evidences).selectinload(Evidence.document))
        .filter(Claim.id == result.claim_id)
        .one()
    )
    return _claim_result_read(claim, result)


@router.get("/runs/{run_id}/export")
def export_report(run_id: UUID, format: str = "markdown", db: Session = Depends(get_db)) -> Response:
    if format not in {"markdown", "md"}:
        raise HTTPException(400, "MVP currently supports markdown export")
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.report_path:
        markdown = storage.read_bytes(run.report_path).decode("utf-8")
    else:
        input_text = db.get(InputText, run.input_text_id)
        documents = (
            db.query(Document)
            .filter(Document.project_id == input_text.project_id, Document.deleted_at.is_(None), Document.source_type != "openalex")
            .all()
            if input_text
            else []
        )
        claims = (
            db.query(Claim)
            .options(selectinload(Claim.evidences).selectinload(Evidence.document))
            .filter(Claim.run_id == run.id)
            .all()
        )
        results = db.query(VerificationResult).filter(VerificationResult.run_id == run.id).all()
        markdown = build_markdown_report(run, input_text, documents, claims, results)
    headers = {"Content-Disposition": f'attachment; filename="factcheck_report_{run.id}.md"'}
    return Response(content=markdown, media_type="text/markdown; charset=utf-8", headers=headers)


def _run_read(db: Session, run: Run) -> RunRead:
    logs = db.query(RunLog).filter(RunLog.run_id == run.id).order_by(RunLog.created_at.asc()).all()
    return RunRead(
        id=run.id,
        input_text_id=run.input_text_id,
        status=run.status,
        progress=run.progress,
        current_step=run.current_step,
        claims_total=run.claims_total,
        claims_checked=run.claims_checked,
        config=run.config,
        report_path=run.report_path,
        error=run.error,
        logs=[RunLogRead.model_validate(log, from_attributes=True) for log in logs],
        created_at=run.created_at,
        updated_at=run.updated_at,
    )

def _document_read(db: Session, document: Document, citation_index: int | None = None) -> DocumentRead:
    chunks_count = db.query(func.count()).select_from(Document).join(Document.chunks).filter(Document.id == document.id).scalar() or 0
    return DocumentRead.model_validate(document, from_attributes=True).model_copy(update={"chunks_count": chunks_count, "citation_index": citation_index})


def _citation_index(db: Session, document: Document) -> int | None:
    if document.deleted_at or document.source_type == "openalex":
        return None
    documents = (
        db.query(Document.id)
        .filter(Document.project_id == document.project_id, Document.deleted_at.is_(None), Document.source_type != "openalex")
        .order_by(Document.created_at.asc())
        .all()
    )
    for index, row in enumerate(documents, start=1):
        if row[0] == document.id:
            return index
    return None


def _setting_value(name: str) -> str | None:
    value = getattr(settings, name, None)
    return str(value) if value else None


def _claim_result_read(claim: Claim, result: VerificationResult) -> ClaimResultRead:
    return ClaimResultRead(
        result_id=result.id,
        claim_id=claim.id,
        original_sentence=claim.original_sentence,
        atomic_claim=claim.atomic_claim,
        claim_type=claim.claim_type,
        citation_refs=claim.citation_refs,
        paragraph_index=claim.paragraph_index,
        sentence_index=claim.sentence_index,
        char_start=claim.char_start,
        char_end=claim.char_end,
        check_required=claim.check_required,
        verdict=result.verdict,
        confidence=result.confidence,
        risk_level=result.risk_level,
        risk_flags=result.risk_flags or [],
        explanation=result.explanation,
        review_status=result.review_status,
        review_note=result.review_note,
        reviewed_at=result.reviewed_at,
        evidences=[
            EvidenceRead(
                id=evidence.id,
                document_id=evidence.document_id,
                chunk_id=evidence.chunk_id,
                document_title=evidence.document.title if evidence.document else None,
                source_priority=evidence.source_priority,
                evidence_text=evidence.evidence_text,
                page_start=evidence.page_start,
                page_end=evidence.page_end,
                retrieval_score=evidence.retrieval_score,
                rerank_score=evidence.rerank_score,
                relation=evidence.relation,
                relevance_score=evidence.relevance_score,
                entailment_score=evidence.entailment_score,
                numeric_match=evidence.numeric_match,
                explanation=evidence.explanation,
                risk_flags=evidence.risk_flags,
            )
            for evidence in sorted(claim.evidences, key=lambda item: item.rerank_score, reverse=True)
        ],
    )


def _summary(claims: list[ClaimResultRead]) -> ResultsSummary:
    active_claims = [claim for claim in claims if claim.review_status != "suppressed"]
    return ResultsSummary(
        total_claims=len(claims),
        checked_claims=sum(1 for claim in active_claims if claim.check_required),
        supported=sum(1 for claim in active_claims if claim.verdict == "SUPPORTED"),
        partially_supported=sum(1 for claim in active_claims if claim.verdict == "PARTIALLY_SUPPORTED"),
        insufficient_evidence=sum(1 for claim in active_claims if claim.verdict == "INSUFFICIENT_EVIDENCE"),
        citation_mismatch=sum(1 for claim in active_claims if claim.verdict == "CITATION_MISMATCH"),
        fabricated_reference=sum(1 for claim in active_claims if claim.verdict == "FABRICATED_REFERENCE"),
        refuted=sum(1 for claim in active_claims if claim.verdict == "REFUTED"),
        high_risk=sum(1 for claim in active_claims if claim.risk_level == "high"),
        critical_risk=sum(1 for claim in active_claims if claim.risk_level == "critical"),
        suppressed=sum(1 for claim in claims if claim.review_status == "suppressed"),
    )
