from fastapi.testclient import TestClient

def test_home_page_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CareerLens" in response.text
    assert 'id="analysis-form"' in response.text
    assert 'id="history-list"' in response.text
    assert 'id="history-dialog"' in response.text


def test_home_page_includes_account_controls(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="auth-gate"' in response.text
    assert 'id="authenticated-app"' in response.text
    assert 'id="auth-dialog"' in response.text
    assert 'id="auth-form"' in response.text
    assert 'id="logout-button"' in response.text
    assert 'autocomplete="current-password"' in response.text


def test_stylesheet_is_served(client: TestClient) -> None:
    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_javascript_is_served(client: TestClient) -> None:
    response = client.get("/static/script.js")

    assert response.status_code == 200
    assert 'apiFetch("/api/analyze"' in response.text
    assert 'apiFetch("/api/auth/me"' in response.text
    assert 'apiFetch("/api/auth/logout"' in response.text
    assert "`/api/auth/${authMode}`" in response.text
    assert "`/api/analyses?page=${page}" in response.text
    assert "`/api/analyses/${analysisId}`" in response.text
    assert "handleExpiredSession()" in response.text


def test_missing_static_file_returns_not_found(client: TestClient) -> None:
    response = client.get("/static/missing.js")

    assert response.status_code == 404


def test_api_documentation_is_not_hidden_by_frontend_routes(
    client: TestClient,
) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_api_routes_are_not_hidden_by_frontend_routes(client: TestClient) -> None:
    response = client.get("/api/analyze")

    assert response.status_code == 405
