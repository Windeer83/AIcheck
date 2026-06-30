from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models import Evidence


@dataclass(frozen=True)
class AggregatedVerdict:
    verdict: str
    confidence: float
    risk_level: str
    risk_flags: list[str]
    explanation: str
    best_evidence_ids: list[str]


SUPPORT_RELATIONS = {"SUPPORTS"}
PARTIAL_RELATIONS = {"PARTIALLY_SUPPORTS"}
REFUTE_RELATIONS = {"REFUTES"}


def aggregate_verdict(
    claim_type: str,
    check_required: bool,
    evidences: list[Evidence],
    citation_document_ids: set[UUID],
) -> AggregatedVerdict:
    if not check_required or claim_type == "NON_CHECKABLE":
        return AggregatedVerdict("NOT_VERIFIABLE", 92, "low", [], "该句更接近写作安排或主观表达，不进入事实核查。", [])

    if not evidences:
        return AggregatedVerdict("INSUFFICIENT_EVIDENCE", 25, "critical", ["NO_EVIDENCE_FOUND"], "未在项目文献库中找到可用证据。", [])

    cited = [e for e in evidences if e.document_id in citation_document_ids] if citation_document_ids else []
    strong_refute = [e for e in evidences if e.relation in REFUTE_RELATIONS and e.entailment_score >= 0.65]
    if strong_refute:
        return _build("REFUTED", evidences, ["CONTRADICTED_BY_SOURCE"], "检索到与声称方向相反的证据。", penalty=40)

    if citation_document_ids:
        if _has_support(cited):
            return _build("SUPPORTED", cited, [], "指定引用文献能够支撑该声称。")
        if _has_support(evidences):
            return _build("CITATION_MISMATCH", evidences, ["UNSUPPORTED_CITATION"], "其他文献可能支持该声称，但当前引用文献未提供直接证据。", penalty=20)
        if _has_partial(cited):
            return _build("PARTIALLY_SUPPORTED", cited, _risk_flags(cited), "指定引用文献只支持部分内容，建议弱化或补充证据。", penalty=12)
        return _build("INSUFFICIENT_EVIDENCE", evidences, ["UNSUPPORTED_CITATION"], "指定引用文献没有提供足够证据。", penalty=25)

    if _has_support(evidences):
        flags = []
        penalty = 0
        explanation = "项目文献库中存在可追溯证据支持该声称。"
        if claim_type == "CONSENSUS" and _independent_document_count(evidences) < 3:
            flags.append("OVERGENERALIZATION_RISK")
            penalty += 15
            explanation = "证据支持部分表述，但共识性表达缺少多篇独立文献支撑。"
            return _build("PARTIALLY_SUPPORTED", evidences, flags, explanation, penalty=penalty)
        return _build("SUPPORTED", evidences, flags, explanation)

    if _has_partial(evidences):
        return _build("PARTIALLY_SUPPORTED", evidences, _risk_flags(evidences), "证据与声称相关，但对象、范围、数值或强度不完全一致。", penalty=14)

    return _build("INSUFFICIENT_EVIDENCE", evidences, ["NO_EVIDENCE_FOUND"], "检索到的证据相关性不足，不能支持或反驳该声称。", penalty=30)


def _has_support(evidences: list[Evidence]) -> bool:
    return any(e.relation in SUPPORT_RELATIONS and e.entailment_score >= 0.6 and e.relevance_score >= 0.55 for e in evidences)


def _has_partial(evidences: list[Evidence]) -> bool:
    return any(e.relation in PARTIAL_RELATIONS or (e.relevance_score >= 0.35 and e.entailment_score >= 0.25) for e in evidences)


def _independent_document_count(evidences: list[Evidence]) -> int:
    return len({e.document_id for e in evidences if e.relation in SUPPORT_RELATIONS | PARTIAL_RELATIONS})


def _risk_flags(evidences: list[Evidence]) -> list[str]:
    flags: list[str] = []
    for evidence in evidences:
        for flag in evidence.risk_flags or []:
            if flag not in flags:
                flags.append(flag)
    if not flags and evidences:
        flags.append("LOW_RETRIEVAL_CONFIDENCE")
    return flags


def _build(verdict: str, evidences: list[Evidence], flags: list[str], explanation: str, penalty: float = 0) -> AggregatedVerdict:
    best = sorted(evidences, key=lambda e: (e.entailment_score, e.relevance_score, e.rerank_score), reverse=True)[:3]
    relevance = max((e.relevance_score for e in best), default=0) * 100
    entailment = max((e.entailment_score for e in best), default=0) * 100
    source_quality = 82 if best else 35
    consistency = 80 if _independent_document_count(best) > 1 else 58
    metadata = 90 if best and all(e.page_start for e in best) else 65
    if verdict == "SUPPORTED":
        base = 0.30 * relevance + 0.30 * entailment + 0.15 * source_quality + 0.15 * consistency + 0.10 * metadata
    elif verdict == "NOT_VERIFIABLE":
        base = 92
    else:
        base = 0.24 * relevance + 0.24 * entailment + 0.12 * source_quality + 0.12 * consistency + 0.08 * metadata
    if any("UNSUPPORTED_NUMERIC_VALUE" == flag for flag in flags):
        penalty += 25
    confidence = max(0, min(100, round(base - penalty, 1)))
    return AggregatedVerdict(verdict, confidence, _risk_level(confidence), flags, explanation, [str(e.id) for e in best])


def _risk_level(confidence: float) -> str:
    if confidence >= 80:
        return "low"
    if confidence >= 60:
        return "medium"
    if confidence >= 30:
        return "high"
    return "critical"

