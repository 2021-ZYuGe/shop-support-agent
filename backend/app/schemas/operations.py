from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import UtcSerializationModel
from app.schemas.chat import ChatMessagePublic


class AdminConversationSummary(UtcSerializationModel):
    public_id: str
    status: str
    channel: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: str | None = None
    open_ticket_count: int
    positive_feedback: int
    negative_feedback: int


class AdminConversationList(BaseModel):
    items: list[AdminConversationSummary]
    total: int
    status_counts: dict[str, int]


class AdminTicketSummary(UtcSerializationModel):
    id: int
    conversation_public_id: str
    reason: str
    summary: str
    status: str
    priority: str
    assigned_admin_id: int | None = None
    assigned_admin_name: str | None = None
    resolution_note: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminConversationDetail(UtcSerializationModel):
    public_id: str
    status: str
    channel: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessagePublic]
    tickets: list[AdminTicketSummary]


class AdminTicketList(BaseModel):
    items: list[AdminTicketSummary]
    total: int
    status_counts: dict[str, int]


class AdminTicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None
    priority: Literal["low", "normal", "high"] | None = None
    resolution_note: str | None = Field(default=None, max_length=2000)
    assign_to_me: bool = True


class InsightMetrics(BaseModel):
    conversations_total: int
    conversations_active: int
    conversations_handed_off: int
    tickets_open: int
    tickets_in_progress: int
    tickets_resolved: int
    messages_total: int
    assistant_messages: int
    feedback_positive: int
    feedback_negative: int
    fallback_messages: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_cny: float
    avg_latency_ms: float


class ToolUsageItem(BaseModel):
    tool_name: str
    label: str
    count: int
    avg_duration_ms: float


class LowFeedbackItem(UtcSerializationModel):
    feedback_id: int
    conversation_public_id: str
    message_id: int
    assistant_preview: str
    rating: int
    comment: str | None = None
    created_at: datetime


class KnowledgeGapItem(UtcSerializationModel):
    conversation_public_id: str
    question: str
    assistant_preview: str
    created_at: datetime


class InsightsResponse(UtcSerializationModel):
    metrics: InsightMetrics
    tools: list[ToolUsageItem]
    low_feedback: list[LowFeedbackItem]
    knowledge_gaps: list[KnowledgeGapItem]
    generated_at: datetime
