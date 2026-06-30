from __future__ import annotations

import re
from uuid import UUID

from app.models import CitationBinding, Document

NUMERIC_CITATION_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")
AUTHOR_YEAR_RE = re.compile(r"([A-Z][A-Za-z-]+|[\u4e00-\u9fff]{2,4})(?:\s+et\s+al\.)?[,，\s]*[（(](\d{4})[）)]")


def parse_citation_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in NUMERIC_CITATION_RE.finditer(text):
        refs.extend(_expand_numeric_ref(match.group(1)))
    for author, year in AUTHOR_YEAR_RE.findall(text):
        refs.append(f"{author}{year}")
    return list(dict.fromkeys(refs))


def _expand_numeric_ref(raw: str) -> list[str]:
    refs: list[str] = []
    for part in re.split(r"\s*,\s*", raw):
        if "-" in part:
            start, end = [int(x.strip()) for x in part.split("-", 1)]
            refs.extend(str(i) for i in range(start, end + 1))
        elif part.strip():
            refs.append(part.strip())
    return refs


def bind_citations(input_text_id: UUID, refs: list[str], documents: list[Document]) -> list[CitationBinding]:
    bindings: list[CitationBinding] = []
    ordered_docs = sorted(documents, key=lambda d: d.created_at)
    for ref in refs:
        document: Document | None = None
        confidence = 0.0
        status = "unmatched"
        if ref.isdigit():
            index = int(ref) - 1
            if 0 <= index < len(ordered_docs):
                document = ordered_docs[index]
                confidence = 0.72
                status = "matched_numeric_order"
        else:
            compact = ref.lower()
            for candidate in ordered_docs:
                haystack = " ".join(
                    [
                        candidate.title or "",
                        " ".join(candidate.authors or []),
                        str(candidate.year or ""),
                    ]
                ).lower()
                if compact in haystack.replace(" ", "") or compact[-4:] in haystack:
                    document = candidate
                    confidence = 0.68
                    status = "matched_author_year"
                    break
        bindings.append(
            CitationBinding(
                input_text_id=input_text_id,
                citation_key=ref,
                document_id=document.id if document else None,
                binding_confidence=confidence,
                binding_status=status,
            )
        )
    return bindings

