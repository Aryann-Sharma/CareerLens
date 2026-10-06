from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app.db.session import get_db
from backend.app.main import app


def test_liveness_check_does_not_require_database(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_check_confirms_database_connection(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_check_reports_database_failure(client: TestClient) -> None:
    original_override = app.dependency_overrides[get_db]

    class UnavailableSession:
        def execute(self, _statement: object) -> None:
            raise SQLAlchemyError("database unavailable")

    def unavailable_database() -> Generator[UnavailableSession, None, None]:
        yield UnavailableSession()

    app.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides[get_db] = original_override

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
