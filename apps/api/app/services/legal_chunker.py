"""Article-aware chunker for Saudi legal texts.

Saudi nizam (نظام) and lawai'h (لائحة) almost always follow the same
structure:

    الباب الأول    Part I
      الفصل الأول   Chapter 1
        المادة (1)  Article 1
          ...text...
        المادة (2)  Article 2
          ...text...

A naïve token-window chunker shreds this structure: an article gets split
across two chunks, citations point at "page 12" instead of "Article 75 of
the Labor Law", and the retriever's relevance signal weakens.

This module produces one chunk per article (or per article-part for very
long articles), with the article number, heading, and full section path
preserved on each row. Plain-text inputs that don't match the pattern fall
through to ordinary token-window chunking so non-articulated docs still
work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.core.logging import get_logger
from app.services.document_processor import (
    DEFAULT_CHUNK_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    ParsedChunk,
    _encoder,
    _token_chunks,
)

log = get_logger(__name__)

# Cap an article chunk at this many tokens. Most Saudi articles fit easily;
# very long ones (e.g. articles enumerating dozens of clauses) get split into
# parts, each tagged with the same article_number so retrieval still scores
# them together.
MAX_ARTICLE_TOKENS = 1500


# -----------------------------------------------------------------------------
# Patterns
# -----------------------------------------------------------------------------
#
# Arabic:
#   "المادة (75)", "مادة 75:", "المادة الأولى", "المادة 75 -"
# English:
#   "Article 75", "Article 75.", "Article (75)"
#
# We only capture numeric / clearly-identifiable tokens. Non-numeric Arabic
# ordinals ("المادة الأولى") get matched but the captured number is the
# whole word — the retriever still indexes them, just with a less-clean id.

_AR_ARTICLE = re.compile(
    r"(?:^|\n)\s*(?:ال)?مادة\s*[\(\[]?\s*([0-9٠-٩۰-۹]+(?:\s*/\s*[0-9٠-٩۰-۹]+)?|[ء-ي]+)\s*[\)\]]?\s*[\:\-\.]?",
    re.UNICODE,
)
_EN_ARTICLE = re.compile(
    r"(?:^|\n)\s*Article\s*[\(\[]?\s*(\d+(?:[A-Za-z]|/\d+)?)\s*[\)\]]?\s*[\:\-\.]?",
    re.IGNORECASE,
)

# Headings (chapter / part). We capture the whole line as `heading` so the
# UI can show the original phrasing. The `section_path` keys are stable
# regardless of language.
_HEADINGS = [
    # Arabic part / chapter / section
    ("part", re.compile(r"(?:^|\n)\s*(الباب\s+[^\n]{1,80})", re.UNICODE)),
    ("chapter", re.compile(r"(?:^|\n)\s*(الفصل\s+[^\n]{1,80})", re.UNICODE)),
    ("section", re.compile(r"(?:^|\n)\s*(القسم\s+[^\n]{1,80})", re.UNICODE)),
    # English equivalents
    ("part", re.compile(r"(?:^|\n)\s*(Part\s+[IVXLC0-9]+(?:[\s\-:][^\n]{0,80})?)", re.IGNORECASE)),
    ("chapter", re.compile(r"(?:^|\n)\s*(Chapter\s+[IVXLC0-9]+(?:[\s\-:][^\n]{0,80})?)", re.IGNORECASE)),
    ("section", re.compile(r"(?:^|\n)\s*(Section\s+\d+(?:[\s\-:][^\n]{0,80})?)", re.IGNORECASE)),
]


# Eastern-Arabic and Persian-Arabic digits → ASCII digits, so article numbers
# normalize to "75" regardless of how the PDF rendered them.
_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


def normalize_article_number(raw: str) -> str:
    return raw.strip().translate(_DIGIT_TRANSLATION)


# -----------------------------------------------------------------------------
# Chunk type
# -----------------------------------------------------------------------------


@dataclass
class LegalChunk:
    text: str
    page_number: int | None
    chunk_index: int
    token_count: int
    article_number: str | None = None
    heading: str | None = None
    section_path: dict = field(default_factory=dict)

    def to_token_tuple(self) -> tuple[int, int | None, str, int]:
        """Compatibility tuple for the existing index_document_chunks signature."""
        return (self.chunk_index, self.page_number, self.text, self.token_count)


# -----------------------------------------------------------------------------
# Header detection on each page
# -----------------------------------------------------------------------------


def _scan_headings(text: str, current: dict) -> dict:
    """Return a fresh section_path with any heading found in `text` applied
    on top of `current`. Mutates nothing."""
    out = dict(current)
    for level, pattern in _HEADINGS:
        m = pattern.search(text)
        if m:
            out[level] = m.group(1).strip()
            # When a higher level changes, lower levels reset — a new "Part"
            # implies the previous chapter no longer applies.
            order = ["part", "chapter", "section"]
            try:
                idx = order.index(level)
                for lower in order[idx + 1 :]:
                    out.pop(lower, None)
            except ValueError:
                pass
    return out


def _latest_heading(section_path: dict) -> str | None:
    for level in ("section", "chapter", "part"):
        v = section_path.get(level)
        if v:
            return v
    return None


# -----------------------------------------------------------------------------
# Article splitting per page
# -----------------------------------------------------------------------------


@dataclass
class _ArticleSpan:
    article_number: str | None
    text: str


def _split_into_articles(page_text: str, language: str) -> list[_ArticleSpan]:
    """Walk the page text and split on article boundaries.

    Returns a list of (article_number, span_text) — span_text is the body
    starting at the article marker up to the next marker. Text before the
    first marker is returned with article_number=None so it isn't lost.
    """
    pattern = _EN_ARTICLE if language == "en" else _AR_ARTICLE
    matches = list(pattern.finditer(page_text))
    if not matches:
        return [_ArticleSpan(article_number=None, text=page_text)]

    spans: list[_ArticleSpan] = []
    # Preamble (text before the first article marker on this page).
    first_start = matches[0].start()
    if first_start > 0 and page_text[:first_start].strip():
        spans.append(_ArticleSpan(article_number=None, text=page_text[:first_start]))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(page_text)
        body = page_text[start:end].rstrip()
        article_no = normalize_article_number(m.group(1))
        spans.append(_ArticleSpan(article_number=article_no, text=body))

    return spans


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------


def chunk_legal_pages(
    pages: list[tuple[int, str]],
    *,
    language: str = "ar",
    max_tokens: int = MAX_ARTICLE_TOKENS,
    fallback_chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    fallback_overlap: int = DEFAULT_OVERLAP_TOKENS,
) -> list[LegalChunk]:
    """Article-aware chunker.

    Tries to split on article boundaries; falls back to ordinary token-window
    chunking when no articles are found in the document. Every chunk carries
    the closest preceding heading and the full section_path captured up to
    that point.
    """
    section_path: dict = {}
    chunks: list[LegalChunk] = []
    idx = 0

    has_any_article = False
    for _, page_text in pages:
        if (_AR_ARTICLE if language != "en" else _EN_ARTICLE).search(page_text or ""):
            has_any_article = True
            break

    for page_number, page_text in pages:
        if not page_text or not page_text.strip():
            continue
        section_path = _scan_headings(page_text, section_path)
        heading = _latest_heading(section_path)

        if not has_any_article:
            # Plain doc — fall back to token-window chunks, preserving
            # whatever heading we've seen so far.
            for piece in _token_chunks(
                page_text, fallback_chunk_tokens, fallback_overlap
            ):
                chunks.append(
                    LegalChunk(
                        text=piece,
                        page_number=page_number,
                        chunk_index=idx,
                        token_count=len(_encoder.encode(piece)),
                        article_number=None,
                        heading=heading,
                        section_path=dict(section_path),
                    )
                )
                idx += 1
            continue

        # Articulated doc — split each page on article markers.
        for span in _split_into_articles(page_text, language=language):
            body = span.text.strip()
            if not body:
                continue
            tokens = _encoder.encode(body)
            if len(tokens) <= max_tokens:
                chunks.append(
                    LegalChunk(
                        text=body,
                        page_number=page_number,
                        chunk_index=idx,
                        token_count=len(tokens),
                        article_number=span.article_number,
                        heading=heading,
                        section_path=dict(section_path),
                    )
                )
                idx += 1
                continue

            # Long article — split into parts. Each part keeps the same
            # article_number so retrieval scores them together.
            for part_idx, piece in enumerate(
                _token_chunks(body, max_tokens, fallback_overlap), start=1
            ):
                part_path = dict(section_path)
                part_path["article_part"] = str(part_idx)
                chunks.append(
                    LegalChunk(
                        text=piece,
                        page_number=page_number,
                        chunk_index=idx,
                        token_count=len(_encoder.encode(piece)),
                        article_number=span.article_number,
                        heading=heading,
                        section_path=part_path,
                    )
                )
                idx += 1

    return chunks


def detect_language(pages: list[tuple[int, str]]) -> str:
    """Crude language guess: if any of the first few pages contain Arabic
    block characters, treat the doc as Arabic."""
    sample = "\n".join(t for _, t in pages[:3] if t)
    for ch in sample:
        if "؀" <= ch <= "ۿ":
            return "ar"
    return "en"


# Compatibility helper for the old ParsedChunk-shaped consumers.
def to_parsed_chunks(chunks: Iterable[LegalChunk]) -> list[ParsedChunk]:
    return [
        ParsedChunk(
            text=c.text,
            page_number=c.page_number,
            chunk_index=c.chunk_index,
            token_count=c.token_count,
        )
        for c in chunks
    ]
