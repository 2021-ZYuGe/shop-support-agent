from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services import knowledge, llm
from app.services.chat import FALLBACK_ANSWER


def _parse_sse(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in payload.strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        data = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((event_name, data))
    return events


def test_chat_falls_back_without_sources(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "search_knowledge", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/stream",
        json={"message": "请讲一个笑话"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    event_names = [name for name, _ in events]
    assert "meta" in event_names
    assert "delta" in event_names
    assert "done" in event_names

    meta = next(data for name, data in events if name == "meta")
    assert meta["mode"] == "fallback"
    assert meta["sources"] == []

    delta = next(data for name, data in events if name == "delta")
    assert FALLBACK_ANSWER in delta["text"]

    conversation = client.get(f"/api/chat/conversations/{meta['conversation_id']}")
    assert conversation.status_code == 200
    messages = conversation.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["model"] == "policy_fallback"


def test_chat_streams_rag_answer_and_persists_citations(
    client: TestClient,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key", raising=False)

    source = {
        "chunk_id": 1,
        "document_id": 1,
        "title": "青禾生活售后政策（2026 版）",
        "doc_type": "policy",
        "version": "2026.1",
        "heading": "七天无理由退货",
        "content": "签收后七天内，在商品完好、不影响二次销售的前提下，可以申请无理由退货。",
        "source_name": "synthetic://policy/after-sales-2026",
        "similarity": 0.78,
    }
    monkeypatch.setattr(knowledge, "search_knowledge", lambda *args, **kwargs: [source])

    def fake_stream(settings, messages):
        captured_messages.append(messages)
        yield llm.LLMDelta("依据售后政策，")
        yield llm.LLMDelta("签收后七天内可以申请退货 [1]。")
        yield llm.LLMUsage(prompt_tokens=120, completion_tokens=28)

    captured_messages: list[list[dict[str, str]]] = []
    monkeypatch.setattr(llm, "stream_completion", fake_stream)

    response = client.post(
        "/api/chat/stream",
        json={"message": "我买的商品可以退吗？"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    meta = next(data for name, data in events if name == "meta")
    assert meta["mode"] == "rag"
    assert meta["sources"][0]["heading"] == "七天无理由退货"

    text = "".join(data["text"] for name, data in events if name == "delta")
    assert "[1]" in text
    assert "签收后七天内" in text
    done = next(data for name, data in events if name == "done")
    assert done["prompt_tokens"] == 120
    assert done["completion_tokens"] == 28
    assert done["mode"] == "rag"
    assert captured_messages[0][0]["role"] == "system"
    assert "七天无理由退货" in captured_messages[0][-1]["content"]

    conversation = client.get(
        f"/api/chat/conversations/{meta['conversation_id']}"
    ).json()
    assistant = conversation["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["citations"][0]["title"] == source["title"]


def test_chat_history_can_be_restored(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(knowledge, "search_knowledge", lambda *args, **kwargs: [])
    first = client.post("/api/chat/stream", json={"message": "你好"})
    conversation_id = next(
        data["conversation_id"]
        for name, data in _parse_sse(first.text)
        if name == "meta"
    )

    second = client.post(
        "/api/chat/stream",
        json={"message": "退货需要多久？", "conversation_id": conversation_id},
    )
    assert second.status_code == 200

    conversation = client.get(f"/api/chat/conversations/{conversation_id}").json()
    assert [message["role"] for message in conversation["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_unknown_conversation_returns_404(client: TestClient) -> None:
    response = client.get("/api/chat/conversations/does-not-exist")
    assert response.status_code == 404


def test_order_logistics_tool_path_and_trace(
    client: TestClient,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key", raising=False)
    captured: list[list[dict[str, str]]] = []

    def fake_stream(settings, messages):
        captured.append(messages)
        yield llm.LLMDelta("订单正在运输中，最新动态为已到达杭州转运中心。")
        yield llm.LLMUsage(prompt_tokens=80, completion_tokens=20)

    monkeypatch.setattr(llm, "stream_completion", fake_stream)

    response = client.post(
        "/api/chat/stream",
        json={"message": "查一下订单 QH20261029006 的物流"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    meta = next(data for name, data in events if name == "meta")

    assert meta["mode"] == "agent"
    assert meta["tools"][0]["tool"] == "lookup_shipment"
    assert meta["tools"][0]["status"] == "success"
    assert "业务系统查询结果" in captured[0][-1]["content"]
    assert "在途" in captured[0][-1]["content"]

    conversation = client.get(
        f"/api/chat/conversations/{meta['conversation_id']}"
    ).json()
    assistant = conversation["messages"][-1]
    assert assistant["tool_trace"][0]["label"] == "物流查询"


def test_after_sales_tool_and_knowledge_combination(
    client: TestClient,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key", raising=False)

    source = {
        "chunk_id": 1,
        "document_id": 1,
        "title": "青禾生活售后政策（2026 版）",
        "doc_type": "policy",
        "version": "2026.1",
        "heading": "质量问题处理",
        "content": "签收后十五天内出现非人为质量问题，可以申请换货或退货。",
        "source_name": "synthetic://policy/after-sales-2026",
        "similarity": 0.8,
    }
    monkeypatch.setattr(knowledge, "search_knowledge", lambda *args, **kwargs: [source])

    def fake_stream(settings, messages):
        assert "售后条件判断" in messages[-1]["content"]
        assert "质量问题处理" in messages[-1]["content"]
        yield llm.LLMDelta("按当前条件可以申请售后，但实际退货需要人工创建工单处理 [1]。")
        yield llm.LLMUsage(prompt_tokens=100, completion_tokens=24)

    monkeypatch.setattr(llm, "stream_completion", fake_stream)

    response = client.post(
        "/api/chat/stream",
        json={"message": "订单 QH20261028003 有划痕能退吗？"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    meta = next(data for name, data in events if name == "meta")
    assert meta["mode"] == "agent"
    assert meta["tools"][0]["tool"] == "check_after_sales"
    assert meta["sources"][0]["heading"] == "质量问题处理"


def test_handoff_creates_ticket(client: TestClient) -> None:
    response = client.post(
        "/api/chat/stream",
        json={"message": "我要转人工处理退款"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    meta = next(data for name, data in events if name == "meta")

    assert meta["mode"] == "handoff"
    assert meta["tools"][0]["tool"] == "create_handoff"
    assert meta["tools"][0]["status"] == "success"
    text = "".join(data["text"] for name, data in events if name == "delta")
    assert "人工工单" in text
    assert "转人工" in text or "#" in text

    conversation = client.get(
        f"/api/chat/conversations/{meta['conversation_id']}"
    ).json()
    assert conversation["status"] == "handed_off"


def test_missing_order_and_tool_error_fallbacks(
    client: TestClient,
    monkeypatch,
) -> None:
    missing = client.post(
        "/api/chat/stream",
        json={"message": "我的订单到哪了"},
    )
    missing_events = _parse_sse(missing.text)
    missing_meta = next(data for name, data in missing_events if name == "meta")
    assert missing_meta["mode"] == "clarify"
    assert "请提供订单号" in next(
        data["text"] for name, data in missing_events if name == "delta"
    )

    invalid = client.post(
        "/api/chat/stream",
        json={"message": "订单 QH99999999999 到哪了"},
    )
    invalid_events = _parse_sse(invalid.text)
    invalid_meta = next(data for name, data in invalid_events if name == "meta")
    assert invalid_meta["mode"] == "clarify"
    assert invalid_meta["tools"][0]["status"] == "error"
    assert "没有找到订单" in next(
        data["text"] for name, data in invalid_events if name == "delta"
    )


def test_order_slot_is_filled_from_history(
    client: TestClient,
    monkeypatch,
) -> None:
    first = client.post(
        "/api/chat/stream",
        json={"message": "我的订单到哪了"},
    )
    first_events = _parse_sse(first.text)
    first_meta = next(data for name, data in first_events if name == "meta")
    conversation_id = first_meta["conversation_id"]

    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key", raising=False)

    def fake_stream(settings, messages):
        yield llm.LLMDelta("订单 QH20261029006 的物流正在运输中。")
        yield llm.LLMUsage(prompt_tokens=60, completion_tokens=16)

    monkeypatch.setattr(llm, "stream_completion", fake_stream)

    second = client.post(
        "/api/chat/stream",
        json={"message": "QH20261029006", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    second_events = _parse_sse(second.text)
    second_meta = next(data for name, data in second_events if name == "meta")
    assert second_meta["mode"] == "agent"
    assert second_meta["tools"][0]["tool"] == "lookup_shipment"
    assert second_meta["conversation_id"] == conversation_id
