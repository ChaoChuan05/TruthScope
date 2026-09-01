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
from app.schemas.agentOutput import ContextAnalysis, GonkaInferenceRecord

logger = logging.getLogger(__name__)


def createContextAnalysisNode(
    gonkaClient: GonkaClientProtocol,
    modelName: str,
) -> AsyncNode:
    async def contextAnalyzer(state: VerificationGraphState) -> NodeUpdate:
        inference: GonkaInferenceRecord | None = None
        try:
            inference = await gonkaClient.infer(
                taskName="contextAnalysis",
                model=modelName,
                systemPrompt=loadPrompt("contextAnalysis.md"),
                inputPayload={
                    "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                    "evidence": evidenceForModel(
                        state["evidence"],
                        maxExcerptChars=4_000,
                    ),
                },
            )
            output = parseStructuredOutput(inference.outputText, ContextAnalysis)
            validEvidenceIds = {evidence.evidenceId for evidence in state["evidence"]}
            citedIds = set(output.staleEvidenceIds + output.suspectedTruncationEvidenceIds)
            if not citedIds.issubset(validEvidenceIds):
                raise ValueError("Context analysis cited an unknown evidence ID.")
            return {
                "contextAnalysis": output,
                "warnings": output.warnings,
                **inferenceMetadata(inference),
            }
        except Exception as error:
            logger.warning(
                "Context analysis failed requestId=%s errorType=%s",
                state.get("requestId"),
                type(error).__name__,
            )
            update: NodeUpdate = {
                "contextAnalysis": None,
                "errors": [
                    workflowError(
                        code="CONTEXT_ANALYSIS_FAILED",
                        stage="contextAnalyzer",
                        message="Context analysis was unavailable.",
                        retryable=True,
                    )
                ],
                "warnings": ["Date, quotation, and statistical context checks were unavailable."],
            }
            if inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return contextAnalyzer
