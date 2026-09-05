import logging
from uuid import uuid4

from app.agents.graph import PROMPT_VERSION, VerificationWorkflow
from app.agents.state import VerificationGraphState
from app.integrations.supabase.client import VerificationRepositoryProtocol
from app.schemas.agentOutput import WorkflowError
from app.schemas.common import InputType, VerificationStatus, utcNow
from app.schemas.evidence import EvidenceRecord
from app.schemas.verification import VerificationRequest, VerificationResult

logger = logging.getLogger(__name__)


class VerificationService:
    """Coordinate graph execution and persistence outside HTTP routes."""

    def __init__(
        self,
        workflow: VerificationWorkflow,
        repository: VerificationRepositoryProtocol,
    ) -> None:
        self.workflow = workflow
        self.repository = repository

    async def verifyClaim(
        self,
        request: VerificationRequest,
        userId: str | None = None,
    ) -> VerificationResult:
        requestId = str(uuid4())
        verificationId = str(uuid4())
        initialState = VerificationGraphState(
            requestId=requestId,
            verificationId=verificationId,
            userId=userId,
            originalInput=request.input,
            inputType=request.inputType or InputType.TEXT,
            outputLanguage=request.outputLanguage,
            analysisInput=request.input,
            sourceDocument=None,
            normalizedText=request.input,
            createdAt=utcNow(),
            claims=[],
            evidenceQueries=[],
            evidence=[],
            contextAnalysis=None,
            agentAnalyses=[],
            judgeResult=None,
            biasAudit=None,
            biasRetryCount=0,
            score=None,
            inferenceRecords=[],
            gonkaRequestIds=[],
            warnings=[],
            limitations=[],
            errors=[],
            promptVersion=PROMPT_VERSION,
        )
        finalState = await self.workflow.run(initialState)
        result = finalState["result"]
        try:
            await self.repository.save(result)
        except Exception as error:
            logger.warning(
                "Verification persistence failed requestId=%s verificationId=%s errorType=%s",
                result.requestId,
                result.verificationId,
                type(error).__name__,
            )
            result.status = VerificationStatus.DEGRADED
            result.warnings.append("Verification completed but could not be saved.")
            result.errors.append(
                WorkflowError(
                    code="PERSISTENCE_UNAVAILABLE",
                    stage="persistence",
                    message="Verification persistence was unavailable.",
                    retryable=True,
                )
            )
        return result

    async def getVerification(
        self,
        verificationId: str,
        userId: str | None,
    ) -> VerificationResult:
        return await self.repository.get(verificationId, userId)

    async def getEvidence(
        self,
        verificationId: str,
        userId: str | None,
    ) -> list[EvidenceRecord]:
        result = await self.getVerification(verificationId, userId)
        return result.evidence
