"""Unit tests for the subdomain core (validator + extractor)."""
from __future__ import annotations

import pytest

from app.core.subdomains import (
    RESERVED_SUBDOMAINS,
    ValidationError,
    ValidationOk,
    extract_subdomain,
    normalize_subdomain,
    validate_subdomain,
)


# ----- normalize ------------------------------------------------------------


def test_normalize_lowercases_and_strips():
    assert normalize_subdomain("  Foo  ") == "foo"
    assert normalize_subdomain("ACME-CO") == "acme-co"
    assert normalize_subdomain("") == ""


# ----- validate -------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "acme",
        "acme-firm",
        "abc",
        "law-office-1",
        "a1b2c3",
        "firm-007",
    ],
)
def test_validate_accepts_good(value):
    assert isinstance(validate_subdomain(value), ValidationOk)


@pytest.mark.parametrize(
    "value,code",
    [
        ("", "empty"),
        ("ab", "too_short"),
        ("a" * 41, "too_long"),
        ("-bad", "invalid_chars"),  # leading hyphen
        ("bad-", "invalid_chars"),  # trailing hyphen
        ("has space", "invalid_chars"),
        ("under_score", "invalid_chars"),
        ("acme--firm", "double_hyphen"),
        ("api", "reserved"),
        ("admin", "reserved"),
        ("login", "reserved"),
        ("dashboard", "reserved"),
    ],
)
def test_validate_rejects(value, code):
    result = validate_subdomain(value)
    assert isinstance(result, ValidationError)
    assert result.code == code


def test_validate_normalizes_uppercase():
    """The validator lowercases before checking so users can type freely.
    The router stores the normalized form, never the raw input."""
    result = validate_subdomain("ACME-Firm")
    assert isinstance(result, ValidationOk)


def test_reserved_list_is_locked_down():
    """Trip the test if anyone removes a critical reserved word."""
    must_keep = {"api", "www", "admin", "dashboard", "login", "auth", "platform"}
    assert must_keep.issubset(RESERVED_SUBDOMAINS)


# ----- extract --------------------------------------------------------------


def test_extract_typical_subdomain():
    assert extract_subdomain("acme.legalai.sa", "legalai.sa") == "acme"


def test_extract_strips_port():
    assert extract_subdomain("acme.legalai.sa:8000", "legalai.sa") == "acme"


def test_extract_returns_none_for_apex():
    assert extract_subdomain("legalai.sa", "legalai.sa") is None


def test_extract_returns_none_for_www():
    assert extract_subdomain("www.legalai.sa", "legalai.sa") is None


def test_extract_returns_none_for_api():
    assert extract_subdomain("api.legalai.sa", "legalai.sa") is None


def test_extract_returns_none_for_localhost():
    assert extract_subdomain("localhost:3030", "legalai.sa") is None


def test_extract_returns_none_for_empty_inputs():
    assert extract_subdomain("", "legalai.sa") is None
    assert extract_subdomain("acme.legalai.sa", "") is None
    assert extract_subdomain(None, "legalai.sa") is None


def test_extract_rejects_multilevel_subdomain():
    """Multi-level subdomains aren't supported yet — return None so they
    don't masquerade as `staging` (or accidentally hit a tenant called
    `staging`)."""
    assert extract_subdomain("acme.staging.legalai.sa", "legalai.sa") is None


def test_extract_is_case_insensitive():
    assert extract_subdomain("ACME.legalai.sa", "legalai.sa") == "acme"
    assert extract_subdomain("acme.LegalAI.sa", "legalai.sa") == "acme"


def test_extract_rejects_close_match():
    """`legalai-sa.com` shares characters but isn't a subdomain of `legalai.sa`."""
    assert extract_subdomain("acme.legalai-sa.com", "legalai.sa") is None
