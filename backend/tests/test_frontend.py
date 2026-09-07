from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_home_page_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CareerLens" in response.text
    assert 'id="analysis-form"' in response.text


def test_stylesheet_is_served() -> None:
    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_javascript_is_served() -> None:
    response = client.get("/static/script.js")

    assert response.status_code == 200
    assert "fetch(\"/api/analyze\"" in response.text


def test_missing_static_file_returns_not_found() -> None:
    response = client.get("/static/missing.js")

    assert response.status_code == 404


def test_api_documentation_is_not_hidden_by_frontend_routes() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_api_routes_are_not_hidden_by_frontend_routes() -> None:
    response = client.get("/api/analyze")

    assert response.status_code == 405
