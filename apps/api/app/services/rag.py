"""Retrieval-Augmented Generation pipeline.

Steps:
  1. Embed the user query.
  2. Hybrid retrieve: cosine over `document_chunks.embedding` + trigram over
     `content` for keyword recall (especially helpful for Arabic legal terms).
  3. Re-rank by combined score, with optional same-domain boost.
  4. Build a grounded answer with inline `[#N]` citation markers, then map them
     to chunk metadata for the response payload.

Cross-tenant safety:
  - Query is always scoped to `tenant_id`.
  - Global / platform corpus is owned by a special `platform` tenant; the
    retrieve step optionally fans out to BOTH the caller's tenant AND the
    platform tenant so lawyers always have access to base Saudi laws.

Legal-corpus features:
  - Optional `domain` filter narrows results to one LegalDomain.
  - Citations carry article_number, heading, authority, decree_number when
    available so the agent can answer "Article 75 of the Labor Law (M/51)"
    instead of just "page 12".
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable
from uuid import UUID

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Document, DocumentChunk, LegalDomain
from app.models.document import HAS_PGVECTOR
from app.services.embeddings import get_embeddings_provider
from app.services.llm import get_llm_provider
from app.services.prompts import legal_rag_system, legal_rag_user_prompt

log = get_logger(__name__)

# Tunable knobs
TOP_K_VECTOR = 12
TOP_K_KEYWORD = 8
TOP_K_FINAL = 6
COSINE_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
# Bonus added to a chunk's score when its legal_domain matches the
# auto-classified or explicit query domain. Soft signal: domain-matched
# chunks float to the top, but mismatched chunks still rank if they have
# very high cosine/trigram scores.
DOMAIN_MATCH_BOOST = 0.15


# =============================================================================
# Query → LegalDomain classifier (cheap, keyword-driven, AR + EN)
# =============================================================================

# Order matters when a query mentions multiple domains: more specific keywords
# (e.g. "termination" → LABOR) should appear before generic ones. The first
# match wins.
_DOMAIN_KEYWORDS: list[tuple[LegalDomain, list[str]]] = [
    (
        LegalDomain.LABOR,
        [
            # Arabic
            "نظام العمل", "عقد عمل", "إنهاء عقد", "إنهاء", "إشعار", "أجر",
            "راتب", "إجازة", "ساعات العمل", "مكافأة نهاية الخدمة", "العمالة",
            "صاحب العمل", "العامل", "فصل تعسفي", "استقالة", "تجربة",
            # English
            "labor", "labour", "employment", "wage", "salary", "termination",
            "notice period", "notice", "resignation", "end of service",
            "leave", "working hours", "employer", "employee", "probation",
        ],
    ),
    (
        LegalDomain.COMMERCIAL,
        [
            "نظام المحكمة التجارية", "الشركات التجارية", "السجل التجاري",
            "العقود التجارية", "المنافسة", "الإفلاس",
            "commercial", "trade", "company", "merchant", "competition",
            "bankruptcy", "insolvency",
        ],
    ),
    (
        LegalDomain.FAMILY,
        [
            "نظام الأحوال الشخصية", "الزواج", "الطلاق", "النفقة", "الحضانة", "الميراث",
            "personal status", "family", "marriage", "divorce", "custody",
            "alimony", "inheritance",
        ],
    ),
    (
        LegalDomain.CRIMINAL,
        [
            "نظام الإجراءات الجزائية", "جزائي", "جريمة", "عقوبة", "سجن",
            "criminal", "penal", "crime", "offence", "imprisonment", "sentence",
        ],
    ),
    (
        LegalDomain.REAL_ESTATE,
        [
            "نظام التسجيل العيني", "العقار", "ملكية", "إيجار", "تطوير عقاري",
            "real estate", "property", "lease", "rent", "ownership", "land",
        ],
    ),
    (
        LegalDomain.INTELLECTUAL_PROPERTY,
        [
            "براءة اختراع", "العلامة التجارية", "حقوق المؤلف", "ملكية فكرية",
            "patent", "trademark", "copyright", "intellectual property",
        ],
    ),
    (
        LegalDomain.CORPORATE,
        [
            "نظام الشركات", "شركة مساهمة", "الشركة المساهمة",
            "شركة ذات مسؤولية محدودة", "تأسيس شركة", "حوكمة", "مجلس إدارة",
            "corporate", "joint stock", "llc", "governance", "board of directors",
            "incorporate", "incorporation",
        ],
    ),
    (
        LegalDomain.BANKING,
        [
            "البنك", "البنك المركزي", "ساما", "تمويل", "قرض", "مرابحة",
            "banking", "bank", "sama", "finance", "loan", "murabaha",
        ],
    ),
    (
        LegalDomain.ADMINISTRATIVE,
        [
            "ديوان المظالم", "إداري", "عقد إداري", "موظف عام",
            "administrative", "diwan", "public servant", "government contract",
        ],
    ),
]


def classify_query_domain(query: str) -> LegalDomain | None:
    """Best-effort guess of the legal domain a query is about.

    Pure keyword match — no LLM call, runs in microseconds. Returns None when
    no keywords hit, in which case the retriever skips domain filtering.
    """
    if not query:
        return None
    q = query.lower()
    for domain, keywords in _DOMAIN_KEYWORDS:
        for kw in keywords:
            if kw.lower() in q:
                return domain
    return None


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    title: str
    page_number: int | None
    content: str
    score: float
    # Legal-corpus extras. Empty/None when the chunk is from a non-legal
    # document (e.g. a contract upload) — the retrieve path stays generic.
    legal_domain: str | None = None
    article_number: str | None = None
    heading: str | None = None
    section_path: dict | None = None
    authority: str | None = None
    decree_number: str | None = None
    enacted_at: str | None = None

    def citation_label(self) -> str:
        """Human-readable label for use in answer citations.

        Examples:
          - "المادة 75 — نظام العمل (M/51)"
          - "Article 12 — Companies Law"
          - "Labor Law, page 14" (when the chunk has no article_number)
        """
        bits: list[str] = []
        if self.article_number:
            bits.append(
                f"المادة {self.article_number}"
                if self.article_number.isdigit()
                else f"Article {self.article_number}"
            )
        bits.append(self.title)
        if self.decree_number:
            bits.append(f"({self.decree_number})")
        if not self.article_number and self.page_number:
            bits.append(f"p. {self.page_number}")
        return " — ".join(b for b in bits if b)


@dataclass
class RagAnswer:
    answer: str
    citations: list[dict]
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


# -----------------------------------------------------------------------------


def retrieve(
    db: Session,
    *,
    query: str,
    tenant_id: UUID,
    platform_tenant_id: UUID | None = None,
    case_id: UUID | None = None,
    top_k: int = TOP_K_FINAL,
    domain: LegalDomain | str | None = None,
    auto_classify_domain: bool = True,
) -> list[RetrievedChunk]:
    """Hybrid (vector + trigram) retrieval over the firm + platform corpus.

    Domain handling:
      - If `domain` is given, applied as a SOFT BOOST during merge (matched
        chunks rise; non-matched still rank if they're highly relevant).
        Chunks with `legal_domain IS NULL` are always eligible because most
        tenant uploads (contracts, evidence) won't be tagged.
      - If `domain` is None and `auto_classify_domain` is True, the keyword
        classifier guesses one from the query.
    """
    tenant_scope = [tenant_id]
    if platform_tenant_id and platform_tenant_id != tenant_id:
        tenant_scope.append(platform_tenant_id)

    # Resolve / normalize domain.
    if isinstance(domain, str):
        try:
            domain = LegalDomain(domain)
        except ValueError:
            domain = None
    if domain is None and auto_classify_domain:
        domain = classify_query_domain(query)
    domain_value = domain.value if isinstance(domain, LegalDomain) else None

    # Columns we always want back from each chunk + parent doc.
    SELECT_COLUMNS = (
        DocumentChunk.id,
        DocumentChunk.document_id,
        DocumentChunk.page_number,
        DocumentChunk.content,
        DocumentChunk.legal_domain,
        DocumentChunk.article_number,
        DocumentChunk.heading,
        DocumentChunk.section_path,
        Document.title,
        Document.authority,
        Document.decree_number,
        Document.enacted_at,
    )

    vec_rows: list = []

    if HAS_PGVECTOR:
        # --- Vector search (cosine distance via pgvector) ---------------------
        embedder = get_embeddings_provider()
        [query_embedding] = embedder.embed([query])

        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        vec_stmt = (
            select(*SELECT_COLUMNS, (1 - distance).label("score"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.tenant_id.in_(tenant_scope))
            .where(DocumentChunk.embedding.is_not(None))
        )
        if case_id is not None:
            vec_stmt = vec_stmt.where(
                (Document.case_id == case_id) | (Document.case_id.is_(None))
            )
        vec_stmt = vec_stmt.order_by(distance).limit(TOP_K_VECTOR)
        vec_rows = list(db.execute(vec_stmt).all())
    else:
        log.info("rag_keyword_only_fallback", reason="pgvector unavailable")

    # --- Keyword search (trigram) --------------------------------------------
    similarity = func.similarity(DocumentChunk.content, query)
    kw_stmt = (
        select(*SELECT_COLUMNS, similarity.label("score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.tenant_id.in_(tenant_scope))
        .where(similarity > 0.05)
    )
    if case_id is not None:
        kw_stmt = kw_stmt.where(
            (Document.case_id == case_id) | (Document.case_id.is_(None))
        )
    kw_stmt = kw_stmt.order_by(similarity.desc()).limit(TOP_K_KEYWORD)

    kw_rows = db.execute(kw_stmt).all()

    # --- Merge + rerank ------------------------------------------------------
    merged: dict[UUID, RetrievedChunk] = {}

    def _row_to_chunk(row, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            title=row.title,
            page_number=row.page_number,
            content=row.content,
            score=score,
            legal_domain=row.legal_domain,
            article_number=row.article_number,
            heading=row.heading,
            section_path=dict(row.section_path) if row.section_path else None,
            authority=row.authority,
            decree_number=row.decree_number,
            enacted_at=row.enacted_at.isoformat() if row.enacted_at else None,
        )

    for row in vec_rows:
        merged[row.id] = _row_to_chunk(row, COSINE_WEIGHT * float(row.score))
    for row in kw_rows:
        if row.id in merged:
            merged[row.id].score += KEYWORD_WEIGHT * float(row.score)
        else:
            merged[row.id] = _row_to_chunk(row, KEYWORD_WEIGHT * float(row.score))

    if domain_value:
        for chunk in merged.values():
            if chunk.legal_domain == domain_value:
                chunk.score += DOMAIN_MATCH_BOOST

    ranked = sorted(merged.values(), key=lambda r: r.score, reverse=True)[:top_k]
    log.info(
        "rag_retrieve",
        chunks=len(ranked),
        domain=domain_value,
        auto_classified=domain_value is not None and domain is not None,
    )
    return ranked


def answer(
    db: Session,
    *,
    query: str,
    tenant_id: UUID,
    platform_tenant_id: UUID | None = None,
    case_id: UUID | None = None,
    locale: str = "ar",
    history: list[dict[str, str]] | None = None,
) -> RagAnswer:
    started = perf_counter()
    chunks = retrieve(
        db,
        query=query,
        tenant_id=tenant_id,
        platform_tenant_id=platform_tenant_id,
        case_id=case_id,
    )

    chunk_payload = [
        {
            "title": c.title,
            "page_number": c.page_number,
            "content": c.content,
            "article_number": c.article_number,
            "heading": c.heading,
            "authority": c.authority,
            "decree_number": c.decree_number,
        }
        for c in chunks
    ]

    messages: list[dict[str, str]] = [
        {"role": "system", "content": legal_rag_system(locale)},
    ]
    if history:
        messages.extend(history[-8:])  # keep recent turns only
    messages.append(
        {"role": "user", "content": legal_rag_user_prompt(query, chunk_payload, locale)}
    )

    llm = get_llm_provider()
    resp = llm.chat(messages)

    citations = [
        {
            "document_id": str(c.document_id),
            "chunk_id": str(c.chunk_id),
            "title": c.title,
            "page_number": c.page_number,
            "snippet": c.content[:300],
            "score": round(float(c.score), 4),
            "legal_domain": c.legal_domain,
            "article_number": c.article_number,
            "heading": c.heading,
            "authority": c.authority,
            "decree_number": c.decree_number,
            "label": c.citation_label(),
        }
        for c in chunks
    ]

    latency_ms = int((perf_counter() - started) * 1000)
    log.info(
        "rag_answer",
        tenant_id=str(tenant_id),
        chunks=len(chunks),
        latency_ms=latency_ms,
    )

    return RagAnswer(
        answer=resp.content,
        citations=citations,
        model=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        latency_ms=latency_ms,
    )


# -----------------------------------------------------------------------------
# Indexing entry point — used by the document-ingestion Celery task.
# -----------------------------------------------------------------------------


def index_document_chunks(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
    chunks: Iterable,
    legal_domain: LegalDomain | str | None = None,
) -> int:
    """Insert chunks + their embeddings into the database.

    `chunks` accepts either:
      - the legacy tuple shape (chunk_index, page_number, content, token_count) — used by
        non-legal uploads (contracts, evidence files), or
      - LegalChunk-shaped objects (with .article_number, .heading, .section_path).
    Returns the number of chunks indexed. The optional `legal_domain` is
    stamped on every chunk so retrieval can filter without a join.
    """
    materialized = list(chunks)
    if not materialized:
        return 0

    if isinstance(legal_domain, str):
        try:
            legal_domain = LegalDomain(legal_domain)
        except ValueError:
            legal_domain = None
    domain_value = legal_domain.value if isinstance(legal_domain, LegalDomain) else None

    # Normalize each entry to a dict so the rest of the function is shape-agnostic.
    normalized: list[dict] = []
    for entry in materialized:
        if isinstance(entry, tuple):
            idx, page, content, tokens = entry
            normalized.append(
                {
                    "chunk_index": idx,
                    "page_number": page,
                    "content": content,
                    "token_count": tokens,
                    "article_number": None,
                    "heading": None,
                    "section_path": {},
                }
            )
        else:
            # LegalChunk or anything else with the right attributes.
            normalized.append(
                {
                    "chunk_index": entry.chunk_index,
                    "page_number": entry.page_number,
                    "content": entry.text,
                    "token_count": entry.token_count,
                    "article_number": getattr(entry, "article_number", None),
                    "heading": getattr(entry, "heading", None),
                    "section_path": getattr(entry, "section_path", {}) or {},
                }
            )

    embedder = get_embeddings_provider()
    vectors = embedder.embed([n["content"] for n in normalized])

    rows = []
    for chunk_data, vec in zip(normalized, vectors, strict=True):
        rows.append(
            DocumentChunk(
                tenant_id=tenant_id,
                document_id=document_id,
                chunk_index=chunk_data["chunk_index"],
                page_number=chunk_data["page_number"],
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                embedding=vec,
                legal_domain=domain_value,
                article_number=chunk_data["article_number"],
                heading=chunk_data["heading"],
                section_path=chunk_data["section_path"],
            )
        )

    db.add_all(rows)
    db.commit()
    return len(rows)
