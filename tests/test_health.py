from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_200():
    """The liveness endpoint must be available."""
    response = client.get("/health/live")

    assert response.status_code == 200


def test_health_endpoint_returns_expected_data():
    """The endpoint must return the correct health schema."""
    response = client.get("/health/live")

    assert response.json() == {
        "status": "ok",
        "service": "ai-control-plane",
        "version": "0.1.0",
    }


def test_health_endpoint_returns_json():
    """The response must be JSON."""
    response = client.get("/health/live")

    assert response.headers["content-type"] == ("application/json")


def test_unknown_endpoint_returns_404():
    """Unknown API routes must return 404."""
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
