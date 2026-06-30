from __future__ import annotations

from app.services.citations import parse_citation_refs
from app.services.chunking import PageText, chunk_pages
from app.services.llm import MockLLMProvider
from app.services.verifier import aggregate_verdict


def test_parse_numeric_citations() -> None:
    assert parse_citation_refs("A 方法已被验证[1, 3-4]。") == ["1", "3", "4"]


def test_chunk_pages_preserves_page_numbers() -> None:
    chunks = chunk_pages([PageText(page=1, text="第一段。\n第二段。"), PageText(page=2, text="第三段。")], target_tokens=6, overlap_tokens=0)
    assert chunks
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 2


def test_mock_claim_extraction_marks_numeric() -> None:
    provider = MockLLMProvider()
    claims = provider.extract_claims("Zhang 等提出的方法将 MAE 降低了 15%[1]。")
    assert claims[0].claim_type == "NUMERIC"
    assert claims[0].citation_refs == ["1"]


def test_aggregate_no_evidence_is_insufficient() -> None:
    verdict = aggregate_verdict("BACKGROUND", True, [], set())
    assert verdict.verdict == "INSUFFICIENT_EVIDENCE"
    assert "NO_EVIDENCE_FOUND" in verdict.risk_flags

