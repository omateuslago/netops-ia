"""Contract tests for the Phase 1 API."""

from fastapi.testclient import TestClient

from netops_ai.core.settings import Settings
from netops_ai.main import create_app


def build_client() -> TestClient:
    settings = Settings(environment="test", _env_file=None)
    return TestClient(create_app(settings))


def test_root_describes_entry_points() -> None:
    response = build_client().get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "NetOps AI",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


def test_health_contract() -> None:
    response = build_client().get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "NetOps AI",
        "version": "0.1.0",
        "environment": "test",
    }


def test_openapi_is_available() -> None:
    response = build_client().get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "NetOps AI"
