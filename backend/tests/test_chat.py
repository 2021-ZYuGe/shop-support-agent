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
