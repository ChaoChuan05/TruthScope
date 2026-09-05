import asyncio
import logging
from time import monotonic

from pydantic import Field

from app.agents.nodes.common import (
    AsyncNode,
    NodeUpdate,
    evidenceForModel,
    inferenceMetadata,
    inferenceMetadataFor,
    localizedPrompt,
    structuredOutputRepairPrompt,
    workflowError,
)
from app.agents.state import VerificationGraphState
from app.core.exceptions import InvalidModelOutputError
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.gonka.mapper import parseStructuredInference
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


def _validatedAnalyses(
    output: VerifierOutput,
    state: VerificationGraphState,
    inference: GonkaInferenceRecord,
) -> list[AgentAnalysis]:
    expectedClaimIds = [claim.claimId for claim in state["claims"]]
    returnedClaimIds = [analysis.claimId for analysis in output.analyses]
    validationPaths: list[str] = []
    if len(returnedClaimIds) != len(set(returnedClaimIds)):
        validationPaths.append("analyses.claimId.duplicate")
    if set(returnedClaimIds) != set(expectedClaimIds):
        validationPaths.append("analyses.claimId.coverage")

    evidenceClaimIds = {
        evidence.evidenceId: set(evidence.claimIds) for evidence in state["evidence"]
    }
    for index, analysis in enumerate(output.analyses):
        assessmentIds = [item.evidenceId for item in analysis.evidenceAssessments]
        if len(assessmentIds) != len(set(assessmentIds)):
            validationPaths.append(f"analyses.{index}.evidenceAssessments.duplicate")
        citedIds = set(analysis.usedEvidenceIds + analysis.contradictingEvidenceIds)
        citedIds.update(item.evidenceId for item in analysis.evidenceAssessments)
        for evidenceId in citedIds:
            relatedClaimIds = evidenceClaimIds.get(evidenceId)
            if relatedClaimIds is None:
                validationPaths.append(f"analyses.{index}.evidenceId.unknown")
            elif analysis.claimId not in relatedClaimIds:
                validationPaths.append(f"analyses.{index}.evidenceId.claimMismatch")

    if validationPaths:
        raise InvalidModelOutputError(
            "Verifier output failed semantic validation.",
            reason="semantic_validation",
            validationPaths=tuple(dict.fromkeys(validationPaths)),
            outputLength=len(inference.outputText),
        )

    return [
        AgentAnalysis(
            **analysis.model_dump(),
            modelName=inference.servedModel,
            gonkaRequestId=inference.requestId,
        )
        for analysis in output.analyses
    ]


def createVerifierNode(
    gonkaClient: GonkaClientProtocol,
    *,
    taskName: str,
    modelName: str,
    stageTimeoutSeconds: float = 180.0,
) -> AsyncNode:
    async def verifier(state: VerificationGraphState) -> NodeUpdate:
        inference: GonkaInferenceRecord | None = None
        inferences: list[GonkaInferenceRecord] = []
        stageStartedAt = monotonic()
        try:
            contextAnalysis = state.get("contextAnalysis")
            systemPrompt = localizedPrompt("verification.md", state["outputLanguage"])
            inputPayload = {
                "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                "evidence": evidenceForModel(
                    state["evidence"],
                    maxExcerptChars=2_500,
                ),
                "contextAnalysis": contextAnalysis.model_dump(mode="json")
                if contextAnalysis
                else None,
                "outputLanguage": state["outputLanguage"].value,
            }
            validationError: InvalidModelOutputError | None = None
            for validationAttempt in range(2):
                remainingSeconds = stageTimeoutSeconds - (monotonic() - stageStartedAt)
                if remainingSeconds <= 0:
                    raise TimeoutError("Verifier stage deadline exceeded.")
                currentInference = await asyncio.wait_for(
                    gonkaClient.infer(
                        taskName=taskName,
                        model=modelName,
                        systemPrompt=systemPrompt
                        if validationError is None
                        else structuredOutputRepairPrompt(systemPrompt, validationError),
                        inputPayload=inputPayload,
                        applicationRequestId=state.get("requestId"),
                        outputSchema=VerifierOutput.model_json_schema(),
                        maxTokens=4096
                        if validationError is not None and validationError.reason == "max_tokens"
                        else None,
                    ),
                    timeout=remainingSeconds,
                )
                inference = currentInference
                inferences.append(currentInference)
                try:
                    output = parseStructuredInference(currentInference, VerifierOutput)
                    analyses = _validatedAnalyses(output, state, currentInference)
                    break
                except InvalidModelOutputError as error:
                    validationError = error
                    log = logger.info if validationAttempt == 0 else logger.warning
                    log(
                        "Verifier output invalid requestId=%s taskName=%s model=%s "
                        "gonkaRequestId=%s validationAttempt=%s reason=%s "
                        "validationPaths=%s outputLength=%s willRetry=%s",
                        state.get("requestId"),
                        taskName,
                        currentInference.servedModel,
                        currentInference.requestId,
                        validationAttempt + 1,
                        error.reason,
                        list(error.validationPaths),
                        error.outputLength,
                        validationAttempt == 0,
                    )
                    if validationAttempt == 1:
                        raise
            else:  # pragma: no cover - loop always breaks or raises
                raise RuntimeError("Verifier structured-output loop did not finish.")

            return {"agentAnalyses": analyses, **inferenceMetadataFor(inferences)}
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
            if inferences:
                update.update(inferenceMetadataFor(inferences))
            elif inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return verifier
