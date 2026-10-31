from fastapi.testclient import TestClient

from app.services.knowledge import chunk_document


def test_chunk_document_respects_length_and_heading() -> None:
    text = (
        "# 七天无理由退货\n\n"
        + "消费者签收商品之日起七天内，在商品完好、不影响二次销售的前提下，可以申请无理由退货。"
        * 12
        + "\n\n# 退款时效\n\n退货商品完成签收和质检后，退款将在三个工作日内原路退回。"
    )
    chunks = chunk_document(text, max_chars=240, overlap=40)

    assert len(chunks) >= 3
    assert all(len(content) <= 240 for _, content in chunks)
    assert {heading for heading, _ in chunks} == {"七天无理由退货", "退款时效"}


def test_knowledge_requires_login(client: TestClient) -> None:
    response = client.get("/api/admin/knowledge/documents")
    assert response.status_code == 401


def test_list_seeded_knowledge_documents(admin_client: TestClient) -> None:
    response = admin_client.get("/api/admin/knowledge/documents")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["documents"] == 3
    assert body["summary"]["chunks"] == 9
    assert body["summary"]["indexed_chunks"] == 0
    assert body["summary"]["pending_chunks"] == 9
    assert all(item["index_status"] == "pending" for item in body["items"])


def test_upload_markdown_document(admin_client: TestClient) -> None:
    content = (
        "# 发货时效\n\n"
        "现货商品通常在付款后四十八小时内发出。大促期间订单量较大，"
        "发货时间可能延长至七十二小时。\n\n"
        "# 物流异常\n\n"
        "若物流信息超过四十八小时未更新，请联系人工客服协助核查。"
    )
    response = admin_client.post(
        "/api/admin/knowledge/documents",
        data={
            "title": "测试发货说明",
            "doc_type": "logistics",
            "version": "1.0",
            "effective_date": "2026-10-01",
        },
        files={
            "file": (
                "test-shipping.md",
                content.encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "测试发货说明"
    assert body["chunk_count"] >= 2
    assert body["pending_count"] == body["chunk_count"]
    assert body["index_status"] == "pending"

    listing = admin_client.get("/api/admin/knowledge/documents")
    assert listing.status_code == 200
    assert listing.json()["summary"]["documents"] == 4


def test_index_and_search_require_embedding_key(admin_client: TestClient) -> None:
    index_response = admin_client.post("/api/admin/knowledge/documents/1/index")
    assert index_response.status_code == 503
    assert "SILICONFLOW_API_KEY" in index_response.json()["detail"]

    search_response = admin_client.get(
        "/api/admin/knowledge/search",
        params={"q": "退货政策是什么", "top_k": 3},
    )
    assert search_response.status_code == 503
    assert "SILICONFLOW_API_KEY" in search_response.json()["detail"]
