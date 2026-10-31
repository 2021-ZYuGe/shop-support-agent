from fastapi.testclient import TestClient

ADMIN_EMAIL = "admin@test.local"
ADMIN_PASSWORD = "TestPass123!"


def test_login_rejects_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "邮箱或密码错误"


def test_login_me_logout_flow(client: TestClient) -> None:
    unauthorized = client.get("/api/auth/me")
    assert unauthorized.status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["admin"]["email"] == ADMIN_EMAIL
    assert "shop_support_session" in login.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "测试管理员"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    after_logout = client.get("/api/auth/me")
    assert after_logout.status_code == 401
