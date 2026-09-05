import json
import logging

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import GonkaUnavailableError
from app.integrations.gonka.client import (
    GonkaClient,
    inferencePolicy,
    normalizeGonkaBaseUrl,
    normalizeToolSchema,
    retryDelaySeconds,
)


def test_gonkaBaseUrl_acceptsOptionalV1Suffix() -> None:
    assert normalizeGonkaBaseUrl("https://api.gonkarouter.io") == "https://api.gonkarouter.io"
    assert normalizeGonkaBaseUrl("https://api.gonkarouter.io/v1") == "https://api.gonkarouter.io"


async def test_gonkaClient_rejectsProviderIncompatibleTokenOverride() -> None:
    async with httpx.AsyncClient(base_url="https://api.gonkarouter.io") as httpClient:
        client = GonkaClient(Settings(GONKA_API_KEY="test-key"), httpClient=httpClient)
        with pytest.raises(ValueError, match="between 1024 and 4096"):
            await client.infer(
                taskName="contextAnalysis",
                model="requested-model",
                systemPrompt="Return JSON.",
                inputPayload={"claim": "test"},
                maxTokens=128,
            )


def test_normalizeToolSchema_inlinesDefinitionsAndRemovesAnnotations() -> None:
    schema = {
        "$defs": {
            "Result": {
                "title": "Result",
                "type": "object",
                "properties": {
                    "status": {
                        "$ref": "#/$defs/Status",
                    }
                },
                "required": ["status"],
            },
            "Status": {
                "title": "Status",
                "type": "string",
                "enum": ["ok", "failed"],
            },
        },
        "title": "Envelope",
        "type": "object",
        "properties": {
            "result": {"$ref": "#/$defs/Result"},
            "optional": {"default": None, "type": "string"},
        },
    }

    assert normalizeToolSchema(schema) == {
        "type": "object",
        "properties": {
            "result": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["ok", "failed"],
                    }
                },
                "required": ["status"],
            },
            "optional": {"type": "string"},
        },
    }


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
    assert inferencePolicy(settings, "biasAudit") == (60, 1)
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
    assert record.stopReason is None
    assert capturedRequest is not None
    assert capturedRequest.headers["x-api-key"] == "test-key"
    assert capturedRequest.url.path == "/v1/messages"
    requestBody = json.loads(capturedRequest.content)
    assert requestBody["messages"][0]["role"] == "user"
    await httpClient.aclose()


async def test_gonkaClient_usesForcedToolForStructuredRepair() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        requestBody = json.loads(request.content)
        assert requestBody["tool_choice"] == {
            "type": "tool",
            "name": "submit_structured_output",
        }
        assert requestBody["tools"][0]["input_schema"] == {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        }
        return httpx.Response(
            200,
            json={
                "id": "message-tool",
                "model": "served-model",
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "submit_structured_output",
                        "input": {"ok": True},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(Settings(GONKA_API_KEY="test-key"), httpClient=httpClient)
        record = await client.infer(
            taskName="verifierModelA",
            model="requested-model",
            systemPrompt="Return structured output.",
            inputPayload={"claim": "test"},
            outputSchema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
        )

    assert json.loads(record.outputText) == {"ok": True}
    assert record.stopReason == "tool_use"


async def test_gonkaClient_fallsBackToPlainJsonWhenToolRequestIsRejected(
    caplog,
) -> None:
    requestBodies: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requestBody = json.loads(request.content)
        requestBodies.append(requestBody)
        if len(requestBodies) == 1:
            return httpx.Response(
                400,
                json={"error": {"type": "invalid_request_error", "message": "unsupported"}},
            )
        return httpx.Response(
            200,
            headers={"X-Request-Id": "receipt-plain-json"},
            json={
                "id": "message-plain-json",
                "model": "served-model",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": '{"ok":true}'}],
            },
        )

    caplog.set_level(logging.WARNING, logger="app.integrations.gonka.client")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(
            Settings(GONKA_API_KEY="test-key", GONKA_VERIFIER_MAX_RETRIES=0),
            httpClient=httpClient,
        )
        record = await client.infer(
            taskName="verifierModelA",
            model="requested-model",
            systemPrompt="Return structured output.",
            inputPayload={"claim": "test"},
            applicationRequestId="application-request-123",
            outputSchema={
                "$defs": {"Boolean": {"title": "Boolean", "type": "boolean"}},
                "type": "object",
                "properties": {"ok": {"$ref": "#/$defs/Boolean"}},
                "required": ["ok"],
            },
        )

    assert len(requestBodies) == 2
    firstTool = requestBodies[0]["tools"]
    assert isinstance(firstTool, list)
    assert firstTool[0]["input_schema"] == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }
    assert "tools" not in requestBodies[1]
    assert "tool_choice" not in requestBodies[1]
    assert json.loads(record.outputText) == {"ok": True}
    assert record.requestId == "receipt-plain-json"
    assert "providerErrorType=invalid_request_error" in caplog.text
    assert "retryingWithoutTool=True" in caplog.text


async def test_gonkaClient_preservesReceiptForMissingStructuredToolOutput() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"X-Request-Id": "receipt-empty-tool"},
            json={
                "id": "message-empty-tool",
                "model": "served-model",
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "wrong_tool",
                        "input": {"ok": True},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(Settings(GONKA_API_KEY="test-key"), httpClient=httpClient)
        record = await client.infer(
            taskName="verifierModelA",
            model="requested-model",
            systemPrompt="Return structured output.",
            inputPayload={"claim": "test"},
            outputSchema={"type": "object"},
        )

    assert record.requestId == "receipt-empty-tool"
    assert record.outputText == ""


async def test_gonkaClient_rejectsAmbiguousMultipleStructuredToolOutputs() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "id": "message-multiple-tools",
                "model": "served-model",
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "submit_structured_output",
                        "input": {"ok": True},
                    },
                    {
                        "type": "tool_use",
                        "name": "submit_structured_output",
                        "input": {"ok": False},
                    },
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(Settings(GONKA_API_KEY="test-key"), httpClient=httpClient)
        record = await client.infer(
            taskName="verifierModelA",
            model="requested-model",
            systemPrompt="Return structured output.",
            inputPayload={"claim": "test"},
            outputSchema={"type": "object"},
        )

    assert record.outputText == ""


