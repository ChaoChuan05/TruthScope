from pydantic import Field

from app.schemas.common import BiasAuditStatus, EvidenceStance, StrictSchema, Verdict


class GonkaUsage(StrictSchema):
    inputTokens: int | None = Field(default=None, ge=0)
    outputTokens: int | None = Field(default=None, ge=0)


class GonkaInferenceRecord(StrictSchema):
    taskName: str
    requestedModel: str
    servedModel: str
    requestId: str | None = None
    providerResponseId: str | None = None
    latencyMs: int = Field(ge=0)
    usage: GonkaUsage = Field(default_factory=GonkaUsage)
    fallback: str | None = None
    outputText: str = Field(default="", exclude=True)


class WorkflowError(StrictSchema):
    code: str
    stage: str
    message: str
    retryable: bool = False


class ContextAnalysis(StrictSchema):
    findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    staleEvidenceIds: list[str] = Field(default_factory=list)
    suspectedTruncationEvidenceIds: list[str] = Field(default_factory=list)


class EvidenceAssessment(StrictSchema):
    evidenceId: str
    stance: EvidenceStance
    strength: float = Field(ge=0, le=1)


class AgentAnalysis(StrictSchema):
    claimId: str
    modelName: str
    stance: EvidenceStance
    supportStrength: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    usedEvidenceIds: list[str] = Field(default_factory=list)
    contradictingEvidenceIds: list[str] = Field(default_factory=list)
    evidenceAssessments: list[EvidenceAssessment] = Field(default_factory=list)
    missingContext: list[str] = Field(default_factory=list)
    reasoningSummary: str = Field(min_length=1, max_length=3000)
    warnings: list[str] = Field(default_factory=list)
    gonkaRequestId: str | None = None


class JudgeResult(StrictSchema):
    verdict: Verdict
    supportValue: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    reliedEvidenceIds: list[str] = Field(default_factory=list)
    agreements: list[str] = Field(default_factory=list)
    disagreements: list[str] = Field(default_factory=list)
    reasoningSummary: str = Field(min_length=1, max_length=3000)
    warnings: list[str] = Field(default_factory=list)
    gonkaRequestId: str | None = None


class BiasAuditResult(StrictSchema):
    status: BiasAuditStatus
    violations: list[str] = Field(default_factory=list)
    omittedEvidenceIds: list[str] = Field(default_factory=list)
    reasoningSummary: str = Field(min_length=1, max_length=2000)
    confidencePenalty: float = Field(default=1.0, ge=0, le=1)
    gonkaRequestId: str | None = None
