from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.common import EvidenceStance
from app.schemas.evidence import EvidenceQuality, EvidenceRecord, SourceMetadata


def test_publicationAndRetrievalDates_remainDistinct() -> None:
    publicationDate = datetime(2024, 1, 1, tzinfo=UTC)
    retrievalTimestamp = publicationDate + timedelta(days=30)
    record = EvidenceRecord(
        evidenceId="evidence-1",
        source=SourceMetadata(
            url="https://example.com/report",
            title="Report",
            publicationDate=publicationDate,
            retrievalTimestamp=retrievalTimestamp,
        ),
        excerpt="Evidence",
        claimIds=["claim-1"],
        stance=EvidenceStance.NEUTRAL,
        quality=EvidenceQuality(
            provenance=3,
            directness=3,
            dateRelevance=3,
            contextCompleteness=3,
            corroboration=3,
        ),
    )
    serialized = record.model_dump(mode="json")
    assert serialized["source"]["publicationDate"] != serialized["source"]["retrievalTimestamp"]


def test_defaultGonkaRoles_useDistinctVerifierModels() -> None:
    settings = Settings(_env_file=None)
    assert settings.GONKA_MODEL_A != settings.GONKA_MODEL_B
    assert settings.GONKA_MODEL_A == "MiniMaxAI/MiniMax-M2.7"
    assert settings.GONKA_MODEL_B == "deepseek-ai/DeepSeek-V4-Flash-0731"
    assert settings.GONKA_JUDGE_MODEL == "MiniMaxAI/MiniMax-M2.7"
    assert settings.GONKA_REDUCED_CALLS is True
    assert settings.MAX_EVIDENCE_QUERIES_PER_CLAIM == 1
    assert settings.MAX_EVIDENCE_PER_CLAIM == 6
    assert settings.MAX_TOTAL_EVIDENCE == 8


def test_duplicateVerifierModel_isRejected() -> None:
    with pytest.raises(ValidationError, match="verifier A and verifier B models must be distinct"):
        Settings(
            _env_file=None,
            GONKA_MODEL_A="model-a",
            GONKA_MODEL_B="model-a",
            GONKA_JUDGE_MODEL="model-b",
        )


def test_judgeMayReuseVerifierModel() -> None:
    settings = Settings(
        _env_file=None,
        GONKA_MODEL_A="model-a",
        GONKA_MODEL_B="model-b",
        GONKA_JUDGE_MODEL="model-a",
    )
    assert settings.GONKA_JUDGE_MODEL == settings.GONKA_MODEL_A


def test_exampleEnvironment_acceptsBlankOptionalSettings(monkeypatch: pytest.MonkeyPatch) -> None:
    for settingName in Settings.model_fields:
        monkeypatch.delenv(settingName, raising=False)
    exampleEnvironment = Path(__file__).resolve().parents[2] / ".env.example"
    settings = Settings(_env_file=exampleEnvironment)
    assert settings.SUPABASE_URL is None
    assert settings.SUPABASE_KEY is None
    assert settings.BRAVE_SEARCH_API_KEY is None
    assert settings.searchConfigured is False


def test_corsOrigins_acceptExplicitOriginsAndRemoveDuplicates() -> None:
    settings = Settings(
        _env_file=None,
        CORS_ALLOWED_ORIGINS=(
            "http://127.0.0.1:5500/, https://truthscope.example, http://127.0.0.1:5500"
        ),
    )
    assert settings.corsAllowedOrigins == [
        "http://127.0.0.1:5500",
        "https://truthscope.example",
    ]


@pytest.mark.parametrize(
    "origin",
    ["*", "file:///tmp/frontend", "https://example.com/path", ""],
)
def test_corsOrigins_rejectUnsafeOrNonOriginValues(origin: str) -> None:
    with pytest.raises(ValidationError, match="CORS"):
        Settings(_env_file=None, CORS_ALLOWED_ORIGINS=origin)
