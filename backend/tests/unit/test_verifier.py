import pytest

from app.agents.nodes.biasAuditor import createBiasAuditNode
from app.agents.nodes.verifier import VerifierOutput, _validatedAnalyses, createVerifierNode
from app.agents.state import VerificationGraphState
from app.core.exceptions import InvalidModelOutputError
from app.integrations.gonka.fake import UnavailableGonkaClient
from app.schemas.agentOutput import GonkaInferenceRecord, JudgeResult
from app.schemas.common import ClaimType, EvidenceStance, OutputLanguage, Verdict
from app.schemas.evidence import EvidenceQuality, EvidenceRecord, SourceMetadata
from app.schemas.verification import Claim


def makeClaim(claimId: str) -> Claim:
    return Claim(
        claimId=claimId,
        originalText=claimId,
        normalizedText=claimId,
        claimType=ClaimType.FACTUAL,
    )


def makeEvidence(evidenceId: str, claimId: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidenceId=evidenceId,
        source=SourceMetadata(url=f"https://example.com/{evidenceId}", title=evidenceId),
        excerpt="Controlled evidence.",
        claimIds=[claimId],
        stance=EvidenceStance.UNCLEAR,
        quality=EvidenceQuality(
            provenance=3,
            directness=3,
            dateRelevance=3,
            contextCompleteness=3,
            corroboration=3,
        ),
    )


def makeAnalysis(claimId: str, evidenceId: str | None = None) -> dict[str, object]:
    evidenceIds = [evidenceId] if evidenceId else []
    return {
        "claimId": claimId,
        "stance": "unclear",
        "supportStrength": 0,
        "confidence": 0,
        "usedEvidenceIds": evidenceIds,
        "contradictingEvidenceIds": [],
        "evidenceAssessments": [{"evidenceId": evidenceId, "stance": "unclear", "strength": 0}]
        if evidenceId
        else [],
        "missingContext": [],
        "reasoningSummary": "Controlled analysis.",
        "warnings": [],
    }


def inference() -> GonkaInferenceRecord:
    return GonkaInferenceRecord(
        taskName="verifierModelA",
        requestedModel="model-a",
        servedModel="model-a",
        requestId="request-1",
        latencyMs=1,
        outputText='{"analyses":[]}',
    )


def state() -> VerificationGraphState:
    return {
        "outputLanguage": OutputLanguage.ENGLISH,
        "claims": [makeClaim("claim-1"), makeClaim("claim-2")],
        "evidence": [makeEvidence("evidence-1", "claim-1"), makeEvidence("evidence-2", "claim-2")],
    }


def test_verifierOutput_requiresExactlyOneAnalysisPerClaim() -> None:
    output = VerifierOutput.model_validate(
        {"analyses": [makeAnalysis("claim-1"), makeAnalysis("claim-1")]}
    )

    with pytest.raises(InvalidModelOutputError) as captured:
        _validatedAnalyses(output, state(), inference())

    assert captured.value.reason == "semantic_validation"
    assert "analyses.claimId.duplicate" in captured.value.validationPaths
    assert "analyses.claimId.coverage" in captured.value.validationPaths


def test_verifierOutput_rejectsEvidenceMappedToAnotherClaim() -> None:
    output = VerifierOutput.model_validate(
        {
            "analyses": [
                makeAnalysis("claim-1", "evidence-2"),
                makeAnalysis("claim-2", "evidence-2"),
            ]
        }
    )

    with pytest.raises(InvalidModelOutputError) as captured:
        _validatedAnalyses(output, state(), inference())

    assert "analyses.0.evidenceId.claimMismatch" in captured.value.validationPaths


def test_verifierOutput_acceptsCompleteClaimLinkedAnalyses() -> None:
    output = VerifierOutput.model_validate(
        {
            "analyses": [
                makeAnalysis("claim-1", "evidence-1"),
                makeAnalysis("claim-2", "evidence-2"),
            ]
        }
    )

    analyses = _validatedAnalyses(output, state(), inference())

    assert [analysis.claimId for analysis in analyses] == ["claim-1", "claim-2"]
    assert all(analysis.modelName == "model-a" for analysis in analyses)


async def test_verifierStageDeadline_boundsAllNestedAttempts() -> None:
    node = createVerifierNode(
        UnavailableGonkaClient(),
        taskName="verifierModelA",
        modelName="model-a",
        stageTimeoutSeconds=0,
    )

    update = await node(state())

    assert update["errors"][0].code == "VERIFIER_FAILED"


async def test_biasAuditStageDeadline_boundsAllNestedAttempts() -> None:
    auditState = state()
    auditState["judgeResult"] = JudgeResult(
        verdict=Verdict.MIXED_OR_INCONCLUSIVE,
        supportValue=0,
        confidence=0,
        reasoningSummary="Controlled judgment.",
    )
    node = createBiasAuditNode(
        UnavailableGonkaClient(),
        "audit-model",
        stageTimeoutSeconds=0,
    )

    update = await node(auditState)

    assert update["errors"][0].code == "BIAS_AUDIT_FAILED"
