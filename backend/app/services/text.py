from __future__ import annotations

import math
import re
from collections import Counter

SENTENCE_RE = re.compile(r"[^。！？!?;\n]+[。！？!?;]?")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+|\d+(?:\.\d+)?%?|[\u4e00-\u9fff]")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences(paragraph: str) -> list[str]:
    return [normalize_text(match.group(0)) for match in SENTENCE_RE.finditer(paragraph) if normalize_text(match.group(0))]


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def extract_numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(text))


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(size))
    left_norm = math.sqrt(sum(v * v for v in left[:size]))
    right_norm = math.sqrt(sum(v * v for v in right[:size]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def keyword_score(query: str, document: str) -> float:
    query_terms = tokenize(query)
    document_terms = tokenize(document)
    if not query_terms or not document_terms:
        return 0.0
    doc_counts = Counter(document_terms)
    overlap = sum(min(doc_counts[term], 3) for term in set(query_terms))
    return min(1.0, overlap / max(1, len(set(query_terms))))


def contains_subjective_marker(text: str) -> bool:
    markers = ["本文将", "本文旨在", "我们将", "值得注意", "重要意义", "未来", "建议", "可能有助于"]
    lower = text.lower()
    return any(marker in text for marker in markers) or "we will" in lower or "this paper will" in lower

