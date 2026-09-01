from datetime import datetime
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from app.core.security import validatePublicUrl
from app.schemas.agentOutput import (
    AgentAnalysis,
    BiasAuditResult,
    GonkaInferenceRecord,
    JudgeResult,
    WorkflowError,
)
from app.schemas.common import (
    ClaimType,
    InputType,
    StrictSchema,
    Verdict,
    VerificationStatus,
    utcNow,
)
from app.schemas.evidence import EvidenceRecord


class Claim(StrictSchema):
    claimId: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    originalText: str = Field(min_length=1, max_length=5000)
    normalizedText: str = Field(min_length=1, max_length=5000)
    claimType: ClaimType
    language: str | None = Field(default=None, max_length=50)
    verifiable: bool = True
    qualifiers: list[str] = Field(default_factory=list)


class VerificationRequest(StrictSchema):
    input: str = Field(min_length=1, max_length=5000)
    inputType: InputType | None = None

    @field_validator("input")
    @classmethod
    def inputMustContainContent(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Input must contain non-whitespace content.")
        return normalized

    @model_validator(mode="after")
    def inferAndValidateInputType(self) -> "VerificationRequest":
        parsedUrl = urlsplit(self.input)
        inferredType = InputType.URL if parsedUrl.scheme and parsedUrl.netloc else InputType.TEXT
        if self.inputType is None:
            self.inputType = inferredType
        if self.inputType == InputType.URL:
            try:
                validatePublicUrl(self.input)
            except ValueError as error:
                raise ValueError(str(error)) from error
            except Exception as error:
                raise ValueError(str(error)) from error
        return self


class VerificationScore(StrictSchema):
    truthScore: float = Field(ge=0, le=100)
    confidenceScore: float = Field(ge=0, le=100)
    verdict: Verdict
    evidenceWeight: float = Field(ge=0)
    evidenceCoverage: float = Field(ge=0, le=1)
    modelAgreement: float = Field(ge=0, le=1)
    formulaVersion: str


class VerificationResult(StrictSchema):
    verificationId: str
    requestId: str
    userId: str | None = Field(default=None, exclude=True)
    originalInput: str
    inputType: InputType
    normalizedText: str
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    agentAnalyses: list[AgentAnalysis] = Field(default_factory=list)
    judgeResult: JudgeResult | None = None
    biasAudit: BiasAuditResult | None = None
    score: VerificationScore | None = None
    verdict: Verdict = Verdict.MIXED_OR_INCONCLUSIVE
    modelDisagreement: bool = False
    inferenceRecords: list[GonkaInferenceRecord] = Field(default_factory=list)
    gonkaRequestIds: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    errors: list[WorkflowError] = Field(default_factory=list)
    promptVersion: str
    status: VerificationStatus
    createdAt: datetime = Field(default_factory=utcNow)
    completedAt: datetime = Field(default_factory=utcNow)
