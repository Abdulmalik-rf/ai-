"""Tool registry for the legal agent loop.

Each tool is one Python function with two extras:

  - a JSONSchema definition (the OpenAI Responses API tool shape) that the
    model sees, and
  - the executor that runs server-side when the model emits a `function_call`.

Tools come in two flavors:

  - LAWYER_TOOLS — exposed by the dashboard agent. Wide CRM access (find /
    create / update clients, cases, draft documents, etc.).
  - INTAKE_TOOLS — exposed by the inbound WhatsApp agent. Customer-service
    + lead-generation surface: answer general questions, capture lead
    details, request a consultation, escalate, remember durable facts.

The intake scope deliberately omits broad CRM mutators (no add_case, no
update_client). The agent is talking to potential customers, not lawyers —
its job is to qualify the prospect and get their info on the lawyer's desk,
not to act as an admin.

Every executor receives a `ToolContext` so it can talk to the database,
attribute writes to the right tenant/conversation, and pass through the
user's locale.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    AgentFact,
    Case,
    CaseStatus,
    Client,
    ClientStatus,
    Conversation,
    LegalDomain,
    Tenant,
    WhatsAppContact,
    WhatsAppEscalation,
)
from app.services.rag import retrieve

log = get_logger(__name__)

MAX_FACTS_PER_TENANT = 25
MAX_FACT_LEN = 200


@dataclass
class ToolContext:
    db: Session
    tenant_id: UUID
    locale: str = "ar"
    # Optional: set when the agent is running on behalf of a WhatsApp client.
    whatsapp_contact_id: UUID | None = None
    conversation_id: UUID | None = None
    # Optional: the platform tenant id, so RAG fans out to the global corpus.
    platform_tenant_id: UUID | None = None


# Each entry: { definition: <Responses-API tool schema>, executor: callable }
_TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def tool(definition: dict) -> Callable:
    """Decorator: register a function as a tool.

    `definition` is the JSONSchema in Responses API shape:
      {"type": "function", "name": "...", "description": "...", "parameters": {...}}
    """

    def _wrap(fn: Callable) -> Callable:
        name = definition["name"]
        _TOOL_REGISTRY[name] = {"definition": definition, "executor": fn}
        return fn

    return _wrap


def get_tools(*, scope: str) -> list[dict]:
    """Returns the tool definitions exposed to the model for a given scope."""
    if scope == "lawyer":
        names = LAWYER_TOOLS
    elif scope == "intake":
        names = INTAKE_TOOLS
    else:
        raise ValueError(f"Unknown tool scope: {scope}")
    return [_TOOL_REGISTRY[n]["definition"] for n in names]


def run_tool(name: str, args: dict, ctx: ToolContext) -> dict:
    """Execute one tool call. Returns the JSON-serializable result.

    Errors are caught and returned as `{"error": "..."}` so the model can see
    them and recover (e.g. ask a clarifying question), instead of bubbling up
    and ending the turn.
    """
    entry = _TOOL_REGISTRY.get(name)
    if entry is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = entry["executor"](ctx, **args)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:  # noqa: BLE001
        log.exception("tool_failed", tool=name)
        return {"error": str(exc)}


# =============================================================================
# Tools — legal research
# =============================================================================


@tool(
    {
        "type": "function",
        "name": "search_legal_db",
        "description": (
            "Search the firm's documents AND the platform's Saudi-law corpus "
            "for passages relevant to a question. Returns ranked excerpts "
            "with article numbers, headings, and decree references when "
            "available — use these to ground every legal claim. "
            "Always pass the most likely `domain` so results filter by "
            "category (labor, commercial, family, criminal, etc.). The "
            "retriever falls back to keyword auto-classification if you "
            "omit it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The legal question or keywords to search for.",
                },
                "domain": {
                    "type": "string",
                    "enum": [d.value for d in LegalDomain],
                    "description": (
                        "Best-guess legal domain. Boosts matching chunks. "
                        "Omit only if you genuinely cannot tell."
                    ),
                },
                "case_id": {
                    "type": "string",
                    "description": (
                        "Optional case UUID. If provided, results are biased "
                        "toward documents attached to that case."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of passages to return. Default 5, max 10.",
                },
            },
            "required": ["query"],
        },
    }
)
def search_legal_db(
    ctx: ToolContext,
    query: str,
    domain: str | None = None,
    case_id: str | None = None,
    top_k: int = 5,
) -> dict:
    top_k = max(1, min(int(top_k or 5), 10))
    chunks = retrieve(
        ctx.db,
        query=query,
        tenant_id=ctx.tenant_id,
        platform_tenant_id=ctx.platform_tenant_id,
        case_id=UUID(case_id) if case_id else None,
        top_k=top_k,
        domain=domain,
    )
    return {
        "domain_used": domain or "(auto)",
        "results": [
            {
                "citation": c.citation_label(),
                "document_id": str(c.document_id),
                "chunk_id": str(c.chunk_id),
                "title": c.title,
                "page_number": c.page_number,
                "article_number": c.article_number,
                "heading": c.heading,
                "legal_domain": c.legal_domain,
                "authority": c.authority,
                "decree_number": c.decree_number,
                "snippet": c.content[:600],
                "score": round(float(c.score), 4),
            }
            for c in chunks
        ],
    }


# =============================================================================
# Tools — CRM clients (lawyer scope)
# =============================================================================


@tool(
    {
        "type": "function",
        "name": "find_client",
        "description": (
            "Find one or more clients by name (partial, case-insensitive), "
            "phone, email, or national ID. Returns up to 10 matches."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    }
)
def find_client(ctx: ToolContext, query: str, limit: int = 10) -> dict:
    limit = max(1, min(int(limit or 10), 25))
    q = f"%{query.lower()}%"
    rows = (
        ctx.db.execute(
            select(Client)
            .where(Client.tenant_id == ctx.tenant_id)
            .where(
                func.lower(Client.name).like(q)
                | func.lower(func.coalesce(Client.email, "")).like(q)
                | func.coalesce(Client.phone, "").like(q)
                | func.coalesce(Client.national_id, "").like(q)
                | func.coalesce(Client.cr_number, "").like(q)
            )
            .order_by(Client.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return {
        "clients": [
            {
                "id": str(c.id),
                "name": c.name,
                "kind": c.kind,
                "phone": c.phone,
                "email": c.email,
                "national_id": c.national_id,
                "cr_number": c.cr_number,
            }
            for c in rows
        ]
    }


@tool(
    {
        "type": "function",
        "name": "add_client",
        "description": (
            "Create a CRM client. Use this when the lawyer dictates new "
            "contact info, or when an inbound WhatsApp client introduces "
            "themselves. Returns the new client id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["person", "company"],
                    "description": "Defaults to 'person'.",
                },
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "national_id": {
                    "type": "string",
                    "description": "Saudi Hawiya for individuals.",
                },
                "cr_number": {
                    "type": "string",
                    "description": "Commercial registration for companies.",
                },
                "address": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
    }
)
def add_client(
    ctx: ToolContext,
    name: str,
    kind: str = "person",
    phone: str | None = None,
    email: str | None = None,
    national_id: str | None = None,
    cr_number: str | None = None,
    address: str | None = None,
    notes: str | None = None,
) -> dict:
    client = Client(
        tenant_id=ctx.tenant_id,
        name=name.strip(),
        kind=kind if kind in ("person", "company") else "person",
        phone=phone,
        email=email,
        national_id=national_id,
        cr_number=cr_number,
        address=address,
        notes=notes,
    )
    ctx.db.add(client)
    ctx.db.commit()
    ctx.db.refresh(client)
    return {"id": str(client.id), "name": client.name, "created": True}


@tool(
    {
        "type": "function",
        "name": "update_client",
        "description": "Update fields on an existing client. Only the provided fields are changed.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "national_id": {"type": "string"},
                "cr_number": {"type": "string"},
                "address": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["id"],
        },
    }
)
def update_client(ctx: ToolContext, id: str, **fields: Any) -> dict:
    client = ctx.db.execute(
        select(Client).where(
            Client.tenant_id == ctx.tenant_id, Client.id == UUID(id)
        )
    ).scalar_one_or_none()
    if client is None:
        return {"error": "Client not found."}
    allowed = {"name", "phone", "email", "national_id", "cr_number", "address", "notes"}
    changed = {k: v for k, v in fields.items() if k in allowed and v is not None}
    for k, v in changed.items():
        setattr(client, k, v)
    ctx.db.commit()
    return {"id": str(client.id), "updated": list(changed.keys())}


# =============================================================================
# Tools — Cases (lawyer scope)
# =============================================================================


@tool(
    {
        "type": "function",
        "name": "find_case",
        "description": "Find legal cases by reference number, title, or client name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": [s.value for s in CaseStatus],
                },
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    }
)
def find_case(
    ctx: ToolContext,
    query: str,
    status: str | None = None,
    limit: int = 10,
) -> dict:
    limit = max(1, min(int(limit or 10), 25))
    q = f"%{query.lower()}%"
    stmt = (
        select(Case, Client)
        .outerjoin(Client, Client.id == Case.client_id)
        .where(Case.tenant_id == ctx.tenant_id)
        .where(
            func.lower(Case.reference).like(q)
            | func.lower(Case.title).like(q)
            | func.lower(func.coalesce(Client.name, "")).like(q)
        )
    )
    if status:
        stmt = stmt.where(Case.status == status)
    stmt = stmt.order_by(Case.created_at.desc()).limit(limit)
    rows = list(ctx.db.execute(stmt).all())
    return {
        "cases": [
            {
                "id": str(case.id),
                "reference": case.reference,
                "title": case.title,
                "status": str(case.status),
                "domain": str(case.domain),
                "client_id": str(case.client_id) if case.client_id else None,
                "client_name": client.name if client else None,
            }
            for case, client in rows
        ]
    }


@tool(
    {
        "type": "function",
        "name": "add_case",
        "description": (
            "Open a new legal case for an existing client. The reference is "
            "generated server-side if you don't supply one."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "client_id": {"type": "string"},
                "domain": {
                    "type": "string",
                    "enum": [d.value for d in LegalDomain],
                },
                "description": {"type": "string"},
                "reference": {
                    "type": "string",
                    "description": "Optional manual reference. Auto-generated otherwise.",
                },
            },
            "required": ["title", "client_id"],
        },
    }
)
def add_case(
    ctx: ToolContext,
    title: str,
    client_id: str,
    domain: str = "other",
    description: str | None = None,
    reference: str | None = None,
) -> dict:
    if reference is None:
        # CASE-YYYY-NNNN where NNNN is the count + 1 within the year.
        year = datetime.now(timezone.utc).year
        existing = ctx.db.execute(
            select(func.count())
            .select_from(Case)
            .where(
                Case.tenant_id == ctx.tenant_id,
                Case.reference.like(f"CASE-{year}-%"),
            )
        ).scalar_one()
        reference = f"CASE-{year}-{int(existing) + 1:04d}"

    try:
        domain_enum = LegalDomain(domain)
    except ValueError:
        domain_enum = LegalDomain.OTHER

    case = Case(
        tenant_id=ctx.tenant_id,
        title=title.strip(),
        client_id=UUID(client_id),
        domain=domain_enum,
        description=description,
        reference=reference,
    )
    ctx.db.add(case)
    ctx.db.commit()
    ctx.db.refresh(case)
    return {
        "id": str(case.id),
        "reference": case.reference,
        "title": case.title,
        "created": True,
    }


# =============================================================================
# Tools — Escalation (client scope)
# =============================================================================


@tool(
    {
        "type": "function",
        "name": "escalate_to_lawyer",
        "description": (
            "Flag the conversation for human review. Use this when: the "
            "question requires actual legal advice, the client asks to speak "
            "to a lawyer, or you can't answer confidently. The lawyer sees "
            "this in their dashboard inbox. After calling this, tell the "
            "client (in their language) that a lawyer will follow up."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "One-line reason for the escalation. Shown to the lawyer.",
                },
            },
            "required": ["reason"],
        },
    }
)
def escalate_to_lawyer(ctx: ToolContext, reason: str) -> dict:
    if ctx.conversation_id is None:
        return {"error": "Cannot escalate: no active conversation."}
    ctx.db.add(
        WhatsAppEscalation(
            tenant_id=ctx.tenant_id,
            conversation_id=ctx.conversation_id,
            reason=reason[:500],
        )
    )
    ctx.db.commit()
    return {"escalated": True}


# =============================================================================
# Tools — Long-term memory (both scopes)
# =============================================================================


@tool(
    {
        "type": "function",
        "name": "remember_fact",
        "description": (
            "Save a short fact (≤15 words) for long-term recall. Stays in the "
            "system prompt forever, so be frugal: only save when the user "
            "explicitly asks ('remember X') OR it's a durable preference "
            "(timezone, language, key contact). Cap is 25 facts per tenant."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "scope": {
                    "type": "string",
                    "enum": ["tenant", "contact"],
                    "description": (
                        "'tenant' (default) = visible across all conversations. "
                        "'contact' = scoped to this WhatsApp contact only."
                    ),
                },
            },
            "required": ["text"],
        },
    }
)
def remember_fact(
    ctx: ToolContext, text: str, scope: str = "tenant"
) -> dict:
    text = text.strip()
    if not text:
        return {"error": "Empty fact."}
    if len(text) > MAX_FACT_LEN:
        return {
            "error": f"Fact too long ({len(text)} chars, max {MAX_FACT_LEN}). Compress first."
        }
    contact_id = ctx.whatsapp_contact_id if scope == "contact" else None

    # Dedupe — exact text, case-insensitive, same scope.
    dup_stmt = (
        select(AgentFact)
        .where(AgentFact.tenant_id == ctx.tenant_id)
        .where(func.lower(AgentFact.text) == text.lower())
    )
    if contact_id is not None:
        dup_stmt = dup_stmt.where(AgentFact.whatsapp_contact_id == contact_id)
    else:
        dup_stmt = dup_stmt.where(AgentFact.whatsapp_contact_id.is_(None))
    if ctx.db.execute(dup_stmt).scalar_one_or_none():
        return {"warning": "already saved"}

    count = ctx.db.execute(
        select(func.count())
        .select_from(AgentFact)
        .where(AgentFact.tenant_id == ctx.tenant_id)
    ).scalar_one()
    if int(count) >= MAX_FACTS_PER_TENANT:
        return {
            "error": (
                f"Memory full ({MAX_FACTS_PER_TENANT} facts). Ask the user "
                "which existing memories to forget_fact(id)."
            )
        }

    fact = AgentFact(
        tenant_id=ctx.tenant_id,
        whatsapp_contact_id=contact_id,
        text=text,
    )
    ctx.db.add(fact)
    ctx.db.commit()
    ctx.db.refresh(fact)
    return {"id": str(fact.id), "saved": True}


@tool(
    {
        "type": "function",
        "name": "forget_fact",
        "description": "Delete a saved fact by id. Use when the user says 'forget X' / 'drop that'.",
        "parameters": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    }
)
def forget_fact(ctx: ToolContext, id: str) -> dict:
    fact = ctx.db.execute(
        select(AgentFact).where(
            AgentFact.tenant_id == ctx.tenant_id, AgentFact.id == UUID(id)
        )
    ).scalar_one_or_none()
    if fact is None:
        return {"error": "Fact not found."}
    ctx.db.delete(fact)
    ctx.db.commit()
    return {"deleted": True}


# =============================================================================
# Tools — Lead intake (intake scope, called over WhatsApp)
# =============================================================================


def _append_dated_note(existing: str | None, line: str) -> str:
    """Prepend a date-stamped line so the running note is newest-first.

    Mirrors the adaa-agent's add_client_note pattern — append-only, no
    overwrites, easy for the lawyer to skim chronologically.
    """
    today = date.today().isoformat()
    entry = f"[{today}] {line.strip()}"
    if existing and existing.strip():
        return entry + "\n" + existing.strip()
    return entry


@tool(
    {
        "type": "function",
        "name": "capture_lead",
        "description": (
            "Save the inbound caller as a NEW lead in the firm's CRM. Use "
            "this once you have at least their name + a one-line description "
            "of their legal matter. Phone is captured automatically from the "
            "WhatsApp sender — do not ask for it. The lead's status is set "
            "to 'lead' so the lawyer's dashboard surfaces them in the new-"
            "leads inbox. After this returns, the WhatsApp contact is auto-"
            "linked to the new client. ONLY CALL ONCE per conversation — if "
            "the contact is already linked, use update_lead_matter instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full name as the lead introduced themselves.",
                },
                "matter_summary": {
                    "type": "string",
                    "description": (
                        "One or two sentences describing what they need help "
                        "with, in their own words where possible."
                    ),
                },
                "domain": {
                    "type": "string",
                    "enum": [d.value for d in LegalDomain],
                    "description": "Best-guess legal domain. Use 'other' if unsure.",
                },
                "kind": {
                    "type": "string",
                    "enum": ["person", "company"],
                    "description": "Defaults to 'person'.",
                },
                "company_name": {
                    "type": "string",
                    "description": (
                        "If they're calling on behalf of a company, capture "
                        "the company name here (use it instead of name)."
                    ),
                },
                "city": {
                    "type": "string",
                    "description": "City in Saudi Arabia. Optional.",
                },
                "email": {"type": "string"},
            },
            "required": ["name", "matter_summary", "domain"],
        },
    }
)
def capture_lead(
    ctx: ToolContext,
    name: str,
    matter_summary: str,
    domain: str,
    kind: str = "person",
    company_name: str | None = None,
    city: str | None = None,
    email: str | None = None,
) -> dict:
    if ctx.whatsapp_contact_id is None:
        return {"error": "Not in a WhatsApp conversation."}
    contact = ctx.db.get(WhatsAppContact, ctx.whatsapp_contact_id)
    if contact is None or contact.tenant_id != ctx.tenant_id:
        return {"error": "WhatsApp contact not found."}

    if contact.client_id is not None:
        existing = ctx.db.get(Client, contact.client_id)
        if existing is not None:
            return {
                "warning": "already linked",
                "client_id": str(existing.id),
                "name": existing.name,
            }

    try:
        domain_enum = LegalDomain(domain)
    except ValueError:
        domain_enum = LegalDomain.OTHER

    display_name = (company_name or name).strip()
    matter_line = f"Matter ({domain_enum.value}): {matter_summary.strip()}"
    intake_note = _append_dated_note(None, matter_line)

    tags = ["wa-lead", f"domain:{domain_enum.value}"]
    if city:
        tags.append(f"city:{city.strip().lower()}")

    client = Client(
        tenant_id=ctx.tenant_id,
        name=display_name,
        kind="company" if (kind == "company" or company_name) else "person",
        status=ClientStatus.LEAD,
        phone=contact.wa_phone,
        email=email,
        address=city,
        notes=intake_note,
        tags=tags,
    )
    ctx.db.add(client)
    ctx.db.flush()  # realize client.id before linking the WhatsApp contact
    contact.client_id = client.id
    contact.display_name = display_name
    ctx.db.commit()
    ctx.db.refresh(client)
    log.info(
        "lead_captured",
        tenant_id=str(ctx.tenant_id),
        client_id=str(client.id),
        domain=domain_enum.value,
    )
    return {
        "id": str(client.id),
        "name": client.name,
        # SQLAlchemy returns the raw string when refreshing a row whose column
        # type is String(32) backing a StrEnum — coerce for stable JSON output.
        "status": str(client.status),
        "domain": domain_enum.value,
        "linked_to_whatsapp": True,
    }


@tool(
    {
        "type": "function",
        "name": "update_lead_matter",
        "description": (
            "Append a date-stamped note to the lead's running matter log. "
            "Use this whenever the user shares more detail about their case "
            "(deadlines, opposing party, amounts, documents they have, "
            "what they've already tried). Older notes are preserved — the "
            "lawyer reads the log top-down to get up to speed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": (
                        "One short paragraph capturing the new info. Be "
                        "concrete — names, dates, amounts."
                    ),
                },
            },
            "required": ["note"],
        },
    }
)
def update_lead_matter(ctx: ToolContext, note: str) -> dict:
    if ctx.whatsapp_contact_id is None:
        return {"error": "Not in a WhatsApp conversation."}
    contact = ctx.db.get(WhatsAppContact, ctx.whatsapp_contact_id)
    if contact is None or contact.tenant_id != ctx.tenant_id:
        return {"error": "WhatsApp contact not found."}
    if contact.client_id is None:
        return {
            "error": (
                "No lead captured yet. Call capture_lead first with name + matter."
            )
        }
    client = ctx.db.get(Client, contact.client_id)
    if client is None:
        return {"error": "Client not found."}
    client.notes = _append_dated_note(client.notes, note)
    ctx.db.commit()
    return {"id": str(client.id), "appended": True}


@tool(
    {
        "type": "function",
        "name": "request_consultation",
        "description": (
            "Mark this lead as wanting a paid consultation with the firm. "
            "Optionally include a preferred date/time the lead suggested "
            "(natural language is fine — the lawyer will confirm). This "
            "creates an escalation in the dashboard inbox so the lawyer "
            "can follow up. Call AFTER capture_lead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "preferred_when": {
                    "type": "string",
                    "description": "e.g. 'Sunday morning', 'tomorrow at 3pm'. Optional.",
                },
                "extra_notes": {
                    "type": "string",
                    "description": "Anything else the lawyer should know before reaching out.",
                },
            },
        },
    }
)
def request_consultation(
    ctx: ToolContext,
    preferred_when: str | None = None,
    extra_notes: str | None = None,
) -> dict:
    if ctx.whatsapp_contact_id is None or ctx.conversation_id is None:
        return {"error": "Not in a WhatsApp conversation."}
    contact = ctx.db.get(WhatsAppContact, ctx.whatsapp_contact_id)
    if contact is None or contact.tenant_id != ctx.tenant_id:
        return {"error": "WhatsApp contact not found."}

    bits = ["[CONSULTATION REQUEST]"]
    if preferred_when:
        bits.append(f"Preferred: {preferred_when.strip()}")
    if extra_notes:
        bits.append(f"Notes: {extra_notes.strip()}")
    if contact.client_id is None:
        bits.append("(lead not captured yet)")
    reason = " — ".join(bits)[:500]

    ctx.db.add(
        WhatsAppEscalation(
            tenant_id=ctx.tenant_id,
            conversation_id=ctx.conversation_id,
            reason=reason,
        )
    )

    if contact.client_id is not None:
        client = ctx.db.get(Client, contact.client_id)
        if client is not None:
            tags = list(client.tags or [])
            if "wants-consultation" not in tags:
                tags.append("wants-consultation")
                client.tags = tags
            client.notes = _append_dated_note(
                client.notes,
                f"Consultation requested. {preferred_when or 'no preferred time'}.",
            )
    ctx.db.commit()
    return {"requested": True}


# =============================================================================
# Scope membership lists
# =============================================================================

LAWYER_TOOLS = [
    "search_legal_db",
    "find_client",
    "add_client",
    "update_client",
    "find_case",
    "add_case",
    "remember_fact",
    "forget_fact",
]

# Intake scope is intentionally narrow. The agent can:
#   - answer general legal questions (search_legal_db)
#   - capture lead details + matter (capture_lead, update_lead_matter)
#   - book consultations (request_consultation)
#   - escalate urgent matters (escalate_to_lawyer)
#   - remember durable preferences (remember_fact, forget_fact)
# Notably ABSENT: find_case, find_client (privacy — leads must not see other
# clients' data), add_case, update_client (lawyer's job, not agent's).
INTAKE_TOOLS = [
    "search_legal_db",
    "capture_lead",
    "update_lead_matter",
    "request_consultation",
    "escalate_to_lawyer",
    "remember_fact",
    "forget_fact",
]


# =============================================================================
# Helpers used by the agent loop
# =============================================================================


def list_facts_for_prompt(ctx: ToolContext) -> list[dict]:
    """Returns the facts that should be injected into the system prompt.

    Includes tenant-scoped facts always, plus contact-scoped facts when the
    caller is in a WhatsApp conversation.
    """
    stmt = select(AgentFact).where(AgentFact.tenant_id == ctx.tenant_id)
    if ctx.whatsapp_contact_id is not None:
        stmt = stmt.where(
            (AgentFact.whatsapp_contact_id.is_(None))
            | (AgentFact.whatsapp_contact_id == ctx.whatsapp_contact_id)
        )
    else:
        stmt = stmt.where(AgentFact.whatsapp_contact_id.is_(None))
    rows = list(ctx.db.execute(stmt.order_by(AgentFact.created_at.asc())).scalars())
    return [{"id": str(r.id), "text": r.text} for r in rows]


def resolve_platform_tenant_id(db: Session) -> UUID | None:
    row = db.execute(
        select(Tenant).where(Tenant.slug == "platform", Tenant.is_active.is_(True))
    ).scalar_one_or_none()
    return row.id if row else None
