from datetime import datetime

from pydantic import AnyHttpUrl, Field, field_validator

from app.schemas.common import EvidenceStance, SourceType, StrictSchema, utcNow


class EvidenceQuality(StrictSchema):
    provenance: int = Field(ge=0, le=5)
    directness: int = Field(ge=0, le=5)
    dateRelevance: int = Field(ge=0, le=5)
    contextCompleteness: int = Field(ge=0, le=5)
    corroboration: int = Field(ge=0, le=5)

    def normalizedWeight(self) -> float:
        total = (
            self.provenance
            + self.directness
            + self.dateRelevance
            + self.contextCompleteness
            + self.corroboration
        )
        return total / 25


class SourceMetadata(StrictSchema):
    url: AnyHttpUrl
    title: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(default=None, max_length=300)
    publicationDate: datetime | None = None
    retrievalTimestamp: datetime = Field(default_factory=utcNow)
    sourceType: SourceType = SourceType.UNKNOWN


class RetrievedDocument(StrictSchema):
    source: SourceMetadata
    text: str = Field(min_length=1, max_length=12_000)
    contentType: str = Field(min_length=1, max_length=200)


class EvidenceRecord(StrictSchema):
    evidenceId: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    source: SourceMetadata
    excerpt: str = Field(min_length=1, max_length=12_000)
    claimIds: list[str] = Field(min_length=1)
    stance: EvidenceStance = EvidenceStance.UNCLEAR
    stanceStrength: float = Field(default=0.0, ge=0, le=1)
    quality: EvidenceQuality
    limitations: list[str] = Field(default_factory=list)

    @field_validator("claimIds")
    @classmethod
    def claimIdsMustBeUnique(cls, claimIds: list[str]) -> list[str]:
        return list(dict.fromkeys(claimIds))


class EvidenceQuery(StrictSchema):
    claimId: str
    query: str = Field(min_length=1, max_length=500)
    preferredSourceTypes: list[SourceType] = Field(default_factory=list)
    rationale: str = Field(min_length=1, max_length=1000)
