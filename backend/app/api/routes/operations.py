from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import AppSettings, CurrentAdmin, DbSession
from app.db.base import utcnow
from app.db.models import (
    Admin,
    Conversation,
    Feedback,
    HandoffTicket,
    Message,
    ToolCallLog,
)
from app.schemas.chat import ChatFeedbackPublic, ChatMessagePublic, ChatSource, ChatToolTrace
from app.schemas.operations import (
    AdminConversationDetail,
    AdminConversationList,
    AdminConversationSummary,
    AdminTicketList,
    AdminTicketSummary,
    AdminTicketUpdate,
    InsightMetrics,
    InsightsResponse,
    KnowledgeGapItem,
    LowFeedbackItem,
    ToolUsageItem,
)

router = APIRouter()

TOOL_LABELS = {
    "lookup_order": "订单查询",
    "lookup_shipment": "物流查询",
    "check_after_sales": "售后条件判断",
    "create_handoff": "人工工单",
}
TICKET_STATUSES = {"open", "in_progress", "resolved", "closed"}


def _feedback_map(db: DbSession, messages: list[Message]) -> dict[int, Feedback]:
    ids = [message.id for message in messages]
    if not ids:
        return {}
    return {
        feedback.message_id: feedback
        for feedback in db.scalars(
            select(Feedback).where(Feedback.message_id.in_(ids))
        ).all()
    }


def _to_public_message(message: Message, feedback: Feedback | None) -> ChatMessagePublic:
    citations = None
    if message.citations:
        citations = [ChatSource(**item) for item in message.citations]
    tool_trace = None
    if message.tool_trace:
        tool_trace = [ChatToolTrace(**item) for item in message.tool_trace]
    feedback_public = None
    if feedback:
        feedback_public = ChatFeedbackPublic(
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )
    return ChatMessagePublic(
        id=message.id,
        role=message.role,
        content=message.content,
        citations=citations,
        tool_trace=tool_trace,
        feedback=feedback_public,
        model=message.model,
        prompt_tokens=message.prompt_tokens,
        completion_tokens=message.completion_tokens,
        latency_ms=message.latency_ms,
        created_at=message.created_at,
    )


def _ticket_summary(
    ticket: HandoffTicket,
    conversation_public_id: str,
    admin_names: dict[int, str],
) -> AdminTicketSummary:
    return AdminTicketSummary(
        id=ticket.id,
        conversation_public_id=conversation_public_id,
        reason=ticket.reason,
        summary=ticket.summary,
        status=ticket.status,
        priority=ticket.priority,
        assigned_admin_id=ticket.assigned_admin_id,
        assigned_admin_name=admin_names.get(ticket.assigned_admin_id or 0),
        resolution_note=ticket.resolution_note,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _admin_names(db: DbSession) -> dict[int, str]:
    return {admin.id: admin.display_name for admin in db.scalars(select(Admin)).all()}


@router.get("/conversations", response_model=AdminConversationList)
def list_conversations(
    _: CurrentAdmin,
    db: DbSession,
    conversation_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminConversationList:
    if conversation_status and conversation_status not in {"active", "handed_off"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话状态参数不正确。",
        )

    count_stmt = select(func.count()).select_from(Conversation)
    list_stmt = select(Conversation).options(
        selectinload(Conversation.messages),
        selectinload(Conversation.handoff_tickets),
    )
    if conversation_status:
        count_stmt = count_stmt.where(Conversation.status == conversation_status)
        list_stmt = list_stmt.where(Conversation.status == conversation_status)

    total = int(db.scalar(count_stmt) or 0)
    conversations = db.scalars(
        list_stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    assistant_messages = [
        message
        for conversation in conversations
        for message in conversation.messages
        if message.role == "assistant"
    ]
    feedback_by_message = _feedback_map(db, assistant_messages)

    status_counts = {
        value: int(count)
        for value, count in db.execute(
            select(Conversation.status, func.count()).group_by(Conversation.status)
        ).all()
    }

    items: list[AdminConversationSummary] = []
    for conversation in conversations:
        messages = sorted(conversation.messages, key=lambda item: item.id)
        assistant_messages_for_conversation = [
            message for message in messages if message.role == "assistant"
        ]
        ratings = [
            feedback_by_message[message.id].rating
            for message in assistant_messages_for_conversation
            if message.id in feedback_by_message
        ]
        last_message = messages[-1] if messages else None
        open_ticket_count = sum(
            1
            for ticket in conversation.handoff_tickets
            if ticket.status in {"open", "in_progress"}
        )
        items.append(
            AdminConversationSummary(
                public_id=conversation.public_id,
                status=conversation.status,
                channel=conversation.channel,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                message_count=len(messages),
                last_message_preview=(
                    last_message.content[:100] if last_message else None
                ),
                open_ticket_count=open_ticket_count,
                positive_feedback=sum(1 for rating in ratings if rating == 1),
                negative_feedback=sum(1 for rating in ratings if rating == -1),
            )
        )

    return AdminConversationList(
        items=items,
        total=total,
        status_counts=status_counts,
    )


@router.get(
    "/conversations/{public_id}",
    response_model=AdminConversationDetail,
)
def conversation_detail(
    public_id: str,
    _: CurrentAdmin,
    db: DbSession,
) -> AdminConversationDetail:
    conversation = db.scalar(
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.handoff_tickets),
        )
        .where(Conversation.public_id == public_id)
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。"
        )

    messages = sorted(conversation.messages, key=lambda item: item.id)
    feedback_by_message = _feedback_map(db, messages)
    admin_names = _admin_names(db)
    tickets = sorted(
        conversation.handoff_tickets,
        key=lambda item: item.updated_at,
        reverse=True,
    )
    return AdminConversationDetail(
        public_id=conversation.public_id,
        status=conversation.status,
        channel=conversation.channel,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            _to_public_message(message, feedback_by_message.get(message.id))
            for message in messages
        ],
        tickets=[
            _ticket_summary(ticket, conversation.public_id, admin_names)
            for ticket in tickets
        ],
    )


