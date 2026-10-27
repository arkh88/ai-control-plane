import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ChatCompletionResponse

client = TestClient(app)


def valid_request() -> dict:
    return {
        "model": "local-small",
        "messages": [
            {
                "role": "user",
                "content": "Hello!",
            }
        ],
        "stream": False,
    }


def test_valid_request_reaches_mock_provider(
    use_mock_provider,
):
    from app.main import app
    from app.provider_client import get_provider_client

    # Verify the test fixture installed the override.
    assert get_provider_client in app.dependency_overrides, (
        "Mock provider dependency override is missing"
    )

    response = client.post(
        "/v1/chat/completions",
        json=valid_request(),
    )

    print("Status:", response.status_code)
    print("Response:", response.json())

    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "local-small"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "deterministic mock response" in (data["choices"][0]["message"]["content"])


def test_missing_model_is_rejected():
    payload = valid_request()
    del payload["model"]

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "role",
    ["administrator", "tool", "unknown"],
)
def test_unsupported_roles_are_rejected(role):
    payload = valid_request()
    payload["messages"][0]["role"] = role

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 422


def test_empty_messages_are_rejected():
    payload = valid_request()
    payload["messages"] = []

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


def test_unexpected_fields_are_rejected():
    payload = valid_request()
    payload["application_id"] = "admin"

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 422


def test_response_schema():
    response = ChatCompletionResponse(
        id="chatcmpl-test",
        created=1793000000,
        model="local-small",
        choices=[
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello!",
                },
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        },
    )

    assert response.object == "chat.completion"
    assert response.choices[0].message.role == "assistant"
