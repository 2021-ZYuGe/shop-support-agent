from __future__ import annotations

from app.core.config import get_settings
from app.services import chat, rerank


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.text = ""

    def json(self) -> dict:
        return self.payload


def test_rerank_sorts_by_relevance(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "siliconflow_api_key", "test-key", raising=False)
    captured: dict = {}

    def fake_post(url, headers, json, timeout):
        captured.update(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeResponse(
            {
                "results": [
                    {"index": 0, "relevance_score": 0.21},
                    {"index": 1, "relevance_score": 0.93},
                ]
            }
        )

    monkeypatch.setattr(rerank.httpx, "post", fake_post)
    client = rerank.SiliconFlowRerankClient(settings)
    hits = client.rerank(
        "七天无理由退货",
        ["签收后七天内可以申请退货。", "会员积分可以抵扣。"],
        top_n=2,
    )

    assert [hit.index for hit in hits] == [1, 0]
    assert hits[0].score == 0.93
    assert captured["url"].endswith("/rerank")
    assert captured["json"]["model"] == settings.rerank_model


def test_prompt_v2_has_bounded_answer_instruction() -> None:
    messages = chat.build_llm_messages(
        [],
        [
            {
                "title": "测试政策",
                "heading": "退货",
                "content": "签收后七天内可以申请退货。",
                "doc_type": "policy",
                "version": "1.0",
            }
        ],
        "可以退货吗？",
        prompt_version="v2",
    )
    assert "300 字" in messages[0]["content"]
    assert "参考资料" in messages[-1]["content"]
