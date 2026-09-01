import httpx
from pydantic import ValidationError

from app.core.exceptions import PersistenceUnavailableError
from app.integrations.supabase.models import SupabaseVerificationPayload


class SupabaseRestGateway:
    """Call teammate-owned Supabase RPC functions through PostgREST."""

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

    def _requestHeaders(self) -> dict[str, str]:
        headers = {
            "apikey": self.apiKey,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if not self.apiKey.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.apiKey}"

        return headers

    async def saveVerification(
        self,
        payload: SupabaseVerificationPayload,
    ) -> None:
        if payload.ownerUserId is None:
            raise PersistenceUnavailableError(
                "Supabase could not save a verification without an owner."
            )

        try:
            response = await self.httpClient.post(
                "/rest/v1/rpc/save_verification_result",
                headers=self._requestHeaders(),
                json={
                    "p_user_id": payload.ownerUserId,
                    "p_result": payload.document,
                },
            )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as error:
            raise PersistenceUnavailableError(
                "Supabase could not save the verification."
            ) from error

    async def getVerification(
        self,
        verificationId: str,
    ) -> SupabaseVerificationPayload | None:
        normalizedVerificationId = verificationId.strip()
        if not normalizedVerificationId:
            raise PersistenceUnavailableError(
                "Supabase could not read a verification without an ID."
            )

        try:
            response = await self.httpClient.post(
                "/rest/v1/rpc/get_verification_result",
                headers=self._requestHeaders(),
                json={
                    "p_verification_id": normalizedVerificationId,
                },
            )
            response.raise_for_status()

            if not response.content:
                return None

            responseBody = response.json()
            if responseBody is None:
                return None

            if responseBody is None:
                return None
            if not isinstance(responseBody, dict):
                raise ValueError("Supabase read response must be an object.")

            return SupabaseVerificationPayload.model_validate(responseBody)
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            ValueError,
            ValidationError,
        ) as error:
            raise PersistenceUnavailableError(
                "Supabase could not read the verification."
            ) from error

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()
