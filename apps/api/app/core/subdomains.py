"""Subdomain handling — extract, validate, reserved-words list.

Each subscribed tenant gets `<subdomain>.<base_domain>`. The base domain is
configured via the `BASE_DOMAIN` env var (e.g. `legalai.sa`). Local dev runs
on `localhost:3030` where there's no real DNS; the resolver tolerates that
and skips subdomain handling.

Validation rules (kept tight so we don't have to revisit):
  - 3-40 chars
  - lowercase a-z, 0-9, hyphen
  - must start and end with alphanumeric
  - cannot contain consecutive hyphens
  - must not be in the reserved list

Reserved list covers operational subdomains (`api`, `www`, …), social /
brand-confusable strings (`admin`, `dashboard`, …), and common phishing
bait (`login`, `auth`, …). Add to this list as the product grows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Tighter than the wider DNS spec (which allows 63 chars) — 40 is plenty
# for a firm name and gives us headroom for subdomain prefixes if we ever
# need one (e.g. `acme.staging.legalai.sa`).
_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$")
_DOUBLE_HYPHEN = re.compile(r"--")

MIN_LEN = 3
MAX_LEN = 40

# Reserved subdomains — never claimable by tenants. Sorted alphabetically
# for easy grepping; categories noted inline.
RESERVED_SUBDOMAINS: frozenset[str] = frozenset(
    {
        # Operational / infra
        "api", "app", "auth", "cdn", "docs", "ftp", "health", "metrics",
        "static", "assets", "mail", "smtp", "imap", "pop", "ns", "ns1", "ns2",
        # Branded / platform
        "admin", "dashboard", "platform", "system", "internal", "private",
        # Marketing / public
        "www", "blog", "news", "press", "marketing", "landing", "pricing",
        "about", "contact", "support", "help", "faq", "status", "careers",
        # Auth-flow phishing-bait
        "login", "signup", "register", "reset", "verify", "oauth", "sso", "id",
        # Locales / ops
        "ar", "en", "us", "uk", "sa", "test", "staging", "dev", "prod",
        "demo", "sandbox", "beta", "alpha", "preview",
        # Content
        "doc", "wiki", "kb",
    }
)


@dataclass
class ValidationError:
    code: str
    message: str


@dataclass
class ValidationOk:
    pass


def validate_subdomain(value: str) -> ValidationError | ValidationOk:
    """Return ValidationOk on success, ValidationError otherwise.

    Distinct error codes so the frontend can show friendly localized
    messages without parsing English strings.
    """
    if not value:
        return ValidationError("empty", "Subdomain is required.")
    s = value.strip().lower()
    if len(s) < MIN_LEN:
        return ValidationError(
            "too_short", f"Subdomain must be at least {MIN_LEN} characters."
        )
    if len(s) > MAX_LEN:
        return ValidationError(
            "too_long", f"Subdomain must be at most {MAX_LEN} characters."
        )
    if not _PATTERN.match(s):
        return ValidationError(
            "invalid_chars",
            "Subdomain may only contain lowercase letters, digits, and hyphens, "
            "and must start and end with a letter or digit.",
        )
    if _DOUBLE_HYPHEN.search(s):
        return ValidationError(
            "double_hyphen", "Subdomain cannot contain consecutive hyphens."
        )
    if s in RESERVED_SUBDOMAINS:
        return ValidationError("reserved", "This subdomain is reserved.")
    return ValidationOk()


def extract_subdomain(host: str | None, base_domain: str) -> str | None:
    """Return the leading label of `host` if it lies under `base_domain`.

    Returns None when:
      - host is empty or doesn't include base_domain
      - host *is* the base domain (`legalai.sa`)
      - host's only label is `www` (or anything in the reserved list)

    Examples:
      extract_subdomain("acme.legalai.sa", "legalai.sa")  → "acme"
      extract_subdomain("legalai.sa", "legalai.sa")        → None
      extract_subdomain("www.legalai.sa", "legalai.sa")    → None
      extract_subdomain("api.legalai.sa", "legalai.sa")    → None
      extract_subdomain("localhost:3030", "legalai.sa")    → None
    """
    if not host or not base_domain:
        return None
    # Strip port (`acme.legalai.sa:8000` → `acme.legalai.sa`)
    h = host.split(":", 1)[0].lower().strip(".")
    base = base_domain.split(":", 1)[0].lower().strip(".")
    if not h or not base:
        return None
    if h == base:
        return None
    if not h.endswith("." + base):
        return None
    leading = h[: -(len(base) + 1)]
    if not leading:
        return None
    # Subdomain must be a single label — multi-level subdomains
    # (`acme.staging.legalai.sa`) are not currently supported.
    if "." in leading:
        return None
    if leading in RESERVED_SUBDOMAINS:
        return None
    return leading


def normalize_subdomain(value: str) -> str:
    """Lowercase + strip. Used everywhere the subdomain crosses the API edge."""
    return (value or "").strip().lower()
