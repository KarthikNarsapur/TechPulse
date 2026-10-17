from fastapi.testclient import TestClient

from app.api import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_technologies_returns_six_initial_groups() -> None:
    response = client.get("/api/v1/technologies")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 6


def test_feed_validates_limit() -> None:
    response = client.get("/api/v1/updates?limit=1000")
    assert response.status_code == 422
