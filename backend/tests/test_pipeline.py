from __future__ import annotations

from app.services.citations import parse_citation_refs
from app.services.chunking import PageText, chunk_pages
from app.services.llm import MockLLMProvider
from app.services.openalex import OpenAlexWork, abstract_from_inverted_index, build_openalex_evidence_text
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


def test_openalex_abstract_inverted_index_is_restored() -> None:
    assert abstract_from_inverted_index({"sleep": [0], "improves": [1], "memory": [2]}) == "sleep improves memory"


def test_openalex_evidence_text_keeps_traceable_metadata() -> None:
    text = build_openalex_evidence_text(
        OpenAlexWork(
            openalex_id="https://openalex.org/W123",
            title="Sleep and memory",
            authors=["A. Zhang"],
            year=2024,
            doi="10.1234/example",
            source_name="Example Journal",
            landing_page_url="https://doi.org/10.1234/example",
            abstract="Sleep improved vocabulary recall.",
            cited_by_count=8,
        )
    )

    assert "Title: Sleep and memory" in text
    assert "DOI: 10.1234/example" in text
    assert "Abstract: Sleep improved vocabulary recall." in text
