from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


def utcNow() -> datetime:
    return datetime.now(UTC)


class InputType(StrEnum):
    TEXT = "text"
    URL = "url"


class ClaimType(StrEnum):
    FACTUAL = "factual"
    QUOTATION = "quotation"
    STATISTIC = "statistic"
    EVENT = "event"
    CAUSAL = "causal"
    OPINION = "opinion"
    PREDICTION = "prediction"


class EvidenceStance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    UNCLEAR = "unclear"


class SourceType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class Verdict(StrEnum):
    STRONGLY_CONTRADICTED = "strongly_contradicted"
    MOSTLY_CONTRADICTED = "mostly_contradicted"
    MIXED_OR_INCONCLUSIVE = "mixed_or_inconclusive"
    MOSTLY_SUPPORTED = "mostly_supported"
    STRONGLY_SUPPORTED = "strongly_supported"


class VerificationStatus(StrEnum):
    COMPLETE = "complete"
    INCONCLUSIVE = "inconclusive"
    DEGRADED = "degraded"
    FAILED = "failed"


class BiasAuditStatus(StrEnum):
    PASSED = "passed"
    FLAGGED = "flagged"
    UNAVAILABLE = "unavailable"
