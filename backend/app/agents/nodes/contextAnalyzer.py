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
from app.schemas.agentOutput import ContextAnalysis, GonkaInferenceRecord

logger = logging.getLogger(__name__)


async def deterministicContextAnalysis(state: VerificationGraphState) -> NodeUpdate:
    """Keep context explicit while independent verifiers perform detailed review."""

    missingDateCount = sum(
        evidence.source.publicationDate is None for evidence in state.get("evidence", [])
    )
    warnings = []
    if missingDateCount:
        warnings.append(f"{missingDateCount} evidence source(s) had no verified publication date.")
    return {
        "contextAnalysis": ContextAnalysis(
            findings=[
                "Dates, quotations, statistics, and missing context require verifier review."
            ],
            warnings=warnings,
        ),
        "warnings": warnings,
    }


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
                systemPrompt=localizedPrompt(
                    "contextAnalysis.md",
                    state["outputLanguage"],
                ),
                inputPayload={
                    "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                    "evidence": evidenceForModel(
                        state["evidence"],
                        maxExcerptChars=1_500,
                    ),
                    "outputLanguage": state["outputLanguage"].value,
                },
                applicationRequestId=state.get("requestId"),
                maxTokens=1_024,
            )
            output = parseStructuredInference(inference, ContextAnalysis)
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
