from app.agents.graph import VerificationWorkflow
from app.integrations.gonka.fake import ScriptedGonkaClient
from app.integrations.retrieval.client import FixtureEvidenceRetriever
from app.schemas.common import VerificationStatus
from app.schemas.verification import VerificationRequest, VerificationResult
from app.services.verificationService import VerificationService
from tests.conftest import standardResponses


class FailingRepository:
    async def save(self, result: VerificationResult) -> None:
        del result
        raise RuntimeError("data service unavailable")

    async def get(
        self,
        verificationId: str,
        requestingUserId: str | None,
    ) -> VerificationResult:
        del verificationId, requestingUserId
        raise RuntimeError("data service unavailable")


async def test_persistenceFailure_returnsCompletedAnalysisAsDegraded(sampleEvidence) -> None:
    workflow = VerificationWorkflow(
        gonkaClient=ScriptedGonkaClient(standardResponses()),
        retriever=FixtureEvidenceRetriever([sampleEvidence]),
        modelA="model-a",
        modelB="model-b",
        judgeModel="judge",
    )
    service = VerificationService(workflow, FailingRepository())
    result = await service.verifyClaim(
        VerificationRequest(input="The measured value was 42 units.")
    )
    assert result.status == VerificationStatus.DEGRADED
    assert result.score is not None
    assert any(error.code == "PERSISTENCE_UNAVAILABLE" for error in result.errors)
