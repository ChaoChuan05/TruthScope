import logging

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
from app.schemas.agentOutput import BiasAuditResult, GonkaInferenceRecord
from app.schemas.common import BiasAuditStatus

logger = logging.getLogger(__name__)


def createBiasAuditNode(
    gonkaClient: GonkaClientProtocol,
    modelName: str,
    *,
    isRetry: bool = False,
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
        try:
            inference = await gonkaClient.infer(
                taskName=taskName,
                model=modelName,
                systemPrompt=loadPrompt("biasAudit.md"),
                inputPayload={
                    "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                    "evidence": evidenceForModel(
                        state["evidence"],
                        maxExcerptChars=1_500,
                    ),
                    "judgeResult": judgeResult.model_dump(mode="json"),
                },
            )
            output = parseStructuredOutput(inference.outputText, BiasAuditResult)
            validEvidenceIds = {evidence.evidenceId for evidence in state["evidence"]}
            if not set(output.omittedEvidenceIds).issubset(validEvidenceIds):
                raise ValueError("Bias audit cited an unknown evidence ID.")
            output.gonkaRequestId = inference.requestId
            warnings = output.violations if output.status == BiasAuditStatus.FLAGGED else []
            return {
                "biasAudit": output,
                "warnings": warnings,
                **inferenceMetadata(inference),
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
            if inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return biasAudit
