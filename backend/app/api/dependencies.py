from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.integrations.supabase.auth import SupabaseAuthClientProtocol
from app.services.trendingTopicsService import TrendingTopicsService
from app.services.verificationJobService import VerificationJobService
from app.services.verificationService import VerificationService

bearerScheme = HTTPBearer(auto_error=False)


async def getVerificationService(request: Request) -> VerificationService:
    return cast(VerificationService, request.app.state.verificationService)


async def getVerificationJobService(request: Request) -> VerificationJobService:
    return cast(VerificationJobService, request.app.state.verificationJobService)


async def getTrendingTopicsService(request: Request) -> TrendingTopicsService:
    return cast(TrendingTopicsService, request.app.state.trendingTopicsService)


async def getApplicationSettings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def getSupabaseAuthClient(
    request: Request,
) -> SupabaseAuthClientProtocol:
    authClient = getattr(
        request.app.state,
        "supabaseAuthClient",
        None,
    )
    if authClient is None:
        raise AuthenticationError("Supabase authentication is not configured.")
    return cast(SupabaseAuthClientProtocol, authClient)


async def getCurrentUserId(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearerScheme),
    ],
    authClient: Annotated[
        SupabaseAuthClientProtocol,
        Depends(getSupabaseAuthClient),
    ],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Bearer access token is required.")

    return await authClient.getUserId(credentials.credentials)
