from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_even_without_database() -> None:
    """The API must stay up and report the DB as down rather than 500."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "scoutglobe-api"
    assert body["database"] in {"up", "down", "unknown"}
