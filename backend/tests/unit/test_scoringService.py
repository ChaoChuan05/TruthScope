from app.schemas.agentOutput import AgentAnalysis, BiasAuditResult, EvidenceAssessment
from app.schemas.common import BiasAuditStatus, ClaimType, EvidenceStance, Verdict
from app.schemas.evidence import EvidenceQuality, EvidenceRecord, SourceMetadata
from app.schemas.verification import Claim
from app.services.scoringService import calculateModelAgreement, calculateVerificationScore


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


def test_modelAgreement_comparesModelsOnlyWithinSameClaim() -> None:
    claimOneModelA = makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1"])
    claimOneModelB = makeAnalysis("model-b", EvidenceStance.SUPPORTS, ["evidence-1"])
    claimTwoModelA = makeAnalysis("model-a", EvidenceStance.CONTRADICTS, ["evidence-2"])
    claimTwoModelA.claimId = "claim-2"
    claimTwoModelB = makeAnalysis("model-b", EvidenceStance.CONTRADICTS, ["evidence-2"])
    claimTwoModelB.claimId = "claim-2"

    agreement = calculateModelAgreement(
        [claimOneModelA, claimOneModelB, claimTwoModelA, claimTwoModelB]
    )

    assert agreement == 1


def test_modelAgreement_doesNotCountDuplicateSameModelAsIndependent() -> None:
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1"]),
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1"]),
    ]

    assert calculateModelAgreement(analyses) == 0.5


def test_multiClaimScore_weightsClaimsEquallyDespiteEvidenceVolume() -> None:
    claimOne = makeClaim("Claim one")
    claimTwo = makeClaim("Claim two").model_copy(update={"claimId": "claim-2"})
    supportingEvidence = [
        makeEvidence(f"support-{index}", EvidenceStance.SUPPORTS) for index in range(12)
    ]
    contradictingEvidence = makeEvidence("contradict", EvidenceStance.CONTRADICTS).model_copy(
        update={"claimIds": ["claim-2"]}
    )
    supportIds = [record.evidenceId for record in supportingEvidence]
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, supportIds),
        makeAnalysis("model-b", EvidenceStance.SUPPORTS, supportIds),
        makeAnalysis("model-a", EvidenceStance.CONTRADICTS, ["contradict"]).model_copy(
            update={"claimId": "claim-2"}
        ),
        makeAnalysis("model-b", EvidenceStance.CONTRADICTS, ["contradict"]).model_copy(
            update={"claimId": "claim-2"}
        ),
    ]

    score = calculateVerificationScore(
        claims=[claimOne, claimTwo],
        evidence=[*supportingEvidence, contradictingEvidence],
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )

    assert score is not None
    assert score.truthScore == 50
    assert score.verdict == Verdict.MIXED_OR_INCONCLUSIVE


def test_sharedEvidence_isAssessedSeparatelyForEachClaim() -> None:
    claimOne = makeClaim("Claim one")
    claimTwo = makeClaim("Claim two").model_copy(update={"claimId": "claim-2"})
    evidence = makeEvidence("shared", EvidenceStance.UNCLEAR).model_copy(
        update={"claimIds": ["claim-1", "claim-2"]}
    )
    claimOneAnalyses = [
        makeAnalysis(model, EvidenceStance.SUPPORTS, ["shared"]) for model in ("model-a", "model-b")
    ]
    claimTwoAnalyses = [
        makeAnalysis(model, EvidenceStance.CONTRADICTS, ["shared"]).model_copy(
            update={"claimId": "claim-2"}
        )
        for model in ("model-a", "model-b")
    ]

    score = calculateVerificationScore(
        claims=[claimOne, claimTwo],
        evidence=[evidence],
        analyses=[*claimOneAnalyses, *claimTwoAnalyses],
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )

    assert score is not None
    assert score.truthScore == 50
    assert score.confidenceScore > 0


def test_duplicateAnalysisFromOneModel_cannotProduceStrongVerdict() -> None:
    evidence = [
        makeEvidence("evidence-1", EvidenceStance.SUPPORTS),
        makeEvidence("evidence-2", EvidenceStance.SUPPORTS),
    ]
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1", "evidence-2"]),
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1", "evidence-2"]),
    ]

    score = calculateVerificationScore(
        claims=[makeClaim("Claim")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=passedAudit(),
        contextAnalysis=None,
    )

    assert score is not None
    assert score.truthScore == 100
    assert score.verdict == Verdict.MIXED_OR_INCONCLUSIVE
    assert score.formulaVersion == "truthscope-evidence-v2"


def test_unavailableBiasAudit_cannotProduceStrongVerdict() -> None:
    evidence = [
        makeEvidence("evidence-1", EvidenceStance.SUPPORTS),
        makeEvidence("evidence-2", EvidenceStance.SUPPORTS),
    ]
    analyses = [
        makeAnalysis("model-a", EvidenceStance.SUPPORTS, ["evidence-1", "evidence-2"]),
        makeAnalysis("model-b", EvidenceStance.SUPPORTS, ["evidence-1", "evidence-2"]),
    ]
    unavailableAudit = BiasAuditResult(
        status=BiasAuditStatus.UNAVAILABLE,
        reasoningSummary="Audit unavailable.",
        confidencePenalty=0.7,
    )

    score = calculateVerificationScore(
        claims=[makeClaim("Claim")],
        evidence=evidence,
        analyses=analyses,
        biasAudit=unavailableAudit,
        contextAnalysis=None,
    )

    assert score is not None
    assert score.truthScore == 100
    assert score.verdict == Verdict.MIXED_OR_INCONCLUSIVE
