from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol


from app.config import settings
from app.services.citations import parse_citation_refs
from app.services.text import contains_subjective_marker, extract_numbers, normalize_text, split_paragraphs, split_sentences, tokenize


@dataclass(frozen=True)
class ExtractedClaim:
    original_sentence: str
    atomic_claim: str
    claim_type: str
    citation_refs: list[str]
    paragraph_index: int
    sentence_index: int
    char_start: int
    char_end: int
    check_required: bool
    reason: str


@dataclass(frozen=True)
class EvidenceJudgement:
    relation: str
    relevance_score: float
    entailment_score: float
    numeric_match: bool
    scope_match: bool
    risk_flags: list[str]
    brief_explanation: str


class LLMProvider(Protocol):
    def extract_claims(self, text: str) -> list[ExtractedClaim]:
        ...

    def judge_evidence(self, claim: str, evidence_text: str) -> EvidenceJudgement:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class MockLLMProvider:
    def extract_claims(self, text: str) -> list[ExtractedClaim]:
        claims: list[ExtractedClaim] = []
        cursor = 0
        for paragraph_index, paragraph in enumerate(split_paragraphs(text)):
            paragraph_start = text.find(paragraph, cursor)
            cursor = paragraph_start + len(paragraph)
            for sentence_index, sentence in enumerate(split_sentences(paragraph)):
                local_start = paragraph.find(sentence)
                char_start = max(0, paragraph_start + local_start)
                char_end = char_start + len(sentence)
                clean = _strip_citation_markers(sentence)
                check_required = not contains_subjective_marker(clean)
                claims.append(
                    ExtractedClaim(
                        original_sentence=sentence,
                        atomic_claim=clean,
                        claim_type=_classify_claim(clean),
                        citation_refs=parse_citation_refs(sentence),
                        paragraph_index=paragraph_index,
                        sentence_index=sentence_index,
                        char_start=char_start,
                        char_end=char_end,
                        check_required=check_required,
                        reason="规则抽取：句子包含可核查事实" if check_required else "规则抽取：写作安排或主观表达",
                    )
                )
        return claims

    def judge_evidence(self, claim: str, evidence_text: str) -> EvidenceJudgement:
        claim_numbers = extract_numbers(claim)
        evidence_numbers = extract_numbers(evidence_text)
        numeric_match = not claim_numbers or bool(claim_numbers & evidence_numbers)
        claim_tokens = set(tokenize(claim))
        evidence_tokens = set(tokenize(evidence_text))
        overlap = len(claim_tokens & evidence_tokens) / max(1, len(claim_tokens))
        relevance = min(1.0, overlap)
        entailment = 0.0
        relation = "IRRELEVANT"
        flags: list[str] = []
        if relevance >= 0.42 and numeric_match:
            relation = "SUPPORTS"
            entailment = min(0.86, 0.48 + relevance * 0.42)
        elif relevance >= 0.28:
            relation = "PARTIALLY_SUPPORTS" if numeric_match else "NOT_ENOUGH_INFO"
            entailment = 0.42 if numeric_match else 0.24
            if not numeric_match:
                flags.append("UNSUPPORTED_NUMERIC_VALUE")
        elif relevance >= 0.12:
            relation = "NOT_ENOUGH_INFO"
            entailment = 0.16
        if claim_numbers and not numeric_match and "UNSUPPORTED_NUMERIC_VALUE" not in flags:
            flags.append("UNSUPPORTED_NUMERIC_VALUE")
        return EvidenceJudgement(
            relation=relation,
            relevance_score=round(relevance, 3),
            entailment_score=round(entailment, 3),
            numeric_match=numeric_match,
            scope_match=not _looks_like_consensus(claim) or relation == "SUPPORTS",
            risk_flags=flags,
            brief_explanation=_mock_explanation(relation, numeric_match),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embedding(text, settings.embedding_dimensions) for text in texts]


