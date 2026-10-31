from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db.models import Conversation, Feedback, HandoffTicket, Message
from app.db.session import SessionLocal


def _seed_operations_conversation() -> tuple[str, int, int]:
    public_id = f"ops-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as db:
        conversation = Conversation(
            public_id=public_id,
            channel="web",
            status="handed_off",
            created_at=now - timedelta(minutes=5),
            updated_at=now,
        )
        db.add(conversation)
        db.flush()

        user = Message(
            conversation_id=conversation.id,
            role="user",
            content="订单 QH20261028003 有划痕能退吗？",
            created_at=now - timedelta(minutes=4),
        )
        assistant = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="订单符合申请条件，需要人工工单处理。",
            model="deepseek-flash",
            prompt_tokens=100,
            completion_tokens=20,
            latency_ms=1200,
            tool_trace=[
                {
                    "tool": "check_after_sales",
                    "label": "售后条件判断",
                    "status": "success",
                    "summary": "订单符合申请条件。",
                    "duration_ms": 2,
                }
            ],
            created_at=now - timedelta(minutes=3),
        )
        db.add_all([user, assistant])
        db.flush()

        db.add(
            Feedback(
                message_id=assistant.id,
                rating=-1,
                comment="没有说明实际怎么寄回",
                created_at=now - timedelta(minutes=2),
            )
        )
        ticket = HandoffTicket(
            conversation_id=conversation.id,
            reason="用户要求人工处理退货",
            summary="用户询问订单退货流程。",
            status="open",
            priority="high",
            created_at=now - timedelta(minutes=2),
            updated_at=now,
        )
        db.add(ticket)

        fallback_user = Message(
            conversation_id=conversation.id,
            role="user",
            content="你们支持海外配送吗？",
            created_at=now - timedelta(minutes=1),
        )
        fallback_assistant = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="知识库未命中，建议转人工。",
            model="policy_fallback",
            created_at=now,
        )
        db.add_all([fallback_user, fallback_assistant])
        db.commit()
        db.refresh(assistant)
        db.refresh(ticket)
        return public_id, assistant.id, ticket.id


def test_operations_requires_admin(client: TestClient) -> None:
    assert client.get("/api/admin/conversations").status_code == 401
    assert client.get("/api/admin/tickets").status_code == 401
    assert client.get("/api/admin/insights").status_code == 401


def test_admin_conversation_list_and_detail(admin_client: TestClient) -> None:
    public_id, assistant_id, ticket_id = _seed_operations_conversation()

    listing = admin_client.get("/api/admin/conversations")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    item = next(item for item in body["items"] if item["public_id"] == public_id)
    assert item["status"] == "handed_off"
    assert item["open_ticket_count"] == 1
    assert item["negative_feedback"] == 1

    detail = admin_client.get(f"/api/admin/conversations/{public_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "handed_off"
    assert len(payload["messages"]) == 4
    assert payload["tickets"][0]["id"] == ticket_id
    assistant = next(item for item in payload["messages"] if item["id"] == assistant_id)
    assert assistant["tool_trace"][0]["tool"] == "check_after_sales"
    assert assistant["feedback"]["rating"] == -1


def test_ticket_can_be_worked_and_closed(admin_client: TestClient) -> None:
    _, _, ticket_id = _seed_operations_conversation()

    listing = admin_client.get("/api/admin/tickets")
    assert listing.status_code == 200
    assert any(item["id"] == ticket_id for item in listing.json()["items"])

    updated = admin_client.patch(
        f"/api/admin/tickets/{ticket_id}",
        json={
            "status": "in_progress",
            "priority": "high",
            "resolution_note": "已联系用户补充照片",
            "assign_to_me": True,
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["status"] == "in_progress"
    assert payload["resolution_note"] == "已联系用户补充照片"
    assert payload["assigned_admin_name"] == "测试管理员"

    resolved = admin_client.patch(
        f"/api/admin/tickets/{ticket_id}",
        json={"status": "resolved", "resolution_note": "已完成退货登记"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_insights_contains_feedback_gaps_and_cost(admin_client: TestClient) -> None:
    public_id, _, _ = _seed_operations_conversation()
    response = admin_client.get("/api/admin/insights")
    assert response.status_code == 200
    body = response.json()

    metrics = body["metrics"]
    assert metrics["conversations_total"] >= 1
    assert metrics["messages_total"] >= 4
    assert metrics["assistant_messages"] >= 2
    assert metrics["feedback_negative"] >= 1
    assert metrics["fallback_messages"] >= 1
    assert metrics["prompt_tokens"] >= 100
    assert metrics["estimated_cost_cny"] >= 0

    assert any(item["conversation_public_id"] == public_id for item in body["low_feedback"])
    assert any(item["conversation_public_id"] == public_id for item in body["knowledge_gaps"])
    assert any(item["question"] == "你们支持海外配送吗？" for item in body["knowledge_gaps"])
