import logging

from pydantic import Field

from app.agents.nodes.common import (
    AsyncNode,
    NodeUpdate,
    evidenceForModel,
    inferenceMetadata,
    loadPrompt,
    workflowError,
)
from app.agents.state import VerificationGraphState
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.gonka.mapper import parseStructuredOutput
from app.schemas.agentOutput import AgentAnalysis, EvidenceAssessment, GonkaInferenceRecord
from app.schemas.common import EvidenceStance, StrictSchema

logger = logging.getLogger(__name__)


class VerifierAnalysisOutput(StrictSchema):
    claimId: str
    stance: EvidenceStance
    supportStrength: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    usedEvidenceIds: list[str] = Field(default_factory=list)
    contradictingEvidenceIds: list[str] = Field(default_factory=list)
    evidenceAssessments: list[EvidenceAssessment] = Field(default_factory=list)
    missingContext: list[str] = Field(default_factory=list)
    reasoningSummary: str = Field(min_length=1, max_length=3000)
    warnings: list[str] = Field(default_factory=list)


class VerifierOutput(StrictSchema):
    analyses: list[VerifierAnalysisOutput] = Field(min_length=1)


def createVerifierNode(
    gonkaClient: GonkaClientProtocol,
    *,
    taskName: str,
    modelName: str,
) -> AsyncNode:
    async def verifier(state: VerificationGraphState) -> NodeUpdate:
        inference: GonkaInferenceRecord | None = None
        try:
            contextAnalysis = state.get("contextAnalysis")
            inference = await gonkaClient.infer(
                taskName=taskName,
                model=modelName,
                systemPrompt=loadPrompt("verification.md"),
                inputPayload={
                    "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                    "evidence": evidenceForModel(
                        state["evidence"],
                        maxExcerptChars=4_000,
                    ),
                    "contextAnalysis": contextAnalysis.model_dump(mode="json")
                    if contextAnalysis
                    else None,
                },
            )
            output = parseStructuredOutput(inference.outputText, VerifierOutput)
            validClaimIds = {claim.claimId for claim in state["claims"]}
            validEvidenceIds = {evidence.evidenceId for evidence in state["evidence"]}
            analyses: list[AgentAnalysis] = []
            for analysis in output.analyses:
                citedIds = set(analysis.usedEvidenceIds + analysis.contradictingEvidenceIds)
                citedIds.update(item.evidenceId for item in analysis.evidenceAssessments)
                if analysis.claimId not in validClaimIds or not citedIds.issubset(validEvidenceIds):
                    raise ValueError("Verifier cited an unknown claim or evidence ID.")
                analyses.append(
                    AgentAnalysis(
                        **analysis.model_dump(),
                        modelName=inference.servedModel,
                        gonkaRequestId=inference.requestId,
                    )
                )
            return {"agentAnalyses": analyses, **inferenceMetadata(inference)}
        except Exception as error:
            logger.warning(
                "Verifier failed requestId=%s taskName=%s errorType=%s",
                state.get("requestId"),
                taskName,
                type(error).__name__,
            )
            update: NodeUpdate = {
                "errors": [
                    workflowError(
                        code="VERIFIER_FAILED",
                        stage=taskName,
                        message=f"{taskName} did not return a valid analysis.",
                        retryable=True,
                    )
                ],
                "warnings": [f"{taskName} was unavailable; consensus coverage was reduced."],
            }
            if inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return verifier
