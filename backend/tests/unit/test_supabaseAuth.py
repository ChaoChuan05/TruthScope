import httpx
import pytest

from app.core.exceptions import AuthenticationError
from app.integrations.supabase.auth import SupabaseAuthClient


async def test_supabaseAuthClient_returnsVerifiedUserId() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        assert request.headers["apikey"] == "test-secret-key"
        assert request.headers["Authorization"] == "Bearer valid-user-token"
        return httpx.Response(
            200,
            json={
                "id": "user-123",
                "email": "person@example.com",
            },
        )

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        authClient = SupabaseAuthClient(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )
        userId = await authClient.getUserId("valid-user-token")

    assert userId == "user-123"


async def test_supabaseAuthClient_rejectsInvalidToken() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        return httpx.Response(
            401,
            json={"message": "Invalid JWT"},
        )

    async with httpx.AsyncClient(
        base_url="https://example.supabase.co",
        transport=httpx.MockTransport(handler),
    ) as httpClient:
        authClient = SupabaseAuthClient(
            baseUrl="https://example.supabase.co",
            apiKey="test-secret-key",
            httpClient=httpClient,
        )

        with pytest.raises(
            AuthenticationError,
            match="invalid or expired",
        ):
            await authClient.getUserId("invalid-user-token")
