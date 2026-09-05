import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from app.core.exceptions import VerificationAccessError, VerificationNotFoundError
from app.schemas.common import utcNow
from app.schemas.verification import VerificationRequest, VerificationResult
from app.schemas.verificationJob import VerificationJob, VerificationJobStatus
from app.services.verificationService import VerificationService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _JobRecord:
    jobId: str
    userId: str
    status: VerificationJobStatus = VerificationJobStatus.QUEUED
    result: VerificationResult | None = None
    errorMessage: str | None = None
    createdAt: datetime = field(default_factory=utcNow)
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    task: asyncio.Task[None] | None = None

    def snapshot(self) -> VerificationJob:
        return VerificationJob(
            jobId=self.jobId,
            status=self.status,
            result=self.result.model_copy(deep=True) if self.result else None,
            errorMessage=self.errorMessage,
            createdAt=self.createdAt,
            startedAt=self.startedAt,
            completedAt=self.completedAt,
        )


class VerificationJobService:
    """Run verifications independently from browser connection lifetime."""

    def __init__(self, verificationService: VerificationService) -> None:
        self.verificationService = verificationService
        self._jobs: dict[str, _JobRecord] = {}
        self._lock = asyncio.Lock()

    async def createJob(
        self,
        request: VerificationRequest,
        userId: str,
    ) -> VerificationJob:
        jobId = str(uuid4())
        record = _JobRecord(jobId=jobId, userId=userId)
        async with self._lock:
            self._jobs[jobId] = record
            record.task = asyncio.create_task(
                self._runJob(record, request),
                name=f"verification-job-{jobId}",
            )
        return record.snapshot()

    async def getJob(self, jobId: str, userId: str) -> VerificationJob:
        async with self._lock:
            record = self._jobs.get(jobId)
            if record is None:
                raise VerificationNotFoundError("Verification job was not found.")
            if record.userId != userId:
                raise VerificationAccessError("Verification job belongs to another user.")
            return record.snapshot()

    async def _runJob(
        self,
        record: _JobRecord,
        request: VerificationRequest,
    ) -> None:
        async with self._lock:
            record.status = VerificationJobStatus.RUNNING
            record.startedAt = utcNow()
        try:
            result = await self.verificationService.verifyClaim(request, record.userId)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception(
                "Verification job failed jobId=%s errorType=%s",
                record.jobId,
                type(error).__name__,
            )
            async with self._lock:
                record.status = VerificationJobStatus.FAILED
                record.errorMessage = "Verification job failed unexpectedly."
                record.completedAt = utcNow()
            return

        async with self._lock:
            record.result = result
            record.status = VerificationJobStatus.COMPLETE
            record.completedAt = utcNow()

    async def close(self) -> None:
        async with self._lock:
            tasks = [record.task for record in self._jobs.values() if record.task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
