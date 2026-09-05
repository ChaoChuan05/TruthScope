import json
import logging

import httpx
import pytest

from app.core.exceptions import PersistenceUnavailableError
from app.integrations.supabase.gateway import SupabaseRestGateway
from app.integrations.supabase.models import SupabaseVerificationPayload


def buildPayload() -> SupabaseVerificationPayload:
    return SupabaseVerificationPayload(
        verificationId="verification-123",
        ownerUserId="user-123",
        document={
            "verificationId": "verification-123",
            "userId": "user-123",
            "input": "The measured value was 42 units.",
        },
    )


async def test_supabaseRestGateway_callsSaveRpc() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/rpc/save_verification_result"
        assert request.headers["apikey"] == "test-secret-key"
        assert request.headers["Authorization"] == "Bearer test-secret-key"
        assert json.loads(request.content) == {
            "p_user_id": "user-123",
            "p_result": {
                "verificationId": "verification-123",
                "userId": "user-123",
                "input": "The measured value was 42 units.",
            },
        }
        return httpx.Response(204)

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )
        await gateway.saveVerification(buildPayload())


async def test_supabaseRestGateway_convertsSaveFailure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            503,
            json={"message": "Database unavailable"},
        )

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )

        with pytest.raises(
            PersistenceUnavailableError,
            match="could not save",
        ):
            await gateway.saveVerification(buildPayload())


async def test_supabaseRestGateway_logsSafeConflictMetadata(caplog) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            409,
            json={
                "code": "23505",
                "message": (
                    "duplicate key value violates unique constraint "
                    '"model_inferences_run_id_external_claim_id_model_name_key"'
                ),
                "details": "Sensitive row details must not be logged.",
            },
        )

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )

        with (
            caplog.at_level(logging.WARNING, logger="app.integrations.supabase.gateway"),
            pytest.raises(PersistenceUnavailableError),
        ):
            await gateway.saveVerification(buildPayload())

    assert "statusCode=409" in caplog.text
    assert "databaseCode=23505" in caplog.text
    assert "model_inferences_run_id_external_claim_id_model_name_key" in caplog.text
    assert "Sensitive row details" not in caplog.text


async def test_supabaseRestGateway_getsVerification() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/rest/v1/rpc/get_verification_result"
        assert request.headers["apikey"] == "test-secret-key"
        assert request.headers["Authorization"] == "Bearer test-secret-key"
        assert json.loads(request.content) == {"p_verification_id": "verification-123"}
        return httpx.Response(
            200,
            json={
                "verificationId": "verification-123",
                "ownerUserId": "user-123",
                "document": {
                    "verificationId": "verification-123",
                    "userId": "user-123",
                    "input": "The measured value was 42 units.",
                },
            },
        )

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )
        payload = await gateway.getVerification("verification-123")

    assert payload == buildPayload()


async def test_supabaseRestGateway_returnsNoneWhenVerificationIsMissing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/get_verification_result"
        return httpx.Response(200, json=None)

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )
        payload = await gateway.getVerification("missing-verification")

    assert payload is None


async def test_supabaseRestGateway_convertsReadFailure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            503,
            json={"message": "Database unavailable"},
        )

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )

        with pytest.raises(
            PersistenceUnavailableError,
            match="could not read",
        ):
            await gateway.getVerification("verification-123")


async def test_supabaseRestGateway_usesOpaqueSecretAsApiKeyOnly() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "sb_secret_test-value"
        assert "Authorization" not in request.headers
        return httpx.Response(204)

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        gateway = SupabaseRestGateway(
            baseUrl="https://example.supabase.co",
            apiKey="sb_secret_test-value",
            httpClient=httpClient,
        )
        await gateway.saveVerification(buildPayload())
