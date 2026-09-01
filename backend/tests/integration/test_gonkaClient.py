import json

import httpx

from app.core.config import Settings
from app.integrations.gonka.client import (
    GonkaClient,
    inferencePolicy,
    normalizeGonkaBaseUrl,
    retryDelaySeconds,
)


def test_gonkaBaseUrl_acceptsOptionalV1Suffix() -> None:
    assert normalizeGonkaBaseUrl("https://api.gonkarouter.io") == "https://api.gonkarouter.io"
    assert normalizeGonkaBaseUrl("https://api.gonkarouter.io/v1") == "https://api.gonkarouter.io"


def test_retryDelay_honorsProviderRateLimitHeaderWithinBound() -> None:
    request = httpx.Request("POST", "https://api.gonkarouter.io/v1/messages")
    response = httpx.Response(429, headers={"Retry-After": "30"}, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    assert retryDelaySeconds(error, 0) == 30


def test_retryDelay_capsProviderRateLimitHeaderAtSixtySeconds() -> None:
    request = httpx.Request("POST", "https://api.gonkarouter.io/v1/messages")
    response = httpx.Response(429, headers={"Retry-After": "120"}, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    assert retryDelaySeconds(error, 0) == 60


def test_retryDelay_usesDocumentedRateLimitDefaultWithoutHeader() -> None:
    request = httpx.Request("POST", "https://api.gonkarouter.io/v1/messages")
    response = httpx.Response(429, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    assert retryDelaySeconds(error, 0) == 30


def test_inferencePolicy_boundsVerifierButRetriesJudge() -> None:
    settings = Settings(
        _env_file=None,
        GONKA_TIMEOUT_SECONDS=30,
        GONKA_MAX_RETRIES=2,
        GONKA_VERIFIER_TIMEOUT_SECONDS=120,
        GONKA_VERIFIER_MAX_RETRIES=1,
        GONKA_JUDGE_TIMEOUT_SECONDS=75,
        GONKA_JUDGE_MAX_RETRIES=1,
    )
    assert inferencePolicy(settings, "verifierModelB") == (120, 1)
    assert inferencePolicy(settings, "consensusJudge") == (75, 1)
    assert inferencePolicy(settings, "claimExtraction") == (30, 2)


async def test_gonkaClient_normalizesRequestReceiptAndModelMetadata() -> None:
    capturedRequest: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal capturedRequest
        capturedRequest = request
        return httpx.Response(
            200,
            headers={
                "X-Request-Id": "receipt-123",
                "X-Gonka-Fallback": "requested-model -> served-model",
            },
            json={
                "id": "message-123",
                "type": "message",
                "role": "assistant",
                "model": "served-model",
                "content": [{"type": "text", "text": '{"ok":true}'}],
                "usage": {"input_tokens": 10, "output_tokens": 3},
            },
        )

    httpClient = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    )
    settings = Settings(
        GONKA_API_KEY="test-key",
        GONKA_MAX_RETRIES=0,
        GONKA_MAX_TOKENS=1024,
    )
    client = GonkaClient(settings, httpClient=httpClient)
    record = await client.infer(
        taskName="verification",
        model="requested-model",
        systemPrompt="Return JSON.",
        inputPayload={"claim": "test"},
    )
    assert record.requestId == "receipt-123"
    assert record.providerResponseId == "message-123"
    assert record.servedModel == "served-model"
    assert record.fallback == "requested-model -> served-model"
    assert capturedRequest is not None
    assert capturedRequest.headers["x-api-key"] == "test-key"
    assert capturedRequest.url.path == "/v1/messages"
    requestBody = json.loads(capturedRequest.content)
    assert requestBody["messages"][0]["role"] == "user"
    await httpClient.aclose()
