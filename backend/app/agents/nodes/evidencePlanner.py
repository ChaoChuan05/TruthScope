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
from app.core.security import validatePublicUrl
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.gonka.mapper import parseStructuredOutput
from app.integrations.retrieval.client import EvidenceRetrieverProtocol, documentToEvidence
from app.schemas.agentOutput import GonkaInferenceRecord
from app.schemas.common import SourceType, StrictSchema
from app.schemas.evidence import EvidenceQuery, EvidenceRecord

logger = logging.getLogger(__name__)


class EvidencePlanOutput(StrictSchema):
    queries: list[EvidenceQuery] = Field(min_length=1, max_length=30)


def createEvidencePlanningNode(
    gonkaClient: GonkaClientProtocol,
    retriever: EvidenceRetrieverProtocol,
    modelName: str,
) -> AsyncNode:
    async def evidencePlanningAndRetrieval(
        state: VerificationGraphState,
    ) -> NodeUpdate:
        sourceEvidence: list[EvidenceRecord] = []
        sourceDocument = state.get("sourceDocument")
        if sourceDocument is not None:
            sourceEvidence.append(
                documentToEvidence(
                    sourceDocument,
                    [claim.claimId for claim in state["claims"]],
                    sourceType=SourceType.USER_PROVIDED,
                    limitations=[
                        "User-provided page is uncorroborated and does not establish claim truth."
                    ],
                )
            )

        inference: GonkaInferenceRecord | None = None
        try:
            inference = await gonkaClient.infer(
                taskName="evidencePlanning",
                model=modelName,
                systemPrompt=loadPrompt("evidencePlanning.md"),
                inputPayload={
                    "claims": [claim.model_dump(mode="json") for claim in state["claims"]]
                },
            )
            output = parseStructuredOutput(inference.outputText, EvidencePlanOutput)
            validClaimIds = {claim.claimId for claim in state["claims"]}
            if any(query.claimId not in validClaimIds for query in output.queries):
                raise ValueError("Evidence plan cited an unknown claim ID.")
        except Exception as error:
            logger.warning(
                "Evidence planning failed requestId=%s errorType=%s",
                state.get("requestId"),
                type(error).__name__,
            )
            update: NodeUpdate = {
                "evidenceQueries": [],
                "evidence": sourceEvidence,
                "errors": [
                    workflowError(
                        code="EVIDENCE_PLANNING_FAILED",
                        stage="evidencePlanningAndRetrieval",
                        message="Evidence planning could not be completed through Gonka.",
                        retryable=True,
                    )
                ],
                "warnings": [
                    "No evidence plan was available; only the user-provided source was retained."
                    if sourceEvidence
                    else "No evidence plan was available for retrieval."
                ],
            }
            if inference is not None:
                update.update(inferenceMetadata(inference))
            return update

        try:
            retrievedEvidence = await retriever.retrieve(
                queries=output.queries,
                originalInput=state["originalInput"],
                inputType=state["inputType"],
                claims=state["claims"],
            )
            return {
                "evidenceQueries": output.queries,
                "evidence": [*sourceEvidence, *retrievedEvidence],
                **inferenceMetadata(inference),
            }
        except Exception as error:
            logger.warning(
                "Evidence retrieval failed requestId=%s errorType=%s",
                state.get("requestId"),
                type(error).__name__,
            )
            return {
                "evidenceQueries": output.queries,
                "evidence": sourceEvidence,
                **inferenceMetadata(inference),
                "errors": [
                    workflowError(
                        code="EVIDENCE_RETRIEVAL_FAILED",
                        stage="evidencePlanningAndRetrieval",
                        message="Evidence retrieval could not be completed.",
                        retryable=True,
                    )
                ],
                "warnings": [
                    "Search retrieval failed; the user-provided source was retained."
                    if sourceEvidence
                    else "No evidence pack was available for verification."
                ],
            }

    return evidencePlanningAndRetrieval


async def evidenceNormalization(state: VerificationGraphState) -> NodeUpdate:
    """Deduplicate evidence and remove records unrelated to extracted claims."""

    validClaimIds = {claim.claimId for claim in state["claims"]}
    normalizedEvidence: list[EvidenceRecord] = []
    seenEvidenceIds: set[str] = set()
    warnings: list[str] = []
    for evidence in state.get("evidence", []):
        if evidence.evidenceId in seenEvidenceIds:
            warnings.append(f"Duplicate evidence ID removed: {evidence.evidenceId}")
            continue
        relatedClaimIds = [claimId for claimId in evidence.claimIds if claimId in validClaimIds]
        if not relatedClaimIds:
            warnings.append(f"Unrelated evidence removed: {evidence.evidenceId}")
            continue
        try:
            validatePublicUrl(str(evidence.source.url))
        except Exception:
            warnings.append(f"Unsafe source URL removed: {evidence.evidenceId}")
            continue
        normalizedEvidence.append(evidence.model_copy(update={"claimIds": relatedClaimIds}))
        seenEvidenceIds.add(evidence.evidenceId)
    return {"evidence": normalizedEvidence, "warnings": warnings}
