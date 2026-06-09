from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import ConversationChannel, MessageRole


class Citation(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    page_number: int | None = None
    snippet: str
    score: float


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    case_id: UUID | None = None
    message: str = Field(min_length=1, max_length=8000)
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    citations: list[Citation] = []
    created_at: datetime


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: ChatMessageRead


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    channel: ConversationChannel
    case_id: UUID | None
    client_id: UUID | None
    created_at: datetime
    updated_at: datetime
