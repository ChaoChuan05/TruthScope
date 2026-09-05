import asyncio
import logging
from time import monotonic

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
from app.schemas.agentOutput import BiasAuditResult, GonkaInferenceRecord
from app.schemas.common import BiasAuditStatus

logger = logging.getLogger(__name__)


def createBiasAuditNode(
    gonkaClient: GonkaClientProtocol,
    modelName: str,
    *,
    isRetry: bool = False,
    stageTimeoutSeconds: float = 120.0,
) -> AsyncNode:
    taskName = "biasAuditRetry" if isRetry else "biasAudit"

    async def biasAudit(state: VerificationGraphState) -> NodeUpdate:
        judgeResult = state.get("judgeResult")
        if not judgeResult:
            return {
                "biasAudit": BiasAuditResult(
                    status=BiasAuditStatus.UNAVAILABLE,
                    reasoningSummary="Bias audit could not run without a consensus judgment.",
                    confidencePenalty=0.7,
                )
            }
        inference: GonkaInferenceRecord | None = None
        inferences: list[GonkaInferenceRecord] = []
        stageStartedAt = monotonic()
        try:
            systemPrompt = localizedPrompt("biasAudit.md", state["outputLanguage"])
            inputPayload = {
                "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                "evidence": evidenceForModel(
                    state["evidence"],
                    maxExcerptChars=1_500,
                ),
                "judgeResult": judgeResult.model_dump(mode="json"),
                "outputLanguage": state["outputLanguage"].value,
            }
            validationError: InvalidModelOutputError | None = None
            for validationAttempt in range(2):
                remainingSeconds = stageTimeoutSeconds - (monotonic() - stageStartedAt)
                if remainingSeconds <= 0:
                    raise TimeoutError("Bias-audit stage deadline exceeded.")
                currentInference = await asyncio.wait_for(
                    gonkaClient.infer(
                        taskName=taskName,
                        model=modelName,
                        systemPrompt=systemPrompt
                        if validationError is None
                        else structuredOutputRepairPrompt(systemPrompt, validationError),
                        inputPayload=inputPayload,
                        applicationRequestId=state.get("requestId"),
                        outputSchema=BiasAuditResult.model_json_schema(),
                        maxTokens=4096
                        if validationError is not None and validationError.reason == "max_tokens"
                        else None,
                    ),
                    timeout=remainingSeconds,
                )
                inference = currentInference
                inferences.append(currentInference)
                try:
                    output = parseStructuredInference(currentInference, BiasAuditResult)
                    validEvidenceIds = {evidence.evidenceId for evidence in state["evidence"]}
                    if not set(output.omittedEvidenceIds).issubset(validEvidenceIds):
                        raise InvalidModelOutputError(
                            "Bias audit output failed semantic validation.",
                            reason="semantic_validation",
                            validationPaths=("omittedEvidenceIds.unknown",),
                            outputLength=len(currentInference.outputText),
                        )
                    if output.status == BiasAuditStatus.PASSED and (
                        output.violations or output.omittedEvidenceIds
                    ):
                        raise InvalidModelOutputError(
                            "Bias audit output failed semantic validation.",
                            reason="semantic_validation",
                            validationPaths=("status.passed.inconsistentFindings",),
                            outputLength=len(currentInference.outputText),
                        )
                    if output.status == BiasAuditStatus.FLAGGED and not (
                        output.violations or output.omittedEvidenceIds
                    ):
                        raise InvalidModelOutputError(
                            "Bias audit output failed semantic validation.",
                            reason="semantic_validation",
                            validationPaths=("status.flagged.missingFinding",),
                            outputLength=len(currentInference.outputText),
                        )
                    break
                except InvalidModelOutputError as error:
                    validationError = error
                    log = logger.info if validationAttempt == 0 else logger.warning
                    log(
                        "Bias audit output invalid requestId=%s taskName=%s model=%s "
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
                raise RuntimeError("Bias-audit structured-output loop did not finish.")

            if inference is None:  # pragma: no cover - loop must return or raise
                raise RuntimeError("Bias-audit inference was not recorded.")
            output.gonkaRequestId = inference.requestId
            if output.status == BiasAuditStatus.UNAVAILABLE:
                return {
                    "biasAudit": output,
                    "errors": [
                        workflowError(
                            code="BIAS_AUDIT_UNAVAILABLE",
                            stage=taskName,
                            message="Bias audit did not provide a completed audit.",
                            retryable=True,
                        )
                    ],
                    "warnings": ["Result was not marked as bias-cleared."],
                    **inferenceMetadataFor(inferences),
                }
            warnings = output.violations if output.status == BiasAuditStatus.FLAGGED else []
            return {
                "biasAudit": output,
                "warnings": warnings,
                **inferenceMetadataFor(inferences),
            }
        except Exception as error:
            logger.warning(
                "Bias audit failed requestId=%s taskName=%s errorType=%s",
                state.get("requestId"),
                taskName,
                type(error).__name__,
            )
            update: NodeUpdate = {
                "biasAudit": BiasAuditResult(
                    status=BiasAuditStatus.UNAVAILABLE,
                    reasoningSummary="Bias audit was unavailable.",
                    confidencePenalty=0.7,
                ),
                "errors": [
                    workflowError(
                        code="BIAS_AUDIT_FAILED",
                        stage=taskName,
                        message="Bias audit was unavailable or invalid.",
                        retryable=True,
                    )
                ],
                "warnings": ["Result was not marked as bias-cleared."],
            }
            if inferences:
                update.update(inferenceMetadataFor(inferences))
            elif inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return biasAudit
