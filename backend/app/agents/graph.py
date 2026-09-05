from typing import cast

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from app.agents.nodes.biasAuditor import createBiasAuditNode
from app.agents.nodes.claimExtractor import createClaimExtractionNode
from app.agents.nodes.common import AsyncNode, NodeUpdate
from app.agents.nodes.consensusJudge import createConsensusNode
from app.agents.nodes.contextAnalyzer import (
    createContextAnalysisNode,
    deterministicContextAnalysis,
)
from app.agents.nodes.evidencePlanner import (
    createDirectEvidencePlanningNode,
    createEvidenceNormalizationNode,
    createEvidencePlanningNode,
)
from app.agents.nodes.inputPreparation import createInputPreparationNode
from app.agents.nodes.verifier import createVerifierNode
from app.agents.state import VerificationGraphState
from app.integrations.gonka.client import GonkaClientProtocol
from app.integrations.retrieval.client import (
    DocumentFetcherProtocol,
    EvidenceRetrieverProtocol,
    UnavailableDocumentFetcher,
)
from app.schemas.common import BiasAuditStatus, InputType, Verdict, VerificationStatus, utcNow
from app.schemas.verification import VerificationResult
from app.services.scoringService import calculateModelAgreement, calculateVerificationScore

PROMPT_VERSION = "truthscope-prompts-v5"


def _asRunnable(node: AsyncNode) -> RunnableLambda[VerificationGraphState, NodeUpdate]:
    """Bridge async node factories to LangGraph's typed Runnable interface."""

    return RunnableLambda(node)


