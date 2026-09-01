from app.integrations.supabase.client import SupabaseVerificationRepository
from app.integrations.supabase.models import SupabaseVerificationPayload
from app.schemas.common import InputType, Verdict, VerificationStatus
from app.schemas.verification import VerificationResult


class FakeGateway:
    def __init__(self) -> None:
        self.payload: SupabaseVerificationPayload | None = None

    async def saveVerification(self, payload: SupabaseVerificationPayload) -> None:
        self.payload = payload

    async def getVerification(self, verificationId: str) -> SupabaseVerificationPayload | None:
        if self.payload and self.payload.verificationId == verificationId:
            return self.payload
        return None


async def test_supabaseAdapter_roundTripsContractWithoutSchemaAssumptions() -> None:
    gateway = FakeGateway()
    repository = SupabaseVerificationRepository(gateway)
    result = VerificationResult(
        verificationId="verification-1",
        requestId="request-1",
        userId="user-1",
        originalInput="Claim",
        inputType=InputType.TEXT,
        normalizedText="Claim",
        verdict=Verdict.MIXED_OR_INCONCLUSIVE,
        promptVersion="v1",
        status=VerificationStatus.INCONCLUSIVE,
    )
    await repository.save(result)
    loaded = await repository.get("verification-1", "user-1")
    assert loaded == result
    assert gateway.payload is not None
    assert gateway.payload.ownerUserId == "user-1"
