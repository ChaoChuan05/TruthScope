from pydantic import Field

from app.schemas.common import StrictSchema


class SupabaseVerificationPayload(StrictSchema):
    """Contract-neutral payload passed to the teammate-owned gateway."""

    verificationId: str
    ownerUserId: str | None = None
    document: dict[str, object] = Field(default_factory=dict)
