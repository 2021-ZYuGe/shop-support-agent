from fastapi.testclient import TestClient


def test_health_reports_database(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["environment"] == "test"
    assert "deepseek" in body["integrations"]


def test_root_lists_health_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/api/health"