class OpenAICompatibleProvider(MockLLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM_PROVIDER=openai_compatible")
        self.base_url = settings.openai_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}

    def extract_claims(self, text: str) -> list[ExtractedClaim]:
        prompt = CLAIM_EXTRACTION_PROMPT.replace("{text}", text)
        try:
            parsed = self._chat_json(prompt)
        except Exception:
            return super().extract_claims(text)
        claims: list[ExtractedClaim] = []
        cursor = 0
        for index, item in enumerate(_ensure_list(parsed)):
            sentence = str(item.get("original_sentence") or item.get("atomic_claim") or "").strip()
            atomic = str(item.get("atomic_claim") or sentence).strip()
            if not sentence or not atomic:
                continue
            char_start = text.find(sentence, cursor)
            if char_start < 0:
                char_start = text.find(atomic, cursor)
            if char_start < 0:
                char_start = 0
            char_end = char_start + len(sentence)
            cursor = max(cursor, char_end)
            claims.append(
                ExtractedClaim(
                    original_sentence=sentence,
                    atomic_claim=atomic,
                    claim_type=str(item.get("claim_type") or _classify_claim(atomic)),
                    citation_refs=_ensure_str_list(item.get("citation_refs", [])),
                    paragraph_index=int(item.get("paragraph_index", 0)),
                    sentence_index=int(item.get("sentence_index", index)),
                    char_start=char_start,
                    char_end=char_end,
                    check_required=_as_bool(item.get("check_required", True), default=True),
                    reason=str(item.get("reason") or ""),
                )
            )
        return claims or super().extract_claims(text)

    def judge_evidence(self, claim: str, evidence_text: str) -> EvidenceJudgement:
        prompt = JUDGE_PROMPT.replace("{claim}", claim).replace("{evidence_text}", evidence_text[:3500])
        try:
            item = self._chat_json(prompt)
            return EvidenceJudgement(
                relation=_normalize_relation(item.get("relation", "NOT_ENOUGH_INFO")),
                relevance_score=_as_score(item.get("relevance_score", 0)),
                entailment_score=_as_score(item.get("entailment_score", 0)),
                numeric_match=_as_bool(item.get("numeric_match", False), default=False),
                scope_match=_as_bool(item.get("scope_match", True), default=True),
                risk_flags=_ensure_str_list(item.get("risk_flags", [])),
                brief_explanation=str(item.get("brief_explanation", ""))[:300],
            )
        except Exception:
            return super().judge_evidence(claim, evidence_text)

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            import httpx

            payload: dict[str, Any] = {"model": settings.embedding_model, "input": texts, "dimensions": settings.embedding_dimensions}
            response = httpx.post(f"{self.base_url}/embeddings", headers=self.headers, json=payload, timeout=60)
            if response.status_code >= 400 and "dimensions" in payload:
                payload.pop("dimensions")
                response = httpx.post(f"{self.base_url}/embeddings", headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()["data"]
            vectors = [_resize_vector(item["embedding"], settings.embedding_dimensions) for item in data]
            return vectors
        except Exception:
            return super().embed(texts)

    def _chat_json(self, prompt: str) -> Any:
        import httpx

        base_payload = {
            "model": settings.openai_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You are a strict academic fact-checking component. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
        }
        payloads = [
            {**base_payload, "response_format": {"type": "json_object"}},
            base_payload,
        ]
        last_error: Exception | None = None
        for payload in payloads:
            for _ in range(2):
                try:
                    response = httpx.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload, timeout=90)
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    return _parse_json(content)
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if "response_format" in payload and exc.response.status_code in {400, 422}:
                        break
                except Exception as exc:
                    last_error = exc
        raise RuntimeError(f"LLM JSON parsing failed: {last_error}")


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "openai_compatible" and settings.openai_api_key:
        return OpenAICompatibleProvider()
    return MockLLMProvider()


def _strip_citation_markers(sentence: str) -> str:
    sentence = re.sub(r"\[\d+(?:\s*[-,]\s*\d+)*\]", "", sentence)
    return normalize_text(sentence.strip(" 。.;；"))


def _classify_claim(text: str) -> str:
    lower = text.lower()
    if contains_subjective_marker(text):
        return "NON_CHECKABLE"
    if extract_numbers(text):
        return "NUMERIC"
    if any(marker in text for marker in ["提出", "构建", "设计"]) or "proposed" in lower:
        return "METHOD"
    if any(marker in text for marker in ["表明", "发现", "证明", "结果"]) or any(word in lower for word in ["shows", "found", "demonstrates"]):
        return "RESULT"
    if any(marker in text for marker in ["优于", "高于", "低于", "相比"]) or any(word in lower for word in ["better", "higher", "lower", "outperform"]):
        return "COMPARATIVE"
    if any(marker in text for marker in ["导致", "影响", "促进"]) or "causes" in lower:
        return "CAUSAL"
    if _looks_like_consensus(text):
        return "CONSENSUS"
    return "BACKGROUND"


