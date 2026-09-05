from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import StrictSchema, utcNow
from app.schemas.verification import VerificationResult


class VerificationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class VerificationJob(StrictSchema):
    jobId: str
    status: VerificationJobStatus
    result: VerificationResult | None = None
    errorMessage: str | None = None
    createdAt: datetime = Field(default_factory=utcNow)
    startedAt: datetime | None = None
    completedAt: datetime | None = None
