"""Parse PDF / DOCX / plain text into clean, page-anchored chunks.

The chunker is page-aware so RAG citations can reference real page numbers.
For Arabic + English mixed documents we rely on the underlying parser's
RTL handling and post-process via `arabic_reshaper` for display only — the
indexed text is the raw character stream.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pdfplumber
import tiktoken
from docx import Document as DocxDocument

from app.core.logging import get_logger

log = get_logger(__name__)

# A "soft" chunk size — actual size depends on token count.
DEFAULT_CHUNK_TOKENS = 600
DEFAULT_OVERLAP_TOKENS = 80

_encoder = tiktoken.get_encoding("cl100k_base")


@dataclass
class ParsedChunk:
    text: str
    page_number: int | None
    chunk_index: int
    token_count: int


# ----- Parsing ----------------------------------------------------------------


def _sanitize(text: str) -> str:
    """Clean up two problems Postgres + retrieval choke on:

    1. NUL bytes — psycopg rejects \\x00 in text columns. Sources: PDF fonts
       that use glyph-index encoding, OCR rebuilds with invisible text layers.
    2. Arabic presentation forms — when we render OCR text into a PDF using
       arial.ttf and re-extract via pdfplumber, base letters come back as
       presentation forms (U+FB50–FEFF). NFKC normalizes them back so the
       embedding model and trigram search both work against canonical
       letters ("نظام" not "ﻥﻅﺍﻡ").
    """
    if not text:
        return text
    import unicodedata
    cleaned = text.replace("\x00", "")
    return unicodedata.normalize("NFKC", cleaned)


def parse_pdf(data: bytes) -> list[tuple[int, str]]:
    """Return [(page_number, text), ...].

    Uses PyMuPDF (fitz) — NOT pdfplumber — because pdfplumber returns Arabic
    text in visual (right-to-left display) order, reversing every word
    character-by-character. PyMuPDF's `get_text("text")` returns logical
    (Unicode) order, which is what the embedding model and trigram search
    need.

    pdfplumber kept as a fallback for the rare case PyMuPDF chokes.
    """
    import fitz  # PyMuPDF

    pages: list[tuple[int, str]] = []
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                pages.append((i, _sanitize(text)))
        return pages
    except Exception as exc:  # noqa: BLE001
        log.warning("pymupdf_parse_failed_falling_back_to_pdfplumber", error=str(exc))
        pages = []
        with pdfplumber.open(BytesIO(data)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append((i, _sanitize(text)))
        return pages


def parse_docx(data: bytes) -> list[tuple[int, str]]:
    """DOCX has no real page numbers — treat the whole doc as page 1."""
    doc = DocxDocument(BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(1, _sanitize(text))]


def parse_text(data: bytes, encoding: str = "utf-8") -> list[tuple[int, str]]:
    return [(1, _sanitize(data.decode(encoding, errors="replace")))]


def parse(data: bytes, mime_type: str) -> list[tuple[int, str]]:
    if mime_type == "application/pdf":
        return parse_pdf(data)
    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return parse_docx(data)
    if mime_type.startswith("text/"):
        return parse_text(data)
    log.warning("unknown_mime_type", mime_type=mime_type)
    return parse_text(data)


# ----- Chunking ---------------------------------------------------------------


def _token_chunks(text: str, max_tokens: int, overlap: int) -> list[str]:
    if not text.strip():
        return []
    tokens = _encoder.encode(text)
    chunks: list[str] = []
    i = 0
    while i < len(tokens):
        window = tokens[i : i + max_tokens]
        chunks.append(_encoder.decode(window))
        if i + max_tokens >= len(tokens):
            break
        i += max_tokens - overlap
    return chunks


def chunk_pages(
    pages: list[tuple[int, str]],
    max_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap: int = DEFAULT_OVERLAP_TOKENS,
) -> list[ParsedChunk]:
    out: list[ParsedChunk] = []
    idx = 0
    for page_number, text in pages:
        for piece in _token_chunks(text, max_tokens, overlap):
            out.append(
                ParsedChunk(
                    text=piece,
                    page_number=page_number,
                    chunk_index=idx,
                    token_count=len(_encoder.encode(piece)),
                )
            )
            idx += 1
    return out


def count_tokens(text: str) -> int:
    return len(_encoder.encode(text))
