from __future__ import annotations

from dataclasses import dataclass

from app.services.text import count_tokens, normalize_text


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True)
class Chunk:
    page_start: int
    page_end: int
    text: str
    token_count: int
    chunk_type: str = "body"
    section_title: str | None = None


def chunk_pages(pages: list[PageText], target_tokens: int = 260, overlap_tokens: int = 45) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[str] = []
    page_start = 1
    page_end = 1
    token_total = 0

    for page in pages:
        paragraphs = [p.strip() for p in page.text.split("\n") if p.strip()]
        for paragraph in paragraphs:
            paragraph = normalize_text(paragraph)
            paragraph_tokens = count_tokens(paragraph)
            if not buffer:
                page_start = page.page
            if token_total + paragraph_tokens > target_tokens and buffer:
                chunk_text = " ".join(buffer)
                chunks.append(Chunk(page_start=page_start, page_end=page_end, text=chunk_text, token_count=count_tokens(chunk_text)))
                overlap = _last_words(chunk_text, overlap_tokens)
                buffer = [overlap] if overlap else []
                token_total = count_tokens(overlap)
                page_start = page.page if not overlap else page_start
            buffer.append(paragraph)
            page_end = page.page
            token_total += paragraph_tokens

    if buffer:
        chunk_text = " ".join(buffer)
        chunks.append(Chunk(page_start=page_start, page_end=page_end, text=chunk_text, token_count=count_tokens(chunk_text)))

    return chunks


def _last_words(text: str, size: int) -> str:
    words = text.split()
    if len(words) <= size:
        return text
    return " ".join(words[-size:])

