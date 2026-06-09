"""Chat with the AI: list conversations, send a message (RAG-grounded).

Each user message triggers a RAG answer. We persist both the user message and
the assistant's response (with citations) so the dashboard can re-render the
exact same exchange — including clickable citations — without re-running the
LLM.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import Conversation, ConversationChannel, Message, MessageRole
from app.schemas.chat import (
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    Citation,
    ConversationRead,
)
from app.services.agent import run_dashboard_turn
from app.services.billing import LimitExceeded, assert_within_limits, record_usage
from app.services.rag import answer
from app.services.rate_limit import rate_limit_check

router = APIRouter()


# Per-user/tenant rate limits on the agent loop. The agent can make up to
# MAX_STEPS LLM calls per turn — uncapped, one user could rack up serious
# OpenAI costs in minutes. These are sliding-window counters in Redis;
# fall-open on Redis outage so we never block legitimate work.
_AGENT_RL_PER_USER_PER_MIN = 30
_AGENT_RL_PER_TENANT_PER_MIN = 120


def _enforce_agent_rate_limit(tenant_id, user_id) -> None:
    for bucket, identifier, limit in (
        ("chat-agent-user", str(user_id), _AGENT_RL_PER_USER_PER_MIN),
        ("chat-agent-tenant", str(tenant_id), _AGENT_RL_PER_TENANT_PER_MIN),
    ):
        allowed, _remaining, reset = rate_limit_check(
            bucket=bucket,
            identifier=identifier,
            limit=limit,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit hit on {bucket}. Retry in {reset}s.",
                headers={"Retry-After": str(reset)},
            )


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationRead]:
    rows = TenantQuery.list_(
        db, Conversation, principal.tenant_id, limit=limit, offset=offset
    )
    return [ConversationRead.model_validate(c) for c in rows]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ChatMessageRead],
)
def list_messages(
    conversation_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ChatMessageRead]:
    conv = TenantQuery.get(db, Conversation, principal.tenant_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    msgs = list(
        db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
        ).scalars()
    )
    return [ChatMessageRead.model_validate(m) for m in msgs]


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def send(
    body: ChatRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    _enforce_agent_rate_limit(principal.tenant_id, principal.user.id)
    try:
        assert_within_limits(db, tenant_id=principal.tenant_id, kind="message")
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Plan limit reached: {exc.kind} ({exc.limit}).",
        ) from exc

    # 1. Get or create conversation
    if body.conversation_id is not None:
        conv = TenantQuery.get(db, Conversation, principal.tenant_id, body.conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        conv = Conversation(
            tenant_id=principal.tenant_id,
            channel=ConversationChannel.DASHBOARD,
            user_id=principal.user.id,
            case_id=body.case_id,
            title=body.message[:60],
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # 2. Persist user message
    user_msg = Message(
        tenant_id=principal.tenant_id,
        conversation_id=conv.id,
        role=MessageRole.USER,
        content=body.message,
    )
    db.add(user_msg)
    db.commit()

    # 3. Build short history for the model (last 8 messages before this one)
    history_rows = list(
        db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.id != user_msg.id)
            .order_by(Message.created_at.desc())
            .limit(8)
        ).scalars()
    )
    history = [{"role": m.role.value, "content": m.content} for m in reversed(history_rows)]

    # 4. RAG
    rag = answer(
        db,
        query=body.message,
        tenant_id=principal.tenant_id,
        case_id=conv.case_id,
        locale=body.locale,
        history=history,
    )

    # 5. Persist assistant message with citations
    assistant_msg = Message(
        tenant_id=principal.tenant_id,
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content=rag.answer,
        citations=rag.citations,
        token_count=rag.input_tokens + rag.output_tokens,
        model=rag.model,
        latency_ms=rag.latency_ms,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    record_usage(db, tenant_id=principal.tenant_id, kind="message")

    return ChatResponse(
        conversation_id=conv.id,
        message=ChatMessageRead(
            id=assistant_msg.id,
            conversation_id=conv.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            citations=[Citation(**c) for c in assistant_msg.citations],
            created_at=assistant_msg.created_at,
        ),
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_conversation(
    conversation_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    conv = TenantQuery.get(db, Conversation, principal.tenant_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(conv)
    db.commit()


@router.post("/agent", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def send_agent(
    body: ChatRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Dashboard agent: tool-use loop running on ChatGPT OAuth.

    Same input shape as /chat, but instead of one-shot RAG the model can call
    tools (search_legal_db, find_client, add_case, ...) across multiple steps
    before producing a final reply. Uses the broader "lawyer" tool scope.
    """
    if principal.tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a tenant context.",
        )
    _enforce_agent_rate_limit(principal.tenant_id, principal.user.id)
    try:
        assert_within_limits(db, tenant_id=principal.tenant_id, kind="message")
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Plan limit reached: {exc.kind} ({exc.limit}).",
        ) from exc

    reply = run_dashboard_turn(
        db,
        tenant=principal.tenant,
        user_id=principal.user.id,
        conversation_id=body.conversation_id,
        user_message=body.message,
        locale=body.locale,
        case_id=body.case_id,
    )
    record_usage(db, tenant_id=principal.tenant_id, kind="message")

    # Re-fetch the assistant message we just persisted so the response shape
    # exactly matches /chat.
    assistant_msg = db.execute(
        select(Message)
        .where(
            Message.conversation_id == reply.conversation_id,
            Message.role == MessageRole.ASSISTANT,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    ).scalar_one()

    return ChatResponse(
        conversation_id=reply.conversation_id,
        message=ChatMessageRead(
            id=assistant_msg.id,
            conversation_id=reply.conversation_id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            citations=[Citation(**c) for c in (assistant_msg.citations or [])],
            created_at=assistant_msg.created_at,
        ),
    )
