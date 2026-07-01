from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models import CitationBinding, Claim, Document, DocumentChunk, Evidence, InputText, Run, RunLog, VerificationResult
from app.services.chunking import chunk_pages
from app.services.citations import bind_citations
from app.services.llm import get_llm_provider
from app.services.pdf_parser import extract_metadata_from_pages, extract_pdf_pages
from app.services.report import build_markdown_report
from app.services.retrieval import retrieve_chunks
from app.services.storage import storage
from app.services.verifier import aggregate_verdict
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="parse_document")
def parse_document_task(document_id: str) -> None:
    with SessionLocal() as db:
        parse_document(db, UUID(document_id))


@celery_app.task(name="verify_input_text")
def verify_input_text_task(input_text_id: str, run_id: str, options: dict) -> None:
    with SessionLocal() as db:
        verify_input_text(db, UUID(input_text_id), UUID(run_id), options)


def requeue_incomplete_documents() -> int:
    with SessionLocal() as db:
        documents = db.query(Document).filter(Document.parse_status.in_(["queued", "parsing"]), Document.deleted_at.is_(None)).all()
        for document in documents:
            document.parse_status = "queued"
            document.parse_error = None
        db.commit()

        for document in documents:
            parse_document_task.delay(str(document.id))

        if documents:
            logger.info("Requeued %s incomplete document parsing task(s)", len(documents))
        return len(documents)


def parse_document(db: Session, document_id: UUID) -> None:
    provider = get_llm_provider()
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        return
    document.parse_status = "parsing"
    document.parse_error = None
    db.commit()
    try:
        local_path = storage.materialize(document.file_path)
        pages = extract_pdf_pages(local_path)
        title, authors, year, confidence = extract_metadata_from_pages(pages, document.file_name)
        chunks = chunk_pages(pages)
        embeddings = provider.embed([chunk.text for chunk in chunks]) if chunks else []
        document.title = document.title or title
        document.authors = document.authors or authors
        document.year = document.year or year
        document.metadata_confidence = confidence
        document.parse_status = "completed"
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_title=chunk.section_title,
                    chunk_text=chunk.text,
                    chunk_type=chunk.chunk_type,
                    token_count=chunk.token_count,
                    embedding=embedding,
                )
            )
        db.commit()
    except Exception as exc:
        document.parse_status = "failed"
        document.parse_error = str(exc)[:1000]
        db.commit()


