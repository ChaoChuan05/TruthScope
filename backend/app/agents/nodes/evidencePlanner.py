import logging

from pydantic import Field

from app.agents.nodes.common import (
    AsyncNode,
    NodeUpdate,
    inferenceMetadata,
    localizedPrompt,
    workflowError,
)
from app.agents.state import VerificationGraphState
from app.core.security import validatePublicUrl
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.gonka.mapper import parseStructuredInference
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
    *,
    maxQueriesPerClaim: int = 3,
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
                systemPrompt=localizedPrompt(
                    "evidencePlanning.md",
                    state["outputLanguage"],
                ),
                inputPayload={
                    "claims": [claim.model_dump(mode="json") for claim in state["claims"]],
                    "outputLanguage": state["outputLanguage"].value,
                },
                applicationRequestId=state.get("requestId"),
            )
            output = parseStructuredInference(inference, EvidencePlanOutput)
            validClaimIds = {claim.claimId for claim in state["claims"]}
            if any(query.claimId not in validClaimIds for query in output.queries):
                raise ValueError("Evidence plan cited an unknown claim ID.")
            queryCountByClaim: dict[str, int] = {}
            boundedQueries: list[EvidenceQuery] = []
            for query in output.queries:
                queryCount = queryCountByClaim.get(query.claimId, 0)
                if queryCount >= maxQueriesPerClaim:
                    continue
                boundedQueries.append(query)
                queryCountByClaim[query.claimId] = queryCount + 1
            output = output.model_copy(update={"queries": boundedQueries})
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


def createDirectEvidencePlanningNode(
    retriever: EvidenceRetrieverProtocol,
) -> AsyncNode:
    """Build one direct search query per claim without another Gonka call."""

    async def directEvidencePlanningAndRetrieval(
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

        queries = [
            EvidenceQuery(
                claimId=claim.claimId,
                query=(claim.normalizedText or claim.originalText)[:500],
                preferredSourceTypes=[SourceType.PRIMARY, SourceType.SECONDARY],
                rationale="Direct claim search used to reduce provider calls.",
            )
            for claim in state["claims"]
        ]
        try:
            retrievedEvidence = await retriever.retrieve(
                queries=queries,
                originalInput=state["originalInput"],
                inputType=state["inputType"],
                claims=state["claims"],
            )
            return {
                "evidenceQueries": queries,
                "evidence": [*sourceEvidence, *retrievedEvidence],
            }
        except Exception as error:
            logger.warning(
                "Direct evidence retrieval failed requestId=%s errorType=%s",
                state.get("requestId"),
                type(error).__name__,
            )
            return {
                "evidenceQueries": queries,
                "evidence": sourceEvidence,
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

    return directEvidencePlanningAndRetrieval


def createEvidenceNormalizationNode(
    *,
    maxEvidencePerClaim: int = 12,
    maxTotalEvidence: int = 20,
) -> AsyncNode:
    async def evidenceNormalization(state: VerificationGraphState) -> NodeUpdate:
        """Validate, deduplicate, and bound all evidence regardless of retrieval adapter."""

        validClaimIds = {claim.claimId for claim in state["claims"]}
        normalizedEvidence: list[EvidenceRecord] = []
        evidenceCountByClaim: dict[str, int] = {}
        seenEvidenceIds: set[str] = set()
        warnings: list[str] = []
        for evidence in state.get("evidence", []):
            if evidence.evidenceId in seenEvidenceIds:
                warnings.append(f"Duplicate evidence ID removed: {evidence.evidenceId}")
                continue
            relatedClaimIds = [
                claimId
                for claimId in evidence.claimIds
                if claimId in validClaimIds
                and evidenceCountByClaim.get(claimId, 0) < maxEvidencePerClaim
            ]
            if not relatedClaimIds:
                warnings.append(f"Unrelated or excess evidence removed: {evidence.evidenceId}")
                continue
            if len(normalizedEvidence) >= maxTotalEvidence:
                warnings.append("Total evidence limit reached; remaining records were removed.")
                break
            try:
                validatePublicUrl(str(evidence.source.url))
            except Exception:
                warnings.append(f"Unsafe source URL removed: {evidence.evidenceId}")
                continue
            normalizedEvidence.append(evidence.model_copy(update={"claimIds": relatedClaimIds}))
            seenEvidenceIds.add(evidence.evidenceId)
            for claimId in relatedClaimIds:
                evidenceCountByClaim[claimId] = evidenceCountByClaim.get(claimId, 0) + 1
        return {"evidence": normalizedEvidence, "warnings": warnings}

    return evidenceNormalization
