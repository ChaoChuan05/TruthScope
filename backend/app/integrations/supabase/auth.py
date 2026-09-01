from typing import Protocol

import httpx
from pydantic import Field, ValidationError

from app.core.exceptions import AuthenticationError
from app.schemas.common import StrictSchema


class AuthenticatedSupabaseUser(StrictSchema):
    userId: str = Field(min_length=1)


class SupabaseAuthClientProtocol(Protocol):
    async def getUserId(self, accessToken: str) -> str: ...


class SupabaseAuthClient:
    """Validate Supabase user access tokens through the Auth server."""

    def __init__(
        self,
        *,
        baseUrl: str,
        apiKey: str,
        httpClient: httpx.AsyncClient | None = None,
    ) -> None:
        self.apiKey = apiKey
        self._ownsClient = httpClient is None
        self.httpClient = httpClient or httpx.AsyncClient(
            base_url=baseUrl.rstrip("/"),
            timeout=10.0,
            trust_env=False,
        )

    async def getUserId(self, accessToken: str) -> str:
        normalizedToken = accessToken.strip()
        if not normalizedToken:
            raise AuthenticationError("Supabase access token is required.")

        try:
            response = await self.httpClient.get(
                "/auth/v1/user",
                headers={
                    "apikey": self.apiKey,
                    "Authorization": f"Bearer {normalizedToken}",
                    "Accept": "application/json",
                },
            )
        except httpx.RequestError as error:
            raise AuthenticationError(
                "Supabase Auth could not validate the access token."
            ) from error

        if response.status_code in {401, 403}:
            raise AuthenticationError("Supabase access token is invalid or expired.")

        try:
            response.raise_for_status()
            responseBody = response.json()
            if not isinstance(responseBody, dict):
                raise ValueError("Supabase Auth response must be an object.")

            authenticatedUser = AuthenticatedSupabaseUser.model_validate(
                {"userId": responseBody.get("id")}
            )
        except (httpx.HTTPStatusError, ValueError, ValidationError) as error:
            raise AuthenticationError("Supabase Auth returned an invalid response.") from error

        return authenticatedUser.userId

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()
