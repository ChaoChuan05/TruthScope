import logging

from pydantic import Field

from app.agents.nodes.common import (
    AsyncNode,
    NodeUpdate,
    inferenceMetadata,
    loadPrompt,
    workflowError,
)
from app.agents.state import VerificationGraphState
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.gonka.mapper import parseStructuredOutput
from app.schemas.agentOutput import GonkaInferenceRecord
from app.schemas.common import StrictSchema
from app.schemas.verification import Claim

logger = logging.getLogger(__name__)


class ClaimExtractionOutput(StrictSchema):
    normalizedText: str = Field(min_length=1, max_length=5000)
    claims: list[Claim] = Field(min_length=1, max_length=10)


def createClaimExtractionNode(
    gonkaClient: GonkaClientProtocol,
    modelName: str,
) -> AsyncNode:
    async def claimExtraction(state: VerificationGraphState) -> NodeUpdate:
        inference: GonkaInferenceRecord | None = None
        try:
            inference = await gonkaClient.infer(
                taskName="claimExtraction",
                model=modelName,
                systemPrompt=loadPrompt("claimExtraction.md"),
                inputPayload={
                    "content": state.get("analysisInput", state["originalInput"]),
                    "inputType": state["inputType"].value,
                    "sourceUrl": state["originalInput"]
                    if state["inputType"].value == "url"
                    else None,
                },
            )
            output = parseStructuredOutput(inference.outputText, ClaimExtractionOutput)
            return {
                "normalizedText": output.normalizedText,
                "claims": output.claims,
                **inferenceMetadata(inference),
            }
        except Exception as error:
            logger.warning(
                "Claim extraction failed requestId=%s errorType=%s",
                state.get("requestId"),
                type(error).__name__,
            )
            update: NodeUpdate = {
                "normalizedText": state["originalInput"],
                "claims": [],
                "errors": [
                    workflowError(
                        code="CLAIM_EXTRACTION_FAILED",
                        stage="claimExtraction",
                        message="Claim extraction could not be completed through Gonka.",
                        retryable=True,
                    )
                ],
                "warnings": ["Verification stopped before claim extraction completed."],
            }
            if inference is not None:
                update.update(inferenceMetadata(inference))
            return update

    return claimExtraction
