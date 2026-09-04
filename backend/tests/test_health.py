"""Health-endpoint tests without a real database or Raspberry Pi hardware."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import create_app
from app.routes import health


def test_health_endpoint_returns_ok():
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_endpoint_returns_connected_with_working_connection(monkeypatch):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, _exception_type, _exception, _traceback):
            return False

        def execute(self, statement):
            assert str(statement) == "SELECT 1"

    class Engine:
        def connect(self):
            return Connection()

    monkeypatch.setattr(health, "engine", Engine())

    with TestClient(create_app()) as client:
        response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_database_health_endpoint_hides_connection_error(monkeypatch):
    class Engine:
        def connect(self):
            raise SQLAlchemyError("connection details must not be returned")

    monkeypatch.setattr(health, "engine", Engine())

    with TestClient(create_app()) as client:
        response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
