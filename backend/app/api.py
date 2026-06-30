from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_access_token
from app.models import Claim, Document, Evidence, InputText, Project, Run, VerificationResult
from app.schemas import (
    ClaimResultRead,
    DocumentRead,
    EvidenceRead,
    InputTextCreate,
    InputTextRead,
    ProjectCreate,
    ProjectRead,
    ResultsSummary,
    RunRead,
    RunResultsRead,
    VerifyRequest,
)
from app.services.report import build_markdown_report
from app.services.storage import storage
from app.tasks import parse_document_task, verify_input_text_task

router = APIRouter(prefix="/api", dependencies=[Depends(require_access_token)])


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
    return _document_read(db, document)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
def list_documents(project_id: UUID, db: Session = Depends(get_db)) -> list[DocumentRead]:
    documents = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at.desc()).all()
    return [_document_read(db, document) for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: UUID, db: Session = Depends(get_db)) -> DocumentRead:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return _document_read(db, document)


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
def start_verification(input_text_id: UUID, payload: VerifyRequest, db: Session = Depends(get_db)) -> Run:
    input_text = db.get(InputText, input_text_id)
    if not input_text:
        raise HTTPException(404, "Input text not found")
    run = Run(input_text_id=input_text.id, status="queued", progress=0, current_step="queued", config=payload.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    verify_input_text_task.delay(str(input_text.id), str(run.id), payload.model_dump())
    return run


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


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
    claim_results: list[ClaimResultRead] = []
    for claim in claims:
        result = claim.result
        if not result:
            continue
        claim_results.append(
            ClaimResultRead(
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
                evidences=[
                    EvidenceRead(
                        id=evidence.id,
                        document_id=evidence.document_id,
                        chunk_id=evidence.chunk_id,
                        document_title=evidence.document.title if evidence.document else None,
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
        )
    return RunResultsRead(summary=_summary(claim_results), claims=claim_results)


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
        documents = db.query(Document).filter(Document.project_id == input_text.project_id).all() if input_text else []
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


def _document_read(db: Session, document: Document) -> DocumentRead:
    chunks_count = db.query(func.count()).select_from(Document).join(Document.chunks).filter(Document.id == document.id).scalar() or 0
    return DocumentRead.model_validate(document, from_attributes=True).model_copy(update={"chunks_count": chunks_count})


def _summary(claims: list[ClaimResultRead]) -> ResultsSummary:
    return ResultsSummary(
        total_claims=len(claims),
        checked_claims=sum(1 for claim in claims if claim.check_required),
        supported=sum(1 for claim in claims if claim.verdict == "SUPPORTED"),
        partially_supported=sum(1 for claim in claims if claim.verdict == "PARTIALLY_SUPPORTED"),
        insufficient_evidence=sum(1 for claim in claims if claim.verdict == "INSUFFICIENT_EVIDENCE"),
        citation_mismatch=sum(1 for claim in claims if claim.verdict == "CITATION_MISMATCH"),
        fabricated_reference=sum(1 for claim in claims if claim.verdict == "FABRICATED_REFERENCE"),
        refuted=sum(1 for claim in claims if claim.verdict == "REFUTED"),
        high_risk=sum(1 for claim in claims if claim.risk_level == "high"),
        critical_risk=sum(1 for claim in claims if claim.risk_level == "critical"),
    )

