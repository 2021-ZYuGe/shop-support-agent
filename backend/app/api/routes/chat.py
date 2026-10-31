from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession
from app.db.base import utcnow
from app.db.models import Conversation, Feedback, Message
from app.schemas.chat import (
    ChatConversationPublic,
    ChatFeedbackPublic,
    ChatFeedbackRequest,
    ChatMessagePublic,
    ChatRequest,
    ChatSource,
    ChatToolTrace,
)
from app.services import agent, chat as chat_service
from app.services import embedding, knowledge, llm, vector_store

logger = logging.getLogger(__name__)

router = APIRouter()


def _source_payload(source: ChatSource) -> dict:
    return source.model_dump()


@router.get(
    "/conversations/{public_id}",
    response_model=ChatConversationPublic,
)
def get_conversation(public_id: str, db: DbSession) -> ChatConversationPublic:
    conversation = db.scalar(
        select(Conversation).where(Conversation.public_id == public_id)
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")

    messages = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role.in_(["user", "assistant"]),
        )
        .order_by(Message.id.asc())
        .limit(100)
    ).all()

    feedback_by_message = {
        feedback.message_id: feedback
        for feedback in db.scalars(
            select(Feedback).where(
                Feedback.message_id.in_([message.id for message in messages])
            )
        ).all()
    }

    public_messages: list[ChatMessagePublic] = []
    for message in messages:
        citations = None
        if message.citations:
            citations = [ChatSource(**item) for item in message.citations]
        tool_trace = None
        if message.tool_trace:
            tool_trace = [ChatToolTrace(**item) for item in message.tool_trace]
        feedback = feedback_by_message.get(message.id)
        feedback_public = (
            ChatFeedbackPublic(
                rating=feedback.rating,
                comment=feedback.comment,
                created_at=feedback.created_at,
            )
            if feedback
            else None
        )
        public_messages.append(
            ChatMessagePublic(
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
        )

    return ChatConversationPublic(
        public_id=conversation.public_id,
        status=conversation.status,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=public_messages,
    )


@router.post(
    "/conversations/{public_id}/messages/{message_id}/feedback",
    response_model=ChatFeedbackPublic,
)
def submit_feedback(
    public_id: str,
    message_id: int,
    payload: ChatFeedbackRequest,
    db: DbSession,
) -> ChatFeedbackPublic:
    conversation = db.scalar(
        select(Conversation).where(Conversation.public_id == public_id)
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在。")

    message = db.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
            Message.role == "assistant",
        )
    )
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在。"
        )

    feedback = db.scalar(select(Feedback).where(Feedback.message_id == message.id))
    comment = payload.comment.strip() if payload.comment else None
    if feedback is None:
        feedback = Feedback(
            message_id=message.id,
            rating=payload.rating,
            comment=comment or None,
        )
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = comment or None
    db.commit()
    db.refresh(feedback)
    return ChatFeedbackPublic(
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )


@router.post("/stream")
def stream_chat(
    payload: ChatRequest,
    db: DbSession,
    settings: AppSettings,
) -> StreamingResponse:
    user_text = payload.message.strip()
    if not user_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="消息不能为空。",
        )

    if payload.conversation_id:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.public_id == payload.conversation_id
            )
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在，请开始新对话。",
            )
    else:
        conversation = Conversation(
            public_id=secrets.token_urlsafe(18),
            channel="web",
            status="active",
        )
        db.add(conversation)
        db.flush()

    previous_messages = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role.in_(["user", "assistant"]),
        )
        .order_by(Message.id.desc())
        .limit(settings.chat_history_limit)
    ).all()
    history = chat_service.build_history(
        list(reversed(previous_messages)),
        max_chars=settings.chat_history_message_chars,
    )

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_text,
    )
    conversation.updated_at = utcnow()
    db.add(user_message)
    db.commit()

    try:
        outcome = agent.run_agent(db, conversation, history, user_text)
    except embedding.EmbeddingNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except embedding.EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except vector_store.VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except knowledge.KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    sources_payload = [
        _source_payload(ChatSource(**source)) for source in outcome.sources
    ]
    tool_trace = outcome.tool_trace
    mode = outcome.mode
    public_id = conversation.public_id
    direct_answer = outcome.direct_answer

    needs_generation = direct_answer is None
    if needs_generation and not settings.has_deepseek_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="尚未配置 DEEPSEEK_API_KEY，无法生成回答。",
        )

    def event_stream() -> Iterator[str]:
        yield chat_service.sse_event(
            "meta",
            {
                "conversation_id": public_id,
                "mode": mode,
                "sources": sources_payload,
                "tools": tool_trace,
            },
        )

        started_at = time.perf_counter()
        parts: list[str] = []
        usage = llm.LLMUsage(prompt_tokens=0, completion_tokens=0)
        saved = False
        if direct_answer is None:
            model_name = settings.deepseek_model
        elif mode == "fallback":
            model_name = "policy_fallback"
        elif mode == "handoff":
            model_name = "handoff_workflow"
        else:
            model_name = "workflow_clarify"

        def persist_reply(reply: str) -> int | None:
            nonlocal saved
            if saved or not reply.strip():
                return None
            try:
                message_id = chat_service.save_assistant_message(
                    public_id=public_id,
                    content=reply.strip(),
                    citations=sources_payload,
                    tool_trace=tool_trace,
                    model=model_name,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    latency_ms=int((time.perf_counter() - started_at) * 1000),
                )
                if message_id is not None:
                    saved = True
                return message_id
            except Exception:
                logger.exception("Failed to persist assistant message")
                return None

        try:
            if direct_answer is not None:
                parts.append(direct_answer)
                yield chat_service.sse_event("delta", {"text": direct_answer})
            else:
                for event in llm.stream_completion(settings, outcome.llm_messages or []):
                    if isinstance(event, llm.LLMDelta):
                        parts.append(event.text)
                        yield chat_service.sse_event("delta", {"text": event.text})
                    elif isinstance(event, llm.LLMUsage):
                        usage = event

            reply = "".join(parts)
            if not reply.strip():
                raise llm.LLMError("模型没有返回内容，请稍后重试。")

            latency_ms = int((time.perf_counter() - started_at) * 1000)
            message_id = persist_reply(reply)
            yield chat_service.sse_event(
                "done",
                {
                    "conversation_id": public_id,
                    "message_id": message_id,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "latency_ms": latency_ms,
                    "mode": mode,
                    "tools": tool_trace,
                },
            )
        except GeneratorExit:
            raise
        except Exception as exc:
            logger.warning("Chat response failed: %s", type(exc).__name__)
            persist_reply("".join(parts))
            message = (
                str(exc)
                if isinstance(exc, llm.LLMError)
                else "回答生成失败，请稍后重试或转人工。"
            )
            yield chat_service.sse_event("error", {"message": message})
        finally:
            if not saved and parts:
                persist_reply("".join(parts))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
