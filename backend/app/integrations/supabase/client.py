import asyncio
from typing import Protocol

from app.core.exceptions import VerificationAccessError, VerificationNotFoundError
from app.integrations.supabase.mapper import fromSupabasePayload, toSupabasePayload
from app.integrations.supabase.models import SupabaseVerificationPayload
from app.schemas.verification import VerificationResult


class VerificationRepositoryProtocol(Protocol):
    async def save(self, result: VerificationResult) -> None: ...

    async def get(
        self,
        verificationId: str,
        requestingUserId: str | None,
    ) -> VerificationResult: ...


class SupabaseGatewayProtocol(Protocol):
    """Teammate-supplied API contract; deliberately contains no table or RPC names."""

    async def saveVerification(self, payload: SupabaseVerificationPayload) -> None: ...

    async def getVerification(self, verificationId: str) -> SupabaseVerificationPayload | None: ...


def enforceOwnership(result: VerificationResult, requestingUserId: str | None) -> None:
    if result.userId is not None and result.userId != requestingUserId:
        raise VerificationAccessError("Verification belongs to another user.")


class InMemoryVerificationRepository:
    """Process-local repository for development and contract tests."""

    def __init__(self) -> None:
        self._records: dict[str, VerificationResult] = {}
        self._lock = asyncio.Lock()

    async def save(self, result: VerificationResult) -> None:
        async with self._lock:
            self._records[result.verificationId] = result.model_copy(deep=True)

    async def get(
        self,
        verificationId: str,
        requestingUserId: str | None,
    ) -> VerificationResult:
        async with self._lock:
            result = self._records.get(verificationId)
            if result is None:
                raise VerificationNotFoundError("Verification was not found.")
            resultCopy = result.model_copy(deep=True)
        enforceOwnership(resultCopy, requestingUserId)
        return resultCopy


class SupabaseVerificationRepository:
    """Adapter around teammate-owned gateway without assuming database schema."""

    def __init__(self, gateway: SupabaseGatewayProtocol) -> None:
        self.gateway = gateway

    async def save(self, result: VerificationResult) -> None:
        await self.gateway.saveVerification(toSupabasePayload(result))

    async def get(
        self,
        verificationId: str,
        requestingUserId: str | None,
    ) -> VerificationResult:
        payload = await self.gateway.getVerification(verificationId)
        if payload is None:
            raise VerificationNotFoundError("Verification was not found.")
        result = fromSupabasePayload(payload)
        enforceOwnership(result, requestingUserId)
        return result
