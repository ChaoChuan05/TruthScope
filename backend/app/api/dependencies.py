from typing import Annotated, cast

from fastapi import Header, Request

from app.core.config import Settings
from app.services.verificationService import VerificationService


async def getVerificationService(request: Request) -> VerificationService:
    return cast(VerificationService, request.app.state.verificationService)


async def getApplicationSettings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def getCurrentUserId(
    xUserId: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str | None:
    """OAuth boundary placeholder; production must replace trusted-header identity."""

    if xUserId is None:
        return None
    normalizedUserId = xUserId.strip()
    if not normalizedUserId or len(normalizedUserId) > 200:
        return None
    return normalizedUserId
