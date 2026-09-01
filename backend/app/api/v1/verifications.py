from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import getApplicationSettings, getCurrentUserId, getVerificationService
from app.core.config import Settings
from app.schemas.common import StrictSchema
from app.schemas.evidence import EvidenceRecord
from app.schemas.verification import VerificationRequest, VerificationResult
from app.services.verificationService import VerificationService

router = APIRouter(tags=["verifications"])


class HealthResponse(StrictSchema):
    status: str
    gonkaConfigured: bool
    searchConfigured: bool
    persistenceBackend: str


class EvidenceListResponse(StrictSchema):
    verificationId: str
    evidence: list[EvidenceRecord]


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    settings: Annotated[Settings, Depends(getApplicationSettings)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        gonkaConfigured=settings.gonkaConfigured,
        searchConfigured=settings.searchConfigured,
        persistenceBackend=str(request.app.state.persistenceBackend),
    )


@router.post(
    "/verifications",
    response_model=VerificationResult,
    status_code=status.HTTP_201_CREATED,
)
async def createVerification(
    request: VerificationRequest,
    service: Annotated[VerificationService, Depends(getVerificationService)],
    userId: Annotated[str | None, Depends(getCurrentUserId)],
) -> VerificationResult:
    return await service.verifyClaim(request, userId)


@router.get("/verifications/{verificationId}", response_model=VerificationResult)
async def getVerification(
    verificationId: str,
    service: Annotated[VerificationService, Depends(getVerificationService)],
    userId: Annotated[str | None, Depends(getCurrentUserId)],
) -> VerificationResult:
    return await service.getVerification(verificationId, userId)


@router.get(
    "/verifications/{verificationId}/evidence",
    response_model=EvidenceListResponse,
)
async def getVerificationEvidence(
    verificationId: str,
    service: Annotated[VerificationService, Depends(getVerificationService)],
    userId: Annotated[str | None, Depends(getCurrentUserId)],
) -> EvidenceListResponse:
    evidence = await service.getEvidence(verificationId, userId)
    return EvidenceListResponse(verificationId=verificationId, evidence=evidence)
