from app.schemas.agentOutput import AgentAnalysis, BiasAuditResult, EvidenceAssessment
from app.schemas.common import BiasAuditStatus, ClaimType, EvidenceStance, Verdict
from app.schemas.evidence import EvidenceQuality, EvidenceRecord, SourceMetadata
from app.schemas.verification import Claim
from app.services.scoringService import calculateVerificationScore


def makeClaim(text: str) -> Claim:
    return Claim(
        claimId="claim-1",
        originalText=text,
        normalizedText=text,
        claimType=ClaimType.FACTUAL,
    )


def makeEvidence(evidenceId: str, stance: EvidenceStance) -> EvidenceRecord:
    return EvidenceRecord(
        evidenceId=evidenceId,
        source=SourceMetadata(url=f"https://example.com/{evidenceId}", title=evidenceId),
        excerpt="Controlled synthetic evidence.",
        claimIds=["claim-1"],
        stance=stance,
        stanceStrength=1,
        quality=EvidenceQuality(
            provenance=5,
            directness=5,
            dateRelevance=5,
            contextCompleteness=5,
            corroboration=5,
        ),
    )


def makeAnalysis(modelName: str, stance: EvidenceStance, ids: list[str]) -> AgentAnalysis:
    return AgentAnalysis(
        claimId="claim-1",
        modelName=modelName,
        stance=stance,
        supportStrength=1,
        confidence=1,
        usedEvidenceIds=ids,
        evidenceAssessments=[
            EvidenceAssessment(evidenceId=evidenceId, stance=stance, strength=1)
            for evidenceId in ids
        ],
        reasoningSummary="Controlled evidence assessment.",
    )


def passedAudit() -> BiasAuditResult:
    return BiasAuditResult(
        status=BiasAuditStatus.PASSED,
        reasoningSummary="No asymmetric treatment.",
    )


def test_politicalLabelChange_doesNotChangeScore() -> None:
    evidence = [makeEvidence("evidence-1", EvidenceStance.SUPPORTS)]
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1"]),
        makeAnalysis("model-b", EvidenceStance.SUPPORTS, ["evidence-1"]),
    ]
    bnScore = calculateVerificationScore(
        claims=[makeClaim("BN reported the value.")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    phScore = calculateVerificationScore(
        claims=[makeClaim("PH reported the value.")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    assert bnScore == phScore


def test_strongContradiction_canHaveHighConfidence() -> None:
    evidence = [
        makeEvidence("evidence-1", EvidenceStance.CONTRADICTS),
        makeEvidence("evidence-2", EvidenceStance.CONTRADICTS),
    ]
    analyses = [
        makeAnalysis("model-a", EvidenceStance.CONTRADICTS, ["evidence-1", "evidence-2"]),
        makeAnalysis("model-b", EvidenceStance.CONTRADICTS, ["evidence-1", "evidence-2"]),
    ]
    score = calculateVerificationScore(
        claims=[makeClaim("Claim")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    assert score is not None
    assert score.truthScore == 0
    assert score.confidenceScore == 100
    assert score.verdict == Verdict.STRONGLY_CONTRADICTED


def test_mixedEvidence_neverProducesStrongVerdict() -> None:
    evidence = [
        makeEvidence("evidence-1", EvidenceStance.SUPPORTS),
        makeEvidence("evidence-2", EvidenceStance.CONTRADICTS),
    ]
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1"]),
        makeAnalysis("model-b", EvidenceStance.CONTRADICTS, ["evidence-2"]),
    ]
    score = calculateVerificationScore(
        claims=[makeClaim("Claim")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    assert score is not None
    assert score.verdict == Verdict.MIXED_OR_INCONCLUSIVE


def test_governmentSource_canStronglyContradictGovernmentClaim() -> None:
    evidence = [
        makeEvidence("evidence-1", EvidenceStance.CONTRADICTS),
        makeEvidence("evidence-2", EvidenceStance.CONTRADICTS),
    ]
    for record in evidence:
        record.source.publisher = "Government agency"
    analyses = [
        makeAnalysis("model-a", EvidenceStance.CONTRADICTS, ["evidence-1", "evidence-2"]),
        makeAnalysis("model-b", EvidenceStance.CONTRADICTS, ["evidence-1", "evidence-2"]),
    ]
    score = calculateVerificationScore(
        claims=[makeClaim("Government claim")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    assert score is not None
    assert score.verdict == Verdict.STRONGLY_CONTRADICTED


def test_sourcePublisherIdentity_doesNotChangeWeight() -> None:
    governmentEvidence = makeEvidence("evidence-1", EvidenceStance.SUPPORTS)
    governmentEvidence.source.publisher = "Government agency"
    oppositionEvidence = governmentEvidence.model_copy(deep=True)
    oppositionEvidence.source.publisher = "Opposition party"
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1"]),
        makeAnalysis("model-b", EvidenceStance.SUPPORTS, ["evidence-1"]),
    ]
    governmentScore = calculateVerificationScore(
        claims=[makeClaim("Claim")],
        evidence=[governmentEvidence],
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    oppositionScore = calculateVerificationScore(
        claims=[makeClaim("Claim")],
        evidence=[oppositionEvidence],
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )
    assert governmentScore == oppositionScore
