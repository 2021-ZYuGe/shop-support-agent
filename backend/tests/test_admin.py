from fastapi.testclient import TestClient


def test_overview_requires_login(client: TestClient) -> None:
    response = client.get("/api/admin/overview")
    assert response.status_code == 401


def test_overview_contains_seeded_metrics(admin_client: TestClient) -> None:
    response = admin_client.get("/api/admin/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["products"] == 6
    assert body["metrics"]["orders"] == 8
    assert body["metrics"]["knowledge_documents"] == 3
    assert body["metrics"]["knowledge_chunks"] == 9
    assert len(body["recent_orders"]) == 5
    assert body["generated_at"].endswith("+00:00")
    assert body["recent_orders"][0]["placed_at"].endswith("+00:00")
    capability_statuses = {item["status"] for item in body["capabilities"]}
    assert capability_statuses <= {"ready", "pending", "planned"}
    capabilities = {item["key"]: item for item in body["capabilities"]}
    assert capabilities["agent_tools"]["status"] == "ready"
    assert capabilities["security"]["status"] == "ready"
    assert capabilities["delivery"]["status"] == "ready"


def test_orders_endpoint_returns_seed_orders(admin_client: TestClient) -> None:
    response = admin_client.get("/api/admin/orders", params={"limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 8
    assert len(body["items"]) == 3
    assert body["items"][0]["item_count"] >= 1