class VerificationWorkflow:
    """Compiled LangGraph workflow with provider dependencies captured at construction."""

    def __init__(
        self,
        *,
        gonkaClient: GonkaClientProtocol,
        retriever: EvidenceRetrieverProtocol,
        modelA: str,
        modelB: str,
        judgeModel: str,
        orchestratorModel: str | None = None,
        biasAuditorModel: str | None = None,
        parallelVerifiers: bool = False,
        reducedGonkaCalls: bool = False,
        verifierStageTimeoutSeconds: float = 180.0,
        auditStageTimeoutSeconds: float = 120.0,
        maxEvidenceQueriesPerClaim: int = 3,
        maxEvidencePerClaim: int = 12,
        maxTotalEvidence: int = 20,
        documentFetcher: DocumentFetcherProtocol | None = None,
    ) -> None:
        workflowModel = orchestratorModel or modelA
        auditModel = biasAuditorModel or judgeModel
        inputDocumentFetcher = documentFetcher or UnavailableDocumentFetcher()
        graphBuilder = StateGraph(VerificationGraphState)
        graphBuilder.add_node(
            "inputPreparation",
            _asRunnable(createInputPreparationNode(inputDocumentFetcher)),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "claimExtraction",
            _asRunnable(createClaimExtractionNode(gonkaClient, workflowModel)),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "evidencePlanningAndRetrieval",
            _asRunnable(
                createDirectEvidencePlanningNode(retriever)
                if reducedGonkaCalls
                else createEvidencePlanningNode(
                    gonkaClient,
                    retriever,
                    workflowModel,
                    maxQueriesPerClaim=maxEvidenceQueriesPerClaim,
                )
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "evidenceNormalization",
            _asRunnable(
                createEvidenceNormalizationNode(
                    maxEvidencePerClaim=maxEvidencePerClaim,
                    maxTotalEvidence=maxTotalEvidence,
                )
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "contextAnalyzer",
            _asRunnable(
                deterministicContextAnalysis
                if reducedGonkaCalls
                else createContextAnalysisNode(gonkaClient, workflowModel)
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "verifierModelA",
            _asRunnable(
                createVerifierNode(
                    gonkaClient,
                    taskName="verifierModelA",
                    modelName=modelA,
                    stageTimeoutSeconds=verifierStageTimeoutSeconds,
                )
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "verifierModelB",
            _asRunnable(
                createVerifierNode(
                    gonkaClient,
                    taskName="verifierModelB",
                    modelName=modelB,
                    stageTimeoutSeconds=verifierStageTimeoutSeconds,
                )
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "consensusJudge",
            _asRunnable(createConsensusNode(gonkaClient, judgeModel)),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "biasAudit",
            _asRunnable(
                createBiasAuditNode(
                    gonkaClient,
                    auditModel,
                    stageTimeoutSeconds=auditStageTimeoutSeconds,
                )
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "consensusRetry",
            _asRunnable(createConsensusNode(gonkaClient, judgeModel, isRetry=True)),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "biasAuditRetry",
            _asRunnable(
                createBiasAuditNode(
                    gonkaClient,
                    auditModel,
                    isRetry=True,
                    stageTimeoutSeconds=auditStageTimeoutSeconds,
                )
            ),
            input_schema=VerificationGraphState,
        )
        graphBuilder.add_node(
            "deterministicScoring",
            _asRunnable(deterministicScoring),
            input_schema=VerificationGraphState,
        )

        graphBuilder.add_edge(START, "inputPreparation")
        graphBuilder.add_conditional_edges(
            "inputPreparation",
            routeAfterInputPreparation,
            {"continue": "claimExtraction", "finish": "deterministicScoring"},
        )
        graphBuilder.add_conditional_edges(
            "claimExtraction",
            routeAfterClaimExtraction,
            {
                "continue": "evidencePlanningAndRetrieval",
                "finish": "deterministicScoring",
            },
        )
        graphBuilder.add_edge("evidencePlanningAndRetrieval", "evidenceNormalization")
        graphBuilder.add_conditional_edges(
            "evidenceNormalization",
            routeAfterEvidenceNormalization,
            {"verify": "contextAnalyzer", "finish": "deterministicScoring"},
        )
        if parallelVerifiers:
            graphBuilder.add_edge("contextAnalyzer", "verifierModelA")
            graphBuilder.add_edge("contextAnalyzer", "verifierModelB")
            graphBuilder.add_edge(["verifierModelA", "verifierModelB"], "consensusJudge")
        else:
            graphBuilder.add_edge("contextAnalyzer", "verifierModelA")
            graphBuilder.add_edge("verifierModelA", "verifierModelB")
            graphBuilder.add_edge("verifierModelB", "consensusJudge")
        graphBuilder.add_edge("consensusJudge", "biasAudit")
        graphBuilder.add_conditional_edges(
            "biasAudit",
            routeAfterBiasAudit,
            {"retry": "consensusRetry", "score": "deterministicScoring"},
        )
        graphBuilder.add_edge("consensusRetry", "biasAuditRetry")
        graphBuilder.add_edge("biasAuditRetry", "deterministicScoring")
        graphBuilder.add_edge("deterministicScoring", END)
        self.compiledGraph = graphBuilder.compile()

    async def run(self, initialState: VerificationGraphState) -> VerificationGraphState:
        result = await self.compiledGraph.ainvoke(initialState)
        return cast(VerificationGraphState, result)


async def routeAfterInputPreparation(state: VerificationGraphState) -> str:
    if state["inputType"] == InputType.URL and state.get("sourceDocument") is None:
        return "finish"
    return "continue"


async def routeAfterClaimExtraction(state: VerificationGraphState) -> str:
    return "continue" if state.get("claims") else "finish"


async def routeAfterEvidenceNormalization(state: VerificationGraphState) -> str:
    return "verify" if state.get("evidence") else "finish"


async def routeAfterBiasAudit(state: VerificationGraphState) -> str:
    audit = state.get("biasAudit")
    if (
        audit
        and audit.status == BiasAuditStatus.FLAGGED
        and state.get("biasRetryCount", 0) < 1
        and state.get("judgeResult") is not None
    ):
        return "retry"
    return "score"


async def deterministicScoring(state: VerificationGraphState) -> NodeUpdate:
    score = calculateVerificationScore(
        claims=state.get("claims", []),
        evidence=state.get("evidence", []),
        analyses=state.get("agentAnalyses", []),
        biasAudit=state.get("biasAudit"),
        contextAnalysis=state.get("contextAnalysis"),
    )
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    analyses = state.get("agentAnalyses", [])
    judgeResult = state.get("judgeResult")
    biasAudit = state.get("biasAudit")
    errors = state.get("errors", [])
    warnings = list(dict.fromkeys(state.get("warnings", [])))
    limitations = list(dict.fromkeys(state.get("limitations", [])))
    limitations.append(
        "Truth Score measures support from collected evidence; it is not guaranteed "
        "objective truth."
    )

    if not claims:
        status = VerificationStatus.FAILED
        limitations.append("No verifiable claim was extracted.")
    elif not evidence:
        status = VerificationStatus.INCONCLUSIVE
        limitations.append("No traceable evidence was available.")
    elif (
        judgeResult is None
        or biasAudit is None
        or biasAudit.status == BiasAuditStatus.UNAVAILABLE
        or errors
    ):
        status = VerificationStatus.DEGRADED
        limitations.append("One or more verification stages were unavailable.")
    else:
        status = VerificationStatus.COMPLETE

    modelAgreement = calculateModelAgreement(analyses)
    modelDisagreement = bool(
        (judgeResult and judgeResult.disagreements) or (len(analyses) >= 2 and modelAgreement < 0.7)
    )
    verdict = score.verdict if score else Verdict.MIXED_OR_INCONCLUSIVE
    result = VerificationResult(
        verificationId=state["verificationId"],
        requestId=state["requestId"],
        userId=state.get("userId"),
        originalInput=state["originalInput"],
        inputType=state["inputType"],
        outputLanguage=state["outputLanguage"],
        normalizedText=state.get("normalizedText", state["originalInput"]),
        claims=claims,
        evidence=evidence,
        agentAnalyses=analyses,
        judgeResult=judgeResult,
        biasAudit=biasAudit,
        score=score,
        verdict=verdict,
        modelDisagreement=modelDisagreement,
        inferenceRecords=state.get("inferenceRecords", []),
        gonkaRequestIds=list(dict.fromkeys(state.get("gonkaRequestIds", []))),
        warnings=warnings,
        limitations=list(dict.fromkeys(limitations)),
        errors=errors,
        promptVersion=state.get("promptVersion", PROMPT_VERSION),
        status=status,
        createdAt=state.get("createdAt", utcNow()),
        completedAt=utcNow(),
    )
    return {"score": score, "result": result}
