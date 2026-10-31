from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import UtcSerializationModel


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=64)


class ChatSource(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    doc_type: str
    version: str
    heading: str | None = None
    content: str
    source_name: str
    similarity: float


class ChatToolTrace(BaseModel):
    tool: str
    label: str
    status: str
    summary: str
    duration_ms: int


class ChatFeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=500)


class ChatFeedbackPublic(UtcSerializationModel):
    rating: int
    comment: str | None = None
    created_at: datetime


class ChatMessagePublic(UtcSerializationModel):
    id: int
    role: str
    content: str
    citations: list[ChatSource] | None = None
    tool_trace: list[ChatToolTrace] | None = None
    feedback: ChatFeedbackPublic | None = None
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    created_at: datetime


class ChatConversationPublic(UtcSerializationModel):
    public_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessagePublic]
