from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.db.models import Conversation, HandoffTicket, ToolCallLog
from app.db.session import SessionLocal
from app.services.tools import OrderToolkit, ToolError, extract_order_no


def _conversation() -> Conversation:
    with SessionLocal() as db:
        conversation = Conversation(
            public_id=f"test-{uuid.uuid4().hex}",
            channel="web",
            status="active",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation


def test_extract_order_no() -> None:
    assert extract_order_no("帮我查订单 qh20261028003 的物流") == "QH20261028003"
    assert extract_order_no("没有订单号") is None


def test_lookup_order_and_audit_log() -> None:
    conversation = _conversation()
    with SessionLocal() as db:
        toolkit = OrderToolkit(db, conversation)
        data = toolkit.lookup_order("QH20261028003")
        db.commit()

        assert data["order_no"] == "QH20261028003"
        assert data["status"] == "delivered"
        assert len(toolkit.trace) == 1
        assert toolkit.trace[0]["status"] == "success"
        logs = db.scalar(
            select(func.count())
            .select_from(ToolCallLog)
            .where(ToolCallLog.conversation_id == conversation.id)
        )
        assert logs == 1


def test_logistics_and_after_sales_rules() -> None:
    conversation = _conversation()
    with SessionLocal() as db:
        toolkit = OrderToolkit(db, conversation)

        shipment = toolkit.lookup_shipment("QH20261029006")
        assert shipment["shipment"]["status"] == "in_transit"

        no_reason = toolkit.check_after_sales("QH20261028003", "no_reason")
        assert no_reason["eligible"] is True
        assert no_reason["requires_quality_evidence"] is False

        quality = toolkit.check_after_sales("QH20261028003", "quality")
        assert quality["eligible"] is True
        assert quality["requires_quality_evidence"] is True
        db.commit()

    with SessionLocal() as db:
        toolkit = OrderToolkit(db, conversation)
        old_order = toolkit.check_after_sales("QH20261011005", "no_reason")
        assert old_order["eligible"] is False
        db.commit()


def test_invalid_order_returns_error_trace() -> None:
    conversation = _conversation()
    with SessionLocal() as db:
        toolkit = OrderToolkit(db, conversation)
        with pytest.raises(ToolError):
            toolkit.lookup_order("BAD-ORDER")
        db.commit()
        assert toolkit.trace[0]["status"] == "error"
        assert toolkit.trace[0]["label"] == "订单查询"


def test_handoff_is_idempotent_per_conversation() -> None:
    conversation = _conversation()
    with SessionLocal() as db:
        toolkit = OrderToolkit(db, conversation)
        first = toolkit.create_handoff(
            reason="用户要求转人工处理退款",
            summary="用户要求人工协助。",
            order_no="QH20261028003",
        )
        second = toolkit.create_handoff(
            reason="再次请求人工",
            summary="用户再次请求人工。",
            order_no="QH20261028003",
        )
        db.commit()

        assert first["existing"] is False
        assert second["existing"] is True
        assert first["ticket_id"] == second["ticket_id"]
        count = db.scalar(
            select(func.count())
            .select_from(HandoffTicket)
            .where(HandoffTicket.conversation_id == conversation.id)
        )
        assert count == 1
        refreshed = db.get(Conversation, conversation.id)
        assert refreshed is not None
        assert refreshed.status == "handed_off"