def _looks_like_consensus(text: str) -> bool:
    lower = text.lower()
    return any(marker in text for marker in ["广泛", "普遍", "大量研究", "现有研究"]) or any(word in lower for word in ["widely", "consensus", "many studies"])


def _mock_explanation(relation: str, numeric_match: bool) -> str:
    if relation == "SUPPORTS":
        return "证据与声称主题和关键信息高度重合。"
    if relation == "PARTIALLY_SUPPORTS":
        return "证据覆盖部分声称，但范围或细节仍需人工核对。"
    if relation == "NOT_ENOUGH_INFO" and not numeric_match:
        return "证据相关但未出现声称中的关键数值。"
    if relation == "NOT_ENOUGH_INFO":
        return "证据相关性有限，不足以支持或反驳该声称。"
    return "证据与声称主题重合度较低。"


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1 if digest[4] % 2 == 0 else -1
        vector[index] += sign * (1.0 + min(len(token), 12) / 12)
    norm = sum(v * v for v in vector) ** 0.5
    if norm:
        vector = [v / norm for v in vector]
    return vector


def _resize_vector(vector: list[float], dimensions: int) -> list[float]:
    if len(vector) == dimensions:
        return vector
    if len(vector) > dimensions:
        resized = vector[:dimensions]
    else:
        resized = vector + [0.0] * (dimensions - len(vector))
    norm = sum(v * v for v in resized) ** 0.5
    return [v / norm for v in resized] if norm else resized


def _parse_json(content: str) -> Any:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", content, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(1))
    if isinstance(parsed, dict) and "claims" in parsed:
        return parsed["claims"]
    if isinstance(parsed, dict) and "result" in parsed:
        return parsed["result"]
    return parsed


def _ensure_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []
def _normalize_relation(value: Any) -> str:
    relation = str(value or "NOT_ENOUGH_INFO").strip().upper()
    aliases = {
        "SUPPORT": "SUPPORTS",
        "SUPPORTED": "SUPPORTS",
        "PARTIAL": "PARTIALLY_SUPPORTS",
        "PARTIALLY_SUPPORTED": "PARTIALLY_SUPPORTS",
        "REFUTED": "REFUTES",
        "REFUTE": "REFUTES",
        "INSUFFICIENT_EVIDENCE": "NOT_ENOUGH_INFO",
        "NOT_ENOUGH": "NOT_ENOUGH_INFO",
        "NOT ENOUGH INFO": "NOT_ENOUGH_INFO",
    }
    normalized = aliases.get(relation, relation)
    if normalized not in {"SUPPORTS", "PARTIALLY_SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO", "IRRELEVANT"}:
        return "NOT_ENOUGH_INFO"
    return normalized


def _as_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "是"}:
            return True
        if lowered in {"false", "0", "no", "n", "否"}:
            return False
    return default


def _ensure_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


CLAIM_EXTRACTION_PROMPT = """
你是论文事实核查系统中的声称抽取器。
从文本中抽取可被证据验证的最小事实声称。

规则：
1. 只抽取原文已经表达的内容。
2. 一句话中多个事实必须拆成多条。
3. 保留 original_sentence、citation_refs、check_required。
4. 主观评价、写作安排标记为 NON_CHECKABLE。
5. 输出 JSON 对象：{"claims": [...]}。

字段：
atomic_claim, original_sentence, claim_type, citation_refs, paragraph_index, sentence_index, check_required, reason。

文本：
{text}
"""

JUDGE_PROMPT = """
你是论文事实核查系统中的证据判定器。你只能根据 Evidence 判断 Claim。

Claim:
{claim}

Evidence:
{evidence_text}

输出严格 JSON：
{
  "relation": "SUPPORTS|PARTIALLY_SUPPORTS|REFUTES|NOT_ENOUGH_INFO|IRRELEVANT",
  "relevance_score": 0.0,
  "entailment_score": 0.0,
  "numeric_match": true,
  "scope_match": true,
  "risk_flags": [],
  "brief_explanation": "不超过 80 字"
}
"""
