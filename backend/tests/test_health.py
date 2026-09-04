"""Tests that do not require a running database or Raspberry Pi hardware."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok():
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
