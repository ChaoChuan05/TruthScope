from app.integrations.supabase.models import SupabaseVerificationPayload
from app.schemas.verification import VerificationResult


def toSupabasePayload(result: VerificationResult) -> SupabaseVerificationPayload:
    return SupabaseVerificationPayload(
        verificationId=result.verificationId,
        ownerUserId=result.userId,
        document=result.model_dump(mode="json", exclude_none=False),
    )


def fromSupabasePayload(payload: SupabaseVerificationPayload) -> VerificationResult:
    result = VerificationResult.model_validate(payload.document)
    result.userId = payload.ownerUserId
    return result
