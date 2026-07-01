from __future__ import annotations

import uuid

from app.models import Evidence
from app.services.llm import MockLLMProvider
from app.services.verifier import aggregate_verdict


def _evidence(
    document_id: uuid.UUID,
    relation: str,
    relevance: float = 0.75,
    entailment: float = 0.75,
    flags: list[str] | None = None,
) -> Evidence:
    return Evidence(
        id=uuid.uuid4(),
        claim_id=uuid.uuid4(),
        document_id=document_id,
        chunk_id=uuid.uuid4(),
        evidence_text="中文 gold case 证据片段",
        page_start=1,
        page_end=1,
        retrieval_score=0.8,
        rerank_score=0.8,
        relation=relation,
        relevance_score=relevance,
        entailment_score=entailment,
        numeric_match="UNSUPPORTED_NUMERIC_VALUE" not in (flags or []),
        risk_flags=flags or [],
    )


def test_chinese_supported_gold_case() -> None:
    provider = MockLLMProvider()
    judgement = provider.judge_evidence(
        "睡眠干预组在两周后记忆保持率提高了18%",
        "研究结果显示，睡眠干预组在两周后记忆保持率提高了18%，对照组变化不明显。",
    )
    doc_id = uuid.uuid4()
    evidence = _evidence(doc_id, judgement.relation, judgement.relevance_score, judgement.entailment_score, judgement.risk_flags)

    verdict = aggregate_verdict("NUMERIC", True, [evidence], set())

    assert verdict.verdict == "SUPPORTED"


def test_chinese_numeric_mismatch_gold_case_keeps_numeric_flag() -> None:
    provider = MockLLMProvider()
    judgement = provider.judge_evidence(
        "睡眠干预组在两周后记忆保持率提高了18%",
        "研究结果显示，睡眠干预组在两周后记忆保持率提高了12%，对照组变化不明显。",
    )
    doc_id = uuid.uuid4()
    evidence = _evidence(doc_id, judgement.relation, judgement.relevance_score, judgement.entailment_score, judgement.risk_flags)

    verdict = aggregate_verdict("NUMERIC", True, [evidence], set())

    assert verdict.verdict in {"INSUFFICIENT_EVIDENCE", "PARTIALLY_SUPPORTED"}
    assert "UNSUPPORTED_NUMERIC_VALUE" in verdict.risk_flags


def test_chinese_citation_mismatch_gold_case() -> None:
    cited_doc_id = uuid.uuid4()
    supporting_doc_id = uuid.uuid4()
    cited_evidence = _evidence(cited_doc_id, "IRRELEVANT", relevance=0.1, entailment=0.0)
    other_evidence = _evidence(supporting_doc_id, "SUPPORTS", relevance=0.85, entailment=0.82)

    verdict = aggregate_verdict("BACKGROUND", True, [cited_evidence, other_evidence], {cited_doc_id})

    assert verdict.verdict == "CITATION_MISMATCH"
    assert "UNSUPPORTED_CITATION" in verdict.risk_flags


def test_chinese_overgeneralization_gold_case() -> None:
    doc_id = uuid.uuid4()
    evidence = _evidence(doc_id, "SUPPORTS", relevance=0.82, entailment=0.8)

    verdict = aggregate_verdict("CONSENSUS", True, [evidence], set())

    assert verdict.verdict == "PARTIALLY_SUPPORTED"
    assert "OVERGENERALIZATION_RISK" in verdict.risk_flags


def test_chinese_refuted_gold_case() -> None:
    doc_id = uuid.uuid4()
    evidence = _evidence(doc_id, "REFUTES", relevance=0.9, entailment=0.86, flags=["CONTRADICTED_BY_SOURCE"])

    verdict = aggregate_verdict("RESULT", True, [evidence], set())

    assert verdict.verdict == "REFUTED"
    assert "CONTRADICTED_BY_SOURCE" in verdict.risk_flags


def test_chinese_non_checkable_gold_case() -> None:
    verdict = aggregate_verdict("NON_CHECKABLE", False, [], set())

    assert verdict.verdict == "NOT_VERIFIABLE"