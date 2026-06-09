"""Pure-unit tests — no DB, no Redis, no network."""
from __future__ import annotations

import base64
import json

import pytest

from app.services.auth_tokens import normalize_email, _hash_token
from app.services.invoicing import _q2, build_zatca_qr
from app.services.legal_chunker import (
    chunk_legal_pages,
    detect_language,
    normalize_article_number,
)
from app.services.rag import classify_query_domain
from app.models import LegalDomain


# ----- email normalization --------------------------------------------------


def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Foo@Bar.COM  ") == "foo@bar.com"


def test_normalize_email_handles_empty():
    assert normalize_email("") == ""
    assert normalize_email(None) == ""  # type: ignore[arg-type]


# ----- token hashing --------------------------------------------------------


def test_hash_token_is_deterministic_and_64chars():
    a = _hash_token("secret-value")
    b = _hash_token("secret-value")
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_hash_token_differs_per_input():
    assert _hash_token("a") != _hash_token("b")


# ----- legal chunker --------------------------------------------------------


def test_normalize_article_number_strips_eastern_arabic_digits():
    assert normalize_article_number("٧٥") == "75"
    assert normalize_article_number("75") == "75"


def test_chunk_legal_pages_splits_on_articles():
    pages = [
        (
            1,
            "الفصل الأول\n\nالمادة (1)\nأولى الأحكام.\n\n"
            "المادة (2)\nثاني الأحكام.\n",
        )
    ]
    chunks = chunk_legal_pages(pages, language="ar")
    article_numbers = [c.article_number for c in chunks if c.article_number]
    assert "1" in article_numbers
    assert "2" in article_numbers


def test_chunk_legal_pages_falls_back_when_no_articles():
    pages = [(1, "some plain text without articles.")]
    chunks = chunk_legal_pages(pages, language="en")
    assert len(chunks) >= 1
    assert chunks[0].article_number is None


def test_detect_language_finds_arabic():
    assert detect_language([(1, "نظام العمل المادة الأولى")]) == "ar"
    assert detect_language([(1, "Saudi Labor Law")]) == "en"


# ----- domain classifier ----------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("notice period for termination", LegalDomain.LABOR),
        ("ما هي عقوبة جريمة سرقة؟", LegalDomain.CRIMINAL),
        ("patent infringement claim", LegalDomain.INTELLECTUAL_PROPERTY),
        ("How is alimony calculated?", LegalDomain.FAMILY),
        ("tenant rent eviction", LegalDomain.REAL_ESTATE),
        ("incorporate an LLC in KSA", LegalDomain.CORPORATE),
        ("what's the weather", None),
    ],
)
def test_classify_query_domain(query, expected):
    assert classify_query_domain(query) == expected


# ----- invoicing ------------------------------------------------------------


def test_q2_rounds_half_up():
    assert _q2(1.005) == _q2("1.01")  # half-up, not banker's


def test_zatca_qr_encodes_5_tlv_fields():
    from datetime import datetime, timezone
    from decimal import Decimal

    qr = build_zatca_qr(
        seller_name="Acme",
        seller_vat_number="300000000000003",
        issued_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        total=Decimal("114.99"),
        vat_amount=Decimal("15.00"),
    )
    raw = base64.b64decode(qr)
    # Walk TLV: tag 1, len, value, tag 2, len, value, ... 5 fields total
    cursor = 0
    tags_seen = []
    while cursor < len(raw):
        tag = raw[cursor]
        length = raw[cursor + 1]
        cursor += 2 + length
        tags_seen.append(tag)
    assert tags_seen == [1, 2, 3, 4, 5]
