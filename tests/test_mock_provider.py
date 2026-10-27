from fastapi.testclient import TestClient

from app.mock_provider import (
    MOCK_COMPLETION_ID,
    MOCK_CONTENT,
    app,
)

client = TestClient(app)


def valid_request() -> dict:
    return {
        "model": "local-small",
        "messages": [
            {
                "role": "user",
                "content": "Hello, AI!",
            }
        ],
        "stream": False,
    }


def test_mock_provider_health():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mock_provider_returns_completion():
    response = client.post(
        "/v1/chat/completions",
        json=valid_request(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == MOCK_COMPLETION_ID
    assert data["object"] == "chat.completion"
    assert data["model"] == "local-small"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == MOCK_CONTENT
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"] is None


def test_same_request_returns_same_response():
    payload = valid_request()

    first = client.post(
        "/v1/chat/completions",
        json=payload,
    )
    second = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_missing_model_is_rejected():
    payload = valid_request()
    del payload["model"]

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 422


def test_streaming_is_rejected():
    payload = valid_request()
    payload["stream"] = True

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 422


def test_prompt_is_not_echoed():
    payload = valid_request()
    payload["messages"][0]["content"] = "CONFIDENTIAL_TEST_VALUE_123"

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 200
    assert "CONFIDENTIAL_TEST_VALUE_123" not in response.text
