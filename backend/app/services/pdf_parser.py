from __future__ import annotations

import re
from pathlib import Path

import fitz
import pdfplumber

from app.services.chunking import PageText
from app.services.text import normalize_text


def extract_pdf_pages(path: str | Path) -> list[PageText]:
    pdf_path = Path(path)
    pages = _extract_with_pymupdf(pdf_path)
    if not any(page.text.strip() for page in pages):
        pages = _extract_with_pdfplumber(pdf_path)
    if not pages:
        raise ValueError("PDF parsed successfully but no text was extracted")
    return pages


def extract_metadata_from_pages(pages: list[PageText], fallback_title: str) -> tuple[str, list[str], int | None, float]:
    first_text = pages[0].text if pages else ""
    lines = [normalize_text(line) for line in first_text.splitlines() if normalize_text(line)]
    title = fallback_title
    confidence = 0.25
    if lines:
        title_candidates = [line for line in lines[:8] if len(line) > 12]
        if title_candidates:
            title = max(title_candidates[:3], key=len)[:300]
            confidence = 0.55
    year_match = re.search(r"\b(19|20)\d{2}\b", first_text)
    year = int(year_match.group(0)) if year_match else None
    authors: list[str] = []
    if len(lines) > 1:
        author_line = lines[1]
        if len(author_line) < 180 and not re.search(r"abstract|摘要|introduction", author_line, re.I):
            authors = [part.strip() for part in re.split(r"[,，;；]| and ", author_line) if part.strip()][:8]
    return title, authors, year, confidence


def _extract_with_pymupdf(path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            pages.append(PageText(page=index, text=page.get_text("text") or ""))
    return pages


def _extract_with_pdfplumber(path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            pages.append(PageText(page=index, text=page.extract_text() or ""))
    return pages

