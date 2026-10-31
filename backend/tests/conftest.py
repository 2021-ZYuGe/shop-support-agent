from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["SEED_ADMIN_EMAIL"] = "admin@test.local"
os.environ["SEED_ADMIN_PASSWORD"] = "TestPass123!"
os.environ["SEED_ADMIN_NAME"] = "测试管理员"
os.environ["SILICONFLOW_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["CHROMA_PATH"] = "./data/chroma_test"
os.environ["CHROMA_COLLECTION"] = "knowledge_chunks_test"
os.environ["UPLOAD_DIR"] = "./data/test_uploads"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.seed import seed
from app.db.session import engine
from app.main import app

ADMIN_EMAIL = os.environ["SEED_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["SEED_ADMIN_PASSWORD"]


@pytest.fixture(scope="session", autouse=True)
def bootstrap_database() -> None:
    Base.metadata.create_all(bind=engine)
    seed()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client
