import operator
from datetime import datetime
from typing import Annotated, TypedDict

from app.schemas.agentOutput import (
    AgentAnalysis,
    BiasAuditResult,
    ContextAnalysis,
    GonkaInferenceRecord,
    JudgeResult,
    WorkflowError,
)
from app.schemas.common import InputType
from app.schemas.evidence import EvidenceQuery, EvidenceRecord, RetrievedDocument
from app.schemas.verification import Claim, VerificationResult, VerificationScore


class VerificationGraphState(TypedDict, total=False):
    requestId: str
    verificationId: str
    userId: str | None
    originalInput: str
    inputType: InputType
    analysisInput: str
    sourceDocument: RetrievedDocument | None
    normalizedText: str
    createdAt: datetime
    claims: list[Claim]
    evidenceQueries: list[EvidenceQuery]
    evidence: list[EvidenceRecord]
    contextAnalysis: ContextAnalysis | None
    agentAnalyses: Annotated[list[AgentAnalysis], operator.add]
    judgeResult: JudgeResult | None
    biasAudit: BiasAuditResult | None
    biasRetryCount: int
    score: VerificationScore | None
    result: VerificationResult
    inferenceRecords: Annotated[list[GonkaInferenceRecord], operator.add]
    gonkaRequestIds: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]
    limitations: Annotated[list[str], operator.add]
    errors: Annotated[list[WorkflowError], operator.add]
    promptVersion: str
