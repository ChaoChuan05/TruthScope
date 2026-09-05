import logging

from app.agents.nodes.common import (
    AsyncNode,
    NodeUpdate,
    evidenceForModel,
    inferenceMetadata,
    localizedPrompt,
    workflowError,
)
from app.agents.state import VerificationGraphState
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.gonka.mapper import parseStructuredInference
from app.schemas.agentOutput import GonkaInferenceRecord, JudgeResult

logger = logging.getLogger(__name__)


def createConsensusNode(
    gonkaClient: GonkaClientProtocol,
    modelName: str,
    *,
    isRetry: bool = False,
) -> AsyncNode:
    taskName = "consensusRetry" if isRetry else "consensusJudge"

    async def consensusJudge(state: VerificationGraphState) -> NodeUpdate:
        if not state.get("agentAnalyses"):
            return {
                "judgeResult": None,
                "errors": [
                    workflowError(
                        code="CONSENSUS_UNAVAILABLE",
                        stage=taskName,
                        message="No valid verifier analysis was available for judgment.",
                        retryable=True,
                    )
                ],
            }
        inference: GonkaInferenceRecord | None = None
        try:
            inputPayload: dict[str, object] = {
                "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                "evidence": evidenceForModel(
                    state["evidence"],
                    maxExcerptChars=2_500,
                ),
                "agentAnalyses": [
                    analysis.model_dump(mode="json") for analysis in state["agentAnalyses"]
                ],
                "outputLanguage": state["outputLanguage"].value,
            }
            existingBiasAudit = state.get("biasAudit")
            if isRetry and existingBiasAudit:
                inputPayload["requiredNeutralityCorrections"] = existingBiasAudit.model_dump(
                    mode="json"
                )
            inference = await gonkaClient.infer(
                taskName=taskName,
                model=modelName,
                systemPrompt=localizedPrompt(
                    "consensusJudge.md",
                    state["outputLanguage"],
                ),
                inputPayload=inputPayload,
                applicationRequestId=state.get("requestId"),
            )
            output = parseStructuredInference(inference, JudgeResult)
            validEvidenceIds = {evidence.evidenceId for evidence in state["evidence"]}
            if not set(output.reliedEvidenceIds).issubset(validEvidenceIds):
                raise ValueError("Judge cited an unknown evidence ID.")
            output.gonkaRequestId = inference.requestId
            update: NodeUpdate = {"judgeResult": output, **inferenceMetadata(inference)}
            if isRetry:
                update["biasRetryCount"] = 1
            return update
        except Exception as error:
            logger.warning(
                "Consensus judge failed requestId=%s taskName=%s errorType=%s",
                state.get("requestId"),
                taskName,
                type(error).__name__,
            )
            update = {
                "judgeResult": None,
                "errors": [
                    workflowError(
                        code="JUDGE_FAILED",
                        stage=taskName,
                        message="Consensus judgment was unavailable or invalid.",
                        retryable=True,
                    )
                ],
                "warnings": ["No model judgment was promoted as a fallback verdict."],
            }
            if inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return consensusJudge