@router.get("/tickets", response_model=AdminTicketList)
def list_tickets(
    _: CurrentAdmin,
    db: DbSession,
    ticket_status: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminTicketList:
    if ticket_status and ticket_status not in TICKET_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="工单状态参数不正确。",
        )
    if priority and priority not in {"low", "normal", "high"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="工单优先级参数不正确。",
        )

    count_stmt = select(func.count()).select_from(HandoffTicket)
    list_stmt = (
        select(HandoffTicket, Conversation.public_id)
        .join(Conversation, Conversation.id == HandoffTicket.conversation_id)
    )
    if ticket_status:
        count_stmt = count_stmt.where(HandoffTicket.status == ticket_status)
        list_stmt = list_stmt.where(HandoffTicket.status == ticket_status)
    if priority:
        count_stmt = count_stmt.where(HandoffTicket.priority == priority)
        list_stmt = list_stmt.where(HandoffTicket.priority == priority)

    total = int(db.scalar(count_stmt) or 0)
    rows = db.execute(
        list_stmt.order_by(HandoffTicket.updated_at.desc(), HandoffTicket.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    admin_names = _admin_names(db)
    items = [
        _ticket_summary(ticket, public_id, admin_names)
        for ticket, public_id in rows
    ]
    status_counts = {
        value: int(count)
        for value, count in db.execute(
            select(HandoffTicket.status, func.count()).group_by(
                HandoffTicket.status
            )
        ).all()
    }
    return AdminTicketList(items=items, total=total, status_counts=status_counts)


@router.patch("/tickets/{ticket_id}", response_model=AdminTicketSummary)
def update_ticket(
    ticket_id: int,
    payload: AdminTicketUpdate,
    admin: CurrentAdmin,
    db: DbSession,
) -> AdminTicketSummary:
    row = db.execute(
        select(HandoffTicket, Conversation.public_id)
        .join(Conversation, Conversation.id == HandoffTicket.conversation_id)
        .where(HandoffTicket.id == ticket_id)
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在。"
        )
    ticket, conversation_public_id = row

    if payload.status is not None:
        ticket.status = payload.status
    if payload.priority is not None:
        ticket.priority = payload.priority
    if payload.assign_to_me or ticket.assigned_admin_id is None:
        ticket.assigned_admin_id = admin.id
    if payload.resolution_note is not None:
        ticket.resolution_note = payload.resolution_note.strip() or None
    ticket.updated_at = utcnow()
    db.commit()
    db.refresh(ticket)
    admin_names = _admin_names(db)
    return _ticket_summary(ticket, conversation_public_id, admin_names)


@router.get("/insights", response_model=InsightsResponse)
def insights(
    _: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
) -> InsightsResponse:
    conversation_counts = {
        value: int(count)
        for value, count in db.execute(
            select(Conversation.status, func.count()).group_by(Conversation.status)
        ).all()
    }
    ticket_counts = {
        value: int(count)
        for value, count in db.execute(
            select(HandoffTicket.status, func.count()).group_by(HandoffTicket.status)
        ).all()
    }
    feedback_counts = {
        int(rating): int(count)
        for rating, count in db.execute(
            select(Feedback.rating, func.count()).group_by(Feedback.rating)
        ).all()
    }
    prompt_tokens = int(
        db.scalar(select(func.coalesce(func.sum(Message.prompt_tokens), 0))) or 0
    )
    completion_tokens = int(
        db.scalar(select(func.coalesce(func.sum(Message.completion_tokens), 0))) or 0
    )
    avg_latency = float(
        db.scalar(
            select(func.coalesce(func.avg(Message.latency_ms), 0)).where(
                Message.role == "assistant"
            )
        )
        or 0
    )
    fallback_messages = int(
        db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.role == "assistant", Message.model == "policy_fallback")
        )
        or 0
    )
    metrics = InsightMetrics(
        conversations_total=sum(conversation_counts.values()),
        conversations_active=conversation_counts.get("active", 0),
        conversations_handed_off=conversation_counts.get("handed_off", 0),
        tickets_open=ticket_counts.get("open", 0),
        tickets_in_progress=ticket_counts.get("in_progress", 0),
        tickets_resolved=ticket_counts.get("resolved", 0)
        + ticket_counts.get("closed", 0),
        messages_total=int(db.scalar(select(func.count()).select_from(Message)) or 0),
        assistant_messages=int(
            db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.role == "assistant")
            )
            or 0
        ),
        feedback_positive=feedback_counts.get(1, 0),
        feedback_negative=feedback_counts.get(-1, 0),
        fallback_messages=fallback_messages,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_cny=round(
            prompt_tokens
            / 1_000_000
            * settings.deepseek_input_price_cny_per_million
            + completion_tokens
            / 1_000_000
            * settings.deepseek_output_price_cny_per_million,
            6,
        ),
        avg_latency_ms=round(avg_latency, 1),
    )

    tools = [
        ToolUsageItem(
            tool_name=tool_name,
            label=TOOL_LABELS.get(tool_name, tool_name),
            count=int(count),
            avg_duration_ms=round(float(avg_duration), 1),
        )
        for tool_name, count, avg_duration in db.execute(
            select(
                ToolCallLog.tool_name,
                func.count(),
                func.coalesce(func.avg(ToolCallLog.duration_ms), 0),
            )
            .group_by(ToolCallLog.tool_name)
            .order_by(func.count().desc())
        ).all()
    ]

    low_feedback = [
        LowFeedbackItem(
            feedback_id=feedback.id,
            conversation_public_id=conversation.public_id,
            message_id=message.id,
            assistant_preview=message.content[:160],
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )
        for feedback, message, conversation in db.execute(
            select(Feedback, Message, Conversation)
            .join(Message, Message.id == Feedback.message_id)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Feedback.rating == -1)
            .order_by(Feedback.created_at.desc(), Feedback.id.desc())
            .limit(10)
        ).all()
    ]

    fallback_rows = db.scalars(
        select(Message)
        .options(joinedload(Message.conversation))
        .where(Message.role == "assistant", Message.model == "policy_fallback")
        .order_by(Message.id.desc())
        .limit(10)
    ).all()
    knowledge_gaps: list[KnowledgeGapItem] = []
    for fallback in fallback_rows:
        question = db.scalar(
            select(Message)
            .where(
                Message.conversation_id == fallback.conversation_id,
                Message.role == "user",
                Message.id < fallback.id,
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        if question is None:
            continue
        knowledge_gaps.append(
            KnowledgeGapItem(
                conversation_public_id=fallback.conversation.public_id,
                question=question.content[:300],
                assistant_preview=fallback.content[:160],
                created_at=fallback.created_at,
            )
        )

    return InsightsResponse(
        metrics=metrics,
        tools=tools,
        low_feedback=low_feedback,
        knowledge_gaps=knowledge_gaps,
        generated_at=utcnow(),
    )
