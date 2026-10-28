"""Tests for the OPA HTTP policy client."""

import asyncio
import json

import httpx
import pytest

from app.policy_client import (
    OPA_DECISION_PATH,
    PolicyClientError,
    evaluate_model_access,
)


def opa_response(allow: bool, reason: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "result": {
                "allow": allow,
                "reason": reason,
            }
        },
    )


def evaluate_with_handler(
    handler,
    application_id="demo-app",
    model_id="local-small",
):
    """Run the async policy client using mock HTTP transport."""

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://opa:8181",
            trust_env=False,
        ) as client:
            return await evaluate_model_access(
                client=client,
                application_id=application_id,
                model_id=model_id,
            )

    return asyncio.run(run())


# 1. A valid allow decision returns a typed result.
def test_valid_allow_decision():
    requests = []

    def handler(request):
        requests.append(request)
        return opa_response(True, "ALLOW")

    result = evaluate_with_handler(handler)

    assert result.allow is True
    assert result.reason == "ALLOW"

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == OPA_DECISION_PATH
    assert requests[0].url.host == "opa"

    assert json.loads(requests[0].content) == {
        "input": {
            "application_id": "demo-app",
            "model_id": "local-small",
        }
    }


# 2. A valid denial is preserved, not treated as an error.
def test_valid_deny_decision():
    def handler(request):
        return opa_response(False, "MODEL_NOT_ALLOWED")

    result = evaluate_with_handler(
        handler,
        application_id="demo-app",
        model_id="restricted-small",
    )

    assert result.allow is False
    assert result.reason == "MODEL_NOT_ALLOWED"


# 3. OPA HTTP errors fail closed.
def test_upstream_http_error():
    def handler(request):
        return httpx.Response(503, json={"error": "unavailable"})

    with pytest.raises(
        PolicyClientError,
        match="service unavailable",
    ):
        evaluate_with_handler(handler)


# 4. OPA timeouts fail closed.
def test_opa_timeout():
    def handler(request):
        raise httpx.ReadTimeout(
            "Simulated timeout",
            request=request,
        )

    with pytest.raises(
        PolicyClientError,
        match="timed out",
    ):
        evaluate_with_handler(handler)


# 5. Network connection errors fail closed.
def test_opa_connection_error():
    def handler(request):
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    with pytest.raises(
        PolicyClientError,
        match="service unavailable",
    ):
        evaluate_with_handler(handler)


# 6. Invalid JSON is rejected.
def test_invalid_json():
    def handler(request):
        return httpx.Response(
            200,
            content=b"not valid json",
            headers={"content-type": "application/json"},
        )

    with pytest.raises(
        PolicyClientError,
        match="invalid policy decision",
    ):
        evaluate_with_handler(handler)


# 7. HTTP 200 with no result must not grant access.
def test_missing_result_fails_closed():
    def handler(request):
        return httpx.Response(200, json={})

    with pytest.raises(
        PolicyClientError,
        match="invalid policy decision",
    ):
        evaluate_with_handler(handler)


# 8. A string is not an acceptable boolean decision.
def test_non_boolean_allow_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "result": {
                    "allow": "true",
                    "reason": "ALLOW",
                }
            },
        )

    with pytest.raises(
        PolicyClientError,
        match="invalid policy decision",
    ):
        evaluate_with_handler(handler)


# 9. Unknown reason codes are rejected.
def test_unknown_reason_rejected():
    def handler(request):
        return opa_response(True, "SOME_UNKNOWN_REASON")

    with pytest.raises(
        PolicyClientError,
        match="invalid policy decision",
    ):
        evaluate_with_handler(handler)


# 10. Contradictory decisions are rejected.
def test_inconsistent_decision_rejected():
    def handler(request):
        return opa_response(True, "MODEL_NOT_ALLOWED")

    with pytest.raises(
        PolicyClientError,
        match="invalid policy decision",
    ):
        evaluate_with_handler(handler)