def verify_input_text(db: Session, input_text_id: UUID, run_id: UUID, options: dict) -> None:
    provider = get_llm_provider()
    run = db.get(Run, run_id)
    input_text = db.get(InputText, input_text_id)
    if not run or not input_text:
        return
    try:
        _update_run(db, run, "running", 0.05, "extracting_claims", message="Worker 已接收任务，开始抽取可核查声称。")
        db.query(VerificationResult).filter(VerificationResult.run_id == run.id).delete()
        stale_claims = db.query(Claim).filter(Claim.run_id == run.id).all()
        for stale in stale_claims:
            db.delete(stale)
        db.flush()

        extracted = provider.extract_claims(input_text.raw_text)
        claims: list[Claim] = []
        for item in extracted:
            claim = Claim(
                input_text_id=input_text.id,
                run_id=run.id,
                original_sentence=item.original_sentence,
                atomic_claim=item.atomic_claim,
                claim_type=item.claim_type,
                citation_refs=item.citation_refs,
                paragraph_index=item.paragraph_index,
                sentence_index=item.sentence_index,
                char_start=item.char_start,
                char_end=item.char_end,
                check_required=item.check_required,
            )
            db.add(claim)
            claims.append(claim)
        run.claims_total = len(claims)
        checkable = sum(1 for claim in claims if claim.check_required)
        _append_run_log(db, run, "extracting_claims", f"已抽取 {len(claims)} 条声称，其中 {checkable} 条需要核查。")
        db.commit()

        _update_run(db, run, "running", 0.18, "binding_citations", message="开始识别并绑定文本中的引用标记。")
        documents = db.query(Document).filter(Document.project_id == input_text.project_id, Document.parse_status == "completed", Document.deleted_at.is_(None)).all()
        refs = list(dict.fromkeys(ref for claim in claims for ref in (claim.citation_refs or [])))
        db.query(CitationBinding).filter(CitationBinding.input_text_id == input_text.id).delete()
        bindings = bind_citations(input_text.id, refs, documents)
        db.add_all(bindings)
        matched = sum(1 for binding in bindings if binding.document_id)
        _append_run_log(db, run, "binding_citations", f"发现 {len(refs)} 个引用标记，已按当前文献库匹配 {matched} 个。")
        db.commit()
        binding_map = {binding.citation_key: binding.document_id for binding in bindings if binding.document_id}

        top_k = int(options.get("retrieval_top_k") or 12)
        top_n = int(options.get("evidence_top_n") or 5)
        for index, claim in enumerate(claims, start=1):
            progress = 0.18 + 0.72 * ((index - 1) / max(1, len(claims)))
            preview = _preview(claim.atomic_claim)
            _update_run(db, run, "running", progress, "verifying_claims", checked=index - 1, message=f"正在核查第 {index}/{len(claims)} 条：{preview}")
            citation_document_ids = {binding_map[ref] for ref in (claim.citation_refs or []) if ref in binding_map}
            retrieved = []
            if claim.check_required:
                retrieved = retrieve_chunks(
                    db,
                    input_text.project_id,
                    claim.atomic_claim,
                    provider,
                    citation_document_ids=citation_document_ids,
                    top_k=top_k,
                    top_n=top_n,
                )[:top_n]
            else:
                _append_run_log(db, run, "verifying_claims", f"第 {index} 条为不可核查表达，跳过证据检索。")
            evidences: list[Evidence] = []
            for item in retrieved:
                judgement = provider.judge_evidence(claim.atomic_claim, item.chunk.chunk_text)
                evidence = Evidence(
                    claim_id=claim.id,
                    document_id=item.chunk.document_id,
                    chunk_id=item.chunk.id,
                    evidence_text=item.chunk.chunk_text,
                    page_start=item.chunk.page_start,
                    page_end=item.chunk.page_end,
                    retrieval_score=item.retrieval_score,
                    rerank_score=item.rerank_score,
                    source_priority=item.source_priority,
                    relation=judgement.relation,
                    relevance_score=judgement.relevance_score,
                    entailment_score=judgement.entailment_score,
                    numeric_match=judgement.numeric_match,
                    explanation=judgement.brief_explanation,
                    risk_flags=judgement.risk_flags,
                )
                db.add(evidence)
                evidences.append(evidence)
            db.flush()
            aggregate = aggregate_verdict(claim.claim_type, claim.check_required, evidences, citation_document_ids)
            db.add(
                VerificationResult(
                    claim_id=claim.id,
                    run_id=run.id,
                    verdict=aggregate.verdict,
                    confidence=aggregate.confidence,
                    risk_level=aggregate.risk_level,
                    risk_flags=aggregate.risk_flags,
                    explanation=aggregate.explanation,
                    best_evidence_ids=aggregate.best_evidence_ids,
                )
            )
            run.claims_checked = index
            _append_run_log(
                db,
                run,
                "verifying_claims",
                f"第 {index}/{len(claims)} 条完成：{aggregate.verdict}，可信度 {aggregate.confidence:.1f}，证据 {len(evidences)} 条。",
            )
            db.commit()

        _update_run(db, run, "running", 0.94, "generating_report", checked=len(claims), message="所有声称核查完成，正在生成 Markdown 报告。")
        claims_with_evidence = (
            db.query(Claim)
            .options(selectinload(Claim.evidences).selectinload(Evidence.document))
            .filter(Claim.run_id == run.id)
            .all()
        )
        results = db.query(VerificationResult).filter(VerificationResult.run_id == run.id).all()
        markdown = build_markdown_report(run, input_text, documents, claims_with_evidence, results)
        run.report_path = storage.write_report(run.id, markdown)
        _update_run(db, run, "completed", 1.0, "completed", checked=len(claims), message="核查完成，报告已生成。")
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)[:1000]
        run.current_step = "failed"
        _append_run_log(db, run, "failed", f"核查失败：{run.error}", level="error")
        db.commit()


def _update_run(
    db: Session,
    run: Run,
    status: str,
    progress: float,
    step: str,
    checked: int | None = None,
    message: str | None = None,
) -> None:
    run.status = status
    run.progress = round(progress, 3)
    run.current_step = step
    if checked is not None:
        run.claims_checked = checked
    if message:
        _append_run_log(db, run, step, message)
    db.commit()


def _append_run_log(db: Session, run: Run, step: str, message: str, level: str = "info") -> None:
    db.add(RunLog(run_id=run.id, step=step, message=message[:1000], level=level))


def _preview(text: str, limit: int = 72) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."