async def test_gonkaClient_retriesReadTimeoutWithRequestCorrelation(
    monkeypatch,
    caplog,
) -> None:
    callCount = 0

    async def noSleep(_: float) -> None:
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal callCount
        callCount += 1
        if callCount == 1:
            raise httpx.ReadTimeout("provider slow", request=request)
        return httpx.Response(
            200,
            json={
                "id": "message-retry",
                "model": "served-model",
                "content": [{"type": "text", "text": '{"ok":true}'}],
            },
        )

    monkeypatch.setattr("app.integrations.gonka.client.asyncio.sleep", noSleep)
    caplog.set_level(logging.INFO, logger="app.integrations.gonka.client")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(
            Settings(
                GONKA_API_KEY="test-key",
                GONKA_AUDIT_MAX_RETRIES=1,
            ),
            httpClient=httpClient,
        )
        record = await client.infer(
            taskName="biasAudit",
            model="requested-model",
            systemPrompt="Return JSON.",
            inputPayload={"claim": "test"},
            applicationRequestId="application-request-123",
        )

    assert callCount == 2
    assert record.providerResponseId == "message-retry"
    assert "requestId=application-request-123" in caplog.text
    assert "willRetry=True" in caplog.text


async def test_gonkaClient_exhaustsReadTimeoutRetriesWithinConfiguredBound(
    monkeypatch,
    caplog,
) -> None:
    callCount = 0

    async def noSleep(_: float) -> None:
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal callCount
        callCount += 1
        raise httpx.ReadTimeout("provider slow", request=request)

    monkeypatch.setattr("app.integrations.gonka.client.asyncio.sleep", noSleep)
    caplog.set_level(logging.INFO, logger="app.integrations.gonka.client")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(
            Settings(GONKA_API_KEY="test-key", GONKA_AUDIT_MAX_RETRIES=1),
            httpClient=httpClient,
        )
        with pytest.raises(GonkaUnavailableError):
            await client.infer(
                taskName="biasAudit",
                model="requested-model",
                systemPrompt="Return JSON.",
                inputPayload={"claim": "test"},
                applicationRequestId="application-request-123",
            )

    assert callCount == 2
    assert "attempt=2" in caplog.text
    assert "willRetry=False" in caplog.text


async def test_gonkaClient_logsProviderReceiptForTransientHttpFailure(
    monkeypatch,
    caplog,
) -> None:
    async def noSleep(_: float) -> None:
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            headers={"X-Request-Id": "failed-provider-receipt"},
            request=request,
        )

    monkeypatch.setattr("app.integrations.gonka.client.asyncio.sleep", noSleep)
    caplog.set_level(logging.INFO, logger="app.integrations.gonka.client")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.gonkarouter.io",
    ) as httpClient:
        client = GonkaClient(
            Settings(GONKA_API_KEY="test-key", GONKA_AUDIT_MAX_RETRIES=0),
            httpClient=httpClient,
        )
        with pytest.raises(GonkaUnavailableError):
            await client.infer(
                taskName="biasAudit",
                model="requested-model",
                systemPrompt="Return JSON.",
                inputPayload={"claim": "test"},
            )

    assert "providerRequestId=failed-provider-receipt" in caplog.text
