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


def test_defaultGonkaRoles_useThreeDistinctModels() -> None:
    settings = Settings(_env_file=None)
    assert (
        len(
            {
                settings.GONKA_MODEL_A,
                settings.GONKA_MODEL_B,
                settings.GONKA_JUDGE_MODEL,
            }
        )
        == 3
    )
    assert settings.GONKA_JUDGE_MODEL == "deepseek-ai/DeepSeek-V4-Flash-0731"


def test_duplicateJudgeModel_isRejected() -> None:
    with pytest.raises(ValidationError, match="must be distinct"):
        Settings(
            _env_file=None,
            GONKA_MODEL_A="model-a",
            GONKA_MODEL_B="model-b",
            GONKA_JUDGE_MODEL="model-b",
        )


def test_exampleEnvironment_acceptsBlankOptionalSettings(monkeypatch: pytest.MonkeyPatch) -> None:
    for settingName in Settings.model_fields:
        monkeypatch.delenv(settingName, raising=False)
    exampleEnvironment = Path(__file__).resolve().parents[2] / ".env.example"
    settings = Settings(_env_file=exampleEnvironment)
    assert settings.SUPABASE_URL is None
    assert settings.SUPABASE_KEY is None
    assert settings.BRAVE_SEARCH_API_KEY is None
    assert settings.searchConfigured is False
