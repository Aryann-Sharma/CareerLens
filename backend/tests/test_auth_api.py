import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.user import User
from backend.app.services.passwords import verify_password
from backend.app.services.sessions import SESSION_COOKIE_NAME

EMAIL = "student@example.com"
PASSWORD = "Correct-Horse-27"


def register(client: TestClient, email: str = EMAIL) -> Response:
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD},
    )


def test_register_creates_user_and_starts_session(
    client: TestClient,
    db_session: Session,
) -> None:
    response = register(client, "Student@Example.COM")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["email"] == EMAIL
    assert "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body

    user = db_session.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash)

    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_register_rejects_duplicate_email_case_insensitively(
    client: TestClient,
) -> None:
    assert register(client, "Student@Example.COM").status_code == 201

    response = register(client, EMAIL)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "An account with this email already exists"
    }


def test_production_session_cookie_is_secure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_SECRET_KEY", "x" * 64)
    get_settings.cache_clear()

    try:
        response = register(client)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 201
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": EMAIL, "password": "too-short"},
        {"email": EMAIL, "password": "x" * 129},
        {"email": EMAIL, "password": PASSWORD, "role": "admin"},
    ],
)
def test_register_rejects_invalid_input(
    client: TestClient,
    payload: dict[str, str],
) -> None:
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422


def test_login_starts_session_and_current_user_returns_account(
    client: TestClient,
) -> None:
    registered = register(client)
    user_id = registered.json()["id"]
    client.cookies.clear()

    login = client.post(
        "/api/auth/login",
        json={"email": "STUDENT@example.com", "password": PASSWORD},
    )

    assert login.status_code == 200
    assert login.json()["id"] == user_id
    assert SESSION_COOKIE_NAME in client.cookies

    current_user = client.get("/api/auth/me")
    assert current_user.status_code == 200
    assert current_user.json()["id"] == user_id
    assert current_user.json()["email"] == EMAIL


def test_login_uses_same_error_for_wrong_password_and_unknown_email(
    client: TestClient,
) -> None:
    register(client)
    client.cookies.clear()

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": EMAIL, "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": PASSWORD},
    )

    expected = {"detail": "Invalid email or password"}
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == expected
    assert unknown_email.json() == expected


def test_current_user_requires_valid_session(client: TestClient) -> None:
    missing_cookie = client.get("/api/auth/me")

    client.cookies.set(SESSION_COOKIE_NAME, "tampered-token")
    tampered_cookie = client.get("/api/auth/me")

    assert missing_cookie.status_code == 401
    assert tampered_cookie.status_code == 401
    assert missing_cookie.json() == {"detail": "Not authenticated"}
    assert tampered_cookie.json() == {"detail": "Not authenticated"}


def test_session_for_deleted_user_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    register(client)
    user = db_session.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    db_session.delete(user)
    db_session.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    register(client)
    assert client.get("/api/auth/me").status_code == 200

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 204
    assert logout.content == b""
    assert client.get("/api/auth/me").status_code == 401


def test_authentication_routes_are_documented(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "post" in paths["/api/auth/register"]
    assert "post" in paths["/api/auth/login"]
    assert "post" in paths["/api/auth/logout"]
    assert "get" in paths["/api/auth/me"]
