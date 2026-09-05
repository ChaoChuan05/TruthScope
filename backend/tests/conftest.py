from collections.abc import Mapping

import pytest

from app.agents.graph import VerificationWorkflow
from app.core.exceptions import GonkaUnavailableError
from app.integrations.gonka.fake import ScriptedGonkaClient
from app.integrations.retrieval.client import FixtureDocumentFetcher, FixtureEvidenceRetriever
from app.integrations.supabase.client import InMemoryVerificationRepository
from app.schemas.common import EvidenceStance, SourceType
from app.schemas.evidence import (
    EvidenceQuality,
    EvidenceRecord,
    RetrievedDocument,
    SourceMetadata,
)
from app.services.verificationService import VerificationService


@pytest.fixture
def sampleEvidence() -> EvidenceRecord:
    return EvidenceRecord(
        evidenceId="evidence-1",
        source=SourceMetadata(
            url="https://example.gov.my/report",
            title="Public report",
            publisher="Example agency",
            sourceType=SourceType.PRIMARY,
        ),
        excerpt="Audited record states the measured value was 42 units.",
        claimIds=["claim-1"],
        stance=EvidenceStance.SUPPORTS,
        stanceStrength=0.9,
        quality=EvidenceQuality(
            provenance=5,
            directness=5,
            dateRelevance=5,
            contextCompleteness=4,
            corroboration=4,
        ),
    )


@pytest.fixture
def sampleDocument() -> RetrievedDocument:
    return RetrievedDocument(
        source=SourceMetadata(
            url="https://example.com/claim",
            title="Published claim",
            publisher="example.com",
        ),
        text="The measured value was 42 units according to the published record.",
        contentType="text/html; charset=utf-8",
    )


def standardResponses() -> dict[str, list[Mapping[str, object] | Exception]]:
    analysis = {
        "claimId": "claim-1",
        "stance": "supports",
        "supportStrength": 0.9,
        "confidence": 0.85,
        "usedEvidenceIds": ["evidence-1"],
        "contradictingEvidenceIds": [],
        "evidenceAssessments": [
            {"evidenceId": "evidence-1", "stance": "supports", "strength": 0.9}
        ],
        "missingContext": [],
        "reasoningSummary": "Supplied record directly supports the measured value.",
        "warnings": [],
    }
    return {
        "claimExtraction": [
            {
                "normalizedText": "The measured value was 42 units.",
                "claims": [
                    {
                        "claimId": "claim-1",
                        "originalText": "The measured value was 42 units.",
                        "normalizedText": "The measured value was 42 units.",
                        "claimType": "statistic",
                        "language": "English",
                        "verifiable": True,
                        "qualifiers": [],
                    }
                ],
            }
        ],
        "evidencePlanning": [
            {
                "queries": [
                    {
                        "claimId": "claim-1",
                        "query": "measured value 42 official record",
                        "preferredSourceTypes": ["primary", "secondary"],
                        "rationale": "Find direct record and corroboration.",
                    }
                ]
            }
        ],
        "contextAnalysis": [
            {
                "findings": ["Unit is preserved."],
                "warnings": [],
                "staleEvidenceIds": [],
                "suspectedTruncationEvidenceIds": [],
            }
        ],
        "verifierModelA": [{"analyses": [analysis]}],
        "verifierModelB": [{"analyses": [analysis]}],
        "consensusJudge": [
            {
                "verdict": "strongly_supported",
                "supportValue": 0.9,
                "confidence": 0.85,
                "reliedEvidenceIds": ["evidence-1"],
                "agreements": ["Both analyses identify direct support."],
                "disagreements": [],
                "reasoningSummary": "Evidence consistently supports the claim.",
                "warnings": [],
                "gonkaRequestId": None,
            }
        ],
        "biasAudit": [
            {
                "status": "passed",
                "violations": [],
                "omittedEvidenceIds": [],
                "reasoningSummary": "No political identity weighting was used.",
                "confidencePenalty": 1.0,
                "gonkaRequestId": None,
            }
        ],
    }


def buildService(
    evidence: list[EvidenceRecord],
    responses: dict[str, list[Mapping[str, object] | Exception]] | None = None,
    document: RetrievedDocument | None = None,
    parallelVerifiers: bool = False,
    reducedGonkaCalls: bool = False,
) -> tuple[VerificationService, ScriptedGonkaClient]:
    fakeClient = ScriptedGonkaClient(responses or standardResponses())
    workflow = VerificationWorkflow(
        gonkaClient=fakeClient,
        retriever=FixtureEvidenceRetriever(evidence),
        documentFetcher=FixtureDocumentFetcher(document),
        orchestratorModel="gonka-orchestrator",
        biasAuditorModel="gonka-auditor",
        parallelVerifiers=parallelVerifiers,
        reducedGonkaCalls=reducedGonkaCalls,
        modelA="gonka-model-a",
        modelB="gonka-model-b",
        judgeModel="gonka-judge",
    )
    return VerificationService(workflow, InMemoryVerificationRepository()), fakeClient


@pytest.fixture
def serviceFactory():
    return buildService


@pytest.fixture
def unavailableError() -> GonkaUnavailableError:
    return GonkaUnavailableError("Provider unavailable.")